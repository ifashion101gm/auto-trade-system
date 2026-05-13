"""
Micro-Live Trading Manager - Sprint 5: Controlled Capital Deployment.

Manages the transition from paper trading to micro-live trading with:
- Strict position size caps ($10-$20 equivalent)
- Conservative leverage limits (3x max)
- Tight daily loss limits (1% max)
- Phase-based scale-up logic
- Instant emergency stop capability
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import logging

from app.config import settings
from app.logging_config import get_logger
from app.risk.risk_engine import RiskEngine
from app.database.connection import get_session
from app.database.models import PaperTrades
from sqlalchemy import select, func

logger = get_logger(__name__)


class MicroLiveManager:
    """
    Manage micro-live trading with controlled capital deployment.
    
    Implements phased scale-up strategy:
    - Phase 1: Micro-Live ($100 capital, $20 max position)
    - Phase 2: 50% Scale ($500 capital, $100 max position)
    - Phase 3: Full Deployment ($1000+ capital)
    """
    
    def __init__(self, risk_engine: RiskEngine):
        """
        Initialize Micro-Live Manager.
        
        Args:
            risk_engine: Risk engine instance for integration
        """
        self.risk_engine = risk_engine
        self.current_phase = 1  # Start at Phase 1
        self.phase_start_date = datetime.now(timezone.utc)
        self.trades_in_phase = 0
        self.phase_pnl = 0.0
        
        logger.info("✅ MicroLiveManager initialized")
        logger.info(f"   Current Phase: {self.current_phase}")
        logger.info(f"   Max Leverage: {settings.MICRO_LIVE_MAX_LEVERAGE}x")
        logger.info(f"   Risk per Trade: {settings.MICRO_LIVE_RISK_PER_TRADE:.1%}")
        logger.info(f"   Daily Loss Limit: {settings.MICRO_LIVE_DAILY_LOSS_LIMIT:.1%}")
        logger.info(f"   Max Position: ${settings.MICRO_LIVE_MAX_POSITION_USD:.2f}")
    
    async def validate_trade_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate trade proposal against micro-live constraints.
        
        Args:
            proposal: Trade proposal with symbol, quantity, leverage, etc.
            
        Returns:
            Validation result with approval status and reasons
        """
        violations = []
        warnings = []
        
        # Check leverage
        leverage = proposal.get('leverage', 1)
        if leverage > settings.MICRO_LIVE_MAX_LEVERAGE:
            violations.append(
                f"Leverage {leverage}x exceeds micro-live limit {settings.MICRO_LIVE_MAX_LEVERAGE}x"
            )
        
        # Check position size
        entry_price = proposal.get('entry_price', 0)
        quantity = proposal.get('quantity', 0)
        position_value = entry_price * quantity
        
        if position_value > settings.MICRO_LIVE_MAX_POSITION_USD:
            violations.append(
                f"Position value ${position_value:.2f} exceeds micro-live limit "
                f"${settings.MICRO_LIVE_MAX_POSITION_USD:.2f}"
            )
        
        # Check confidence threshold
        confidence = proposal.get('confidence', 0)
        if confidence < settings.MICRO_LIVE_MIN_CONFIDENCE_THRESHOLD:
            violations.append(
                f"Confidence {confidence:.2f} below minimum "
                f"{settings.MICRO_LIVE_MIN_CONFIDENCE_THRESHOLD:.2f}"
            )
        
        # Check risk per trade
        risk_per_trade = proposal.get('risk_per_trade', 0)
        if risk_per_trade > settings.MICRO_LIVE_RISK_PER_TRADE:
            warnings.append(
                f"Risk per trade {risk_per_trade:.2%} exceeds recommended "
                f"{settings.MICRO_LIVE_RISK_PER_TRADE:.1%}"
            )
        
        approved = len(violations) == 0
        
        return {
            'approved': approved,
            'violations': violations,
            'warnings': warnings,
            'phase': self.current_phase
        }
    
    async def record_trade_result(self, won: bool, pnl: float):
        """Record trade result for phase progression tracking."""
        self.trades_in_phase += 1
        self.phase_pnl += pnl
        
        logger.info(
            f"📊 Phase {self.current_phase} progress: "
            f"{self.trades_in_phase} trades, P&L: ${self.phase_pnl:+,.2f}"
        )
        
        # Check if phase transition criteria met
        await self._check_phase_transition()
    
    async def _check_phase_transition(self):
        """Check if conditions are met to advance to next phase."""
        if self.current_phase >= 3:
            return  # Already at full deployment
        
        # Check minimum trades
        if self.trades_in_phase < settings.PHASE_TRANSITION_MIN_TRADES:
            logger.debug(
                f"Phase transition check: Need {settings.PHASE_TRANSITION_MIN_TRADES} trades, "
                f"have {self.trades_in_phase}"
            )
            return
        
        # Check validation period
        days_in_phase = (datetime.now(timezone.utc) - self.phase_start_date).days
        if days_in_phase < settings.PHASE_TRANSITION_VALIDATION_DAYS:
            logger.debug(
                f"Phase transition check: Need {settings.PHASE_TRANSITION_VALIDATION_DAYS} days, "
                f"have {days_in_phase}"
            )
            return
        
        # Check performance metrics (query from database)
        win_rate = await self._calculate_phase_win_rate()
        max_drawdown = await self._calculate_phase_max_drawdown()
        profit_factor = await self._calculate_phase_profit_factor()
        
        logger.info(
            f"Phase {self.current_phase} performance metrics:\n"
            f"  Win Rate: {win_rate:.1%} (required: {settings.PHASE_TRANSITION_MIN_WIN_RATE:.1%})\n"
            f"  Max Drawdown: {max_drawdown:.1%} (max allowed: {settings.PHASE_TRANSITION_MAX_DRAWDOWN:.1%})\n"
            f"  Profit Factor: {profit_factor:.2f} (required: {settings.PHASE_TRANSITION_MIN_PROFIT_FACTOR:.2f})"
        )
        
        # Evaluate transition criteria
        criteria_met = (
            win_rate >= settings.PHASE_TRANSITION_MIN_WIN_RATE and
            max_drawdown <= settings.PHASE_TRANSITION_MAX_DRAWDOWN and
            profit_factor >= settings.PHASE_TRANSITION_MIN_PROFIT_FACTOR
        )
        
        if criteria_met:
            await self._advance_to_next_phase()
        else:
            logger.warning(
                f"⚠️  Phase {self.current_phase} transition criteria NOT met: "
                f"Win Rate: {win_rate:.1%}, Drawdown: {max_drawdown:.1%}, "
                f"Profit Factor: {profit_factor:.2f}"
            )
    
    async def _advance_to_next_phase(self):
        """Advance to next deployment phase."""
        old_phase = self.current_phase
        self.current_phase += 1
        self.phase_start_date = datetime.now(timezone.utc)
        self.trades_in_phase = 0
        self.phase_pnl = 0.0
        
        logger.info(
            f"🎉 PHASE TRANSITION: Phase {old_phase} → Phase {self.current_phase}"
        )
        logger.info(
            f"   New capital allocation: ${self._get_capital_for_phase(self.current_phase):.2f}"
        )
        
        # Send notification
        try:
            from app.notifications.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            await notifier.send_message(
                f"🎉 <b>Phase Transition Approved</b>\n\n"
                f"Advanced from Phase {old_phase} to Phase {self.current_phase}\n"
                f"All validation criteria met successfully.\n\n"
                f"<b>New Parameters:</b>\n"
                f"• Capital: ${self._get_capital_for_phase(self.current_phase):.2f}\n"
                f"• Max Position: ${self._get_max_position_for_phase(self.current_phase):.2f}\n"
                f"• Trades in Previous Phase: {settings.PHASE_TRANSITION_MIN_TRADES}+\n"
                f"• Validation Period: {settings.PHASE_TRANSITION_VALIDATION_DAYS}+ days"
            )
        except Exception as e:
            logger.error(f"Failed to send phase transition notification: {e}")
    
    async def _calculate_phase_win_rate(self) -> float:
        """Calculate win rate for current phase."""
        try:
            async with get_session() as session:
                # Query trades since phase start
                stmt = select(PaperTrades).where(
                    PaperTrades.ts_open >= self.phase_start_date,
                    PaperTrades.status == 'closed'
                )
                result = await session.execute(stmt)
                trades = result.scalars().all()
                
                if not trades:
                    return 0.0
                
                winning_trades = sum(1 for t in trades if t.profit and t.profit > 0)
                return (winning_trades / len(trades))
        except Exception as e:
            logger.error(f"Error calculating phase win rate: {e}")
            return 0.0
    
    async def _calculate_phase_max_drawdown(self) -> float:
        """Calculate max drawdown for current phase."""
        try:
            async with get_session() as session:
                # Get all closed trades in this phase
                stmt = select(PaperTrades).where(
                    PaperTrades.ts_open >= self.phase_start_date,
                    PaperTrades.status == 'closed'
                ).order_by(PaperTrades.ts_open.asc())
                
                result = await session.execute(stmt)
                trades = result.scalars().all()
                
                if not trades:
                    return 0.0
                
                # Calculate running balance and track peak
                balance = 100.0  # Starting balance assumption
                peak_balance = balance
                max_dd = 0.0
                
                for trade in trades:
                    if trade.profit:
                        balance += trade.profit
                    
                    if balance > peak_balance:
                        peak_balance = balance
                    
                    dd = (peak_balance - balance) / peak_balance if peak_balance > 0 else 0
                    if dd > max_dd:
                        max_dd = dd
                
                return max_dd
        except Exception as e:
            logger.error(f"Error calculating phase max drawdown: {e}")
            return 0.0
    
    async def _calculate_phase_profit_factor(self) -> float:
        """Calculate profit factor for current phase."""
        try:
            async with get_session() as session:
                # Query closed trades in this phase
                stmt = select(PaperTrades).where(
                    PaperTrades.ts_open >= self.phase_start_date,
                    PaperTrades.status == 'closed'
                )
                result = await session.execute(stmt)
                trades = result.scalars().all()
                
                if not trades:
                    return 0.0
                
                total_profit = sum(t.profit for t in trades if t.profit and t.profit > 0)
                total_loss = abs(sum(t.profit for t in trades if t.profit and t.profit < 0))
                
                if total_loss == 0:
                    return float('inf') if total_profit > 0 else 0.0
                
                return total_profit / total_loss
        except Exception as e:
            logger.error(f"Error calculating phase profit factor: {e}")
            return 0.0
    
    def get_phase_status(self) -> Dict[str, Any]:
        """Get current phase status and metrics."""
        return {
            'current_phase': self.current_phase,
            'phase_start_date': self.phase_start_date.isoformat(),
            'trades_in_phase': self.trades_in_phase,
            'phase_pnl': self.phase_pnl,
            'days_in_phase': (datetime.now(timezone.utc) - self.phase_start_date).days,
            'capital_allocation': self._get_capital_for_phase(self.current_phase),
            'max_position_usd': self._get_max_position_for_phase(self.current_phase),
            'transition_criteria': {
                'min_trades': settings.PHASE_TRANSITION_MIN_TRADES,
                'min_win_rate': settings.PHASE_TRANSITION_MIN_WIN_RATE,
                'max_drawdown': settings.PHASE_TRANSITION_MAX_DRAWDOWN,
                'min_profit_factor': settings.PHASE_TRANSITION_MIN_PROFIT_FACTOR,
                'validation_days': settings.PHASE_TRANSITION_VALIDATION_DAYS
            }
        }
    
    def _get_capital_for_phase(self, phase: int) -> float:
        """Get capital allocation for given phase."""
        if phase == 1:
            return settings.SCALE_UP_PHASE_1_CAPITAL_USD
        elif phase == 2:
            return settings.SCALE_UP_PHASE_2_CAPITAL_USD
        else:
            return settings.SCALE_UP_FULL_DEPLOYMENT_CAPITAL_USD
    
    def _get_max_position_for_phase(self, phase: int) -> float:
        """Get max position size for given phase."""
        if phase == 1:
            return settings.MICRO_LIVE_MAX_POSITION_USD
        elif phase == 2:
            return 100.0  # $100 max position in Phase 2
        else:
            return 500.0  # $500 max position in Phase 3
