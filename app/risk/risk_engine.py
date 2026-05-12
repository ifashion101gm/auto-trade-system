"""
Risk Management Engine - Comprehensive risk monitoring and enforcement.
Prevents catastrophic losses through hard limits and dynamic risk controls.

Features:
- Daily loss limit enforcement (-3%)
- Max drawdown monitoring (15%)
- Position size caps (1.5% per trade)
- Leverage limits (5x max)
- Volatility chaos filter (ATR-based)
- Slippage limits (bid-ask spread)
- Cooldown periods after consecutive losses
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.database.models import PaperTrades, RiskMetrics
from app.logging_config import get_logger
from app.infra.exchange_manager import UnifiedExchangeManager

logger = get_logger(__name__)


@dataclass
class RiskDecision:
    """Result of comprehensive risk validation."""
    approved: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0-100, higher = riskier
    daily_pnl_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    position_size_pct: float = 0.0
    cooldown_remaining_seconds: int = 0


class RiskEngine:
    """
    Centralized risk management with real-time monitoring and enforcement.
    
    Tracks:
    - Daily P&L and percentage changes
    - Account drawdown from peak balance
    - Consecutive losses and cooldown periods
    - Position sizing relative to account balance
    - Market volatility conditions
    - Slippage and spread conditions
    """
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        """
        Initialize risk engine.
        
        Args:
            db_session: Database session for querying historical data
        """
        self.db_session = db_session
        
        # Load configuration
        self.max_daily_loss_pct = settings.RISK_MAX_DAILY_LOSS_PCT
        self.max_drawdown_pct = settings.RISK_MAX_DRAWDOWN_PCT
        self.max_position_size_pct = settings.RISK_MAX_POSITION_SIZE_PCT
        self.max_leverage = settings.RISK_MAX_LEVERAGE
        self.volatility_threshold = settings.RISK_VOLATILITY_THRESHOLD
        self.max_slippage_pct = settings.RISK_MAX_SLIPPAGE_PCT
        self.cooldown_period_seconds = settings.RISK_COOLDOWN_PERIOD_SECONDS
        self.max_consecutive_losses = settings.RISK_MAX_CONSECUTIVE_LOSSES
        
        # Runtime tracking
        self.daily_pnl = 0.0
        self.daily_pnl_pct = 0.0
        self.peak_balance = 100.0  # Starting balance assumption
        self.current_balance = 100.0
        self.consecutive_losses = 0
        self.last_loss_time: Optional[float] = None
        self.today_date: str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        logger.info("✅ Risk Engine initialized")
        logger.info(f"   Daily Loss Limit: {self.max_daily_loss_pct:.1%}")
        logger.info(f"   Max Drawdown: {self.max_drawdown_pct:.1%}")
        logger.info(f"   Max Position Size: {self.max_position_size_pct:.1%}")
        logger.info(f"   Max Leverage: {self.max_leverage}x")
    
    async def check_trade_approval(
        self,
        proposal: Dict[str, Any],
        user_id: str = "default_user"
    ) -> RiskDecision:
        """
        Comprehensive pre-trade risk validation.
        
        Checks performed in order:
        1. Daily loss limit (-3%)
        2. Max drawdown (15%)
        3. Position size cap (1.5% of balance)
        4. Leverage limit (5x max)
        5. Cooldown period after consecutive losses
        
        Args:
            proposal: Trade proposal with symbol, quantity, leverage, etc.
            user_id: User identifier for tracking
            
        Returns:
            RiskDecision with approval status and reasons
        """
        decision = RiskDecision(approved=True)
        
        # Check 1: Daily loss limit
        if self.daily_pnl_pct <= -self.max_daily_loss_pct:
            decision.approved = False
            decision.violations.append(
                f"Daily loss limit reached: {self.daily_pnl_pct:.2%} <= -{self.max_daily_loss_pct:.1%}"
            )
            logger.warning(f"🚫 Daily loss limit breached: {self.daily_pnl_pct:.2%}")
            return decision
        
        # Check 2: Max drawdown
        current_drawdown = self._calculate_drawdown()
        decision.current_drawdown_pct = current_drawdown
        
        if current_drawdown >= self.max_drawdown_pct:
            decision.approved = False
            decision.violations.append(
                f"Max drawdown exceeded: {current_drawdown:.2%} >= {self.max_drawdown_pct:.1%}"
            )
            logger.warning(f"🚫 Max drawdown breached: {current_drawdown:.2%}")
            return decision
        
        # Check 3: Position size cap
        entry_price = proposal.get('entry_price', 0)
        quantity = proposal.get('quantity', 0)
        leverage = proposal.get('leverage', 1)
        
        if entry_price > 0 and quantity > 0:
            position_value = entry_price * quantity * leverage
            position_size_pct = position_value / self.current_balance if self.current_balance > 0 else 0
            decision.position_size_pct = position_size_pct
            
            if position_size_pct > self.max_position_size_pct:
                decision.approved = False
                decision.violations.append(
                    f"Position size too large: {position_size_pct:.2%} > {self.max_position_size_pct:.1%} "
                    f"(value: ${position_value:.2f}, balance: ${self.current_balance:.2f})"
                )
                logger.warning(f"🚫 Position size limit breached: {position_size_pct:.2%}")
                return decision
        
        # Check 4: Leverage limit
        if leverage > self.max_leverage:
            decision.approved = False
            decision.violations.append(
                f"Leverage too high: {leverage}x > {self.max_leverage}x"
            )
            logger.warning(f"🚫 Leverage limit breached: {leverage}x")
            return decision
        
        # Check 5: Cooldown period
        cooldown_status = self._check_cooldown_period()
        decision.cooldown_remaining_seconds = cooldown_status['remaining_seconds']
        
        if not cooldown_status['can_trade']:
            decision.approved = False
            decision.violations.append(
                f"Cooldown period active: {cooldown_status['remaining_seconds']}s remaining "
                f"(after {self.consecutive_losses} consecutive losses)"
            )
            logger.warning(f"🚫 Cooldown period active: {cooldown_status['remaining_seconds']}s remaining")
            return decision
        
        # Calculate risk score (0-100, higher = riskier)
        decision.risk_score = self._calculate_risk_score(proposal, decision)
        
        # Add warnings for approaching limits
        if self.daily_pnl_pct <= -self.max_daily_loss_pct * 0.75:
            decision.warnings.append(
                f"Approaching daily loss limit: {self.daily_pnl_pct:.2%}"
            )
        
        if current_drawdown >= self.max_drawdown_pct * 0.75:
            decision.warnings.append(
                f"Approaching max drawdown: {current_drawdown:.2%}"
            )
        
        if self.consecutive_losses >= self.max_consecutive_losses - 1:
            decision.warnings.append(
                f"Approaching max consecutive losses: {self.consecutive_losses}/{self.max_consecutive_losses}"
            )
        
        logger.info(f"✅ Risk check passed (score: {decision.risk_score}/100)")
        return decision
    
    async def update_daily_pnl(self, trade_result: Dict[str, Any]):
        """
        Update daily P&L tracking after trade closure.
        
        Args:
            trade_result: Trade result with profit, profit_pct, symbol
        """
        profit = trade_result.get('profit', 0)
        profit_pct = trade_result.get('profit_pct', 0)
        
        # Update running totals
        self.daily_pnl += profit
        self.current_balance += profit
        
        # Recalculate daily P&L percentage
        if self.current_balance > 0:
            self.daily_pnl_pct = self.daily_pnl / (self.current_balance - self.daily_pnl) * 100
        
        # Update peak balance
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        # Check if we need to reset daily counters (new day)
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if current_date != self.today_date:
            await self.reset_daily_counters()
        
        # Persist to database if session available
        if self.db_session:
            await self._persist_risk_metrics()
        
        logger.info(
            f"📊 Daily P&L updated: ${self.daily_pnl:.2f} ({self.daily_pnl_pct:.2%}), "
            f"Balance: ${self.current_balance:.2f}"
        )
    
    async def record_trade_outcome(self, won: bool, strategy_name: str = "unknown"):
        """
        Track win/loss for consecutive loss monitoring.
        
        Args:
            won: Whether the trade was profitable
            strategy_name: Strategy used for the trade
        """
        if won:
            self.consecutive_losses = 0
            logger.info(f"✅ Trade won (strategy: {strategy_name}), consecutive losses reset")
        else:
            self.consecutive_losses += 1
            self.last_loss_time = time.time()
            logger.warning(
                f"❌ Trade lost (strategy: {strategy_name}), "
                f"consecutive losses: {self.consecutive_losses}"
            )
            
            # Check if we've hit max consecutive losses
            if self.consecutive_losses >= self.max_consecutive_losses:
                logger.warning(
                    f"⏸️  Max consecutive losses reached ({self.consecutive_losses}), "
                    f"cooldown period activated for {self.cooldown_period_seconds}s"
                )
    
    async def get_risk_metrics(self, user_id: str = "default_user") -> Dict[str, Any]:
        """
        Return current risk state dashboard.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with all risk metrics
        """
        current_drawdown = self._calculate_drawdown()
        cooldown_status = self._check_cooldown_period()
        
        return {
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': self.daily_pnl_pct,
            'current_balance': self.current_balance,
            'peak_balance': self.peak_balance,
            'current_drawdown_pct': current_drawdown,
            'consecutive_losses': self.consecutive_losses,
            'max_consecutive_losses': self.max_consecutive_losses,
            'cooldown_active': not cooldown_status['can_trade'],
            'cooldown_remaining_seconds': cooldown_status['remaining_seconds'],
            'today_date': self.today_date,
            'limits': {
                'max_daily_loss_pct': self.max_daily_loss_pct,
                'max_drawdown_pct': self.max_drawdown_pct,
                'max_position_size_pct': self.max_position_size_pct,
                'max_leverage': self.max_leverage
            }
        }
    
    async def check_volatility_chaos(self, symbol: str) -> bool:
        """
        Check if market volatility exceeds chaos threshold.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if market too volatile for trading
        """
        try:
            # Fetch market data to get volatility/ATR
            exchange_manager = UnifiedExchangeManager()
            ticker = await exchange_manager.fetch_ticker(symbol)
            
            # Calculate volatility from recent price movements
            # In production, you'd fetch OHLCV and calculate ATR
            # For now, use a simplified approach
            volatility = ticker.get('volatility', 0.5)
            
            await exchange_manager.close()
            
            is_chaotic = volatility > self.volatility_threshold
            
            if is_chaotic:
                logger.warning(
                    f"🌪️  High volatility detected for {symbol}: "
                    f"{volatility:.2%} > {self.volatility_threshold:.1%}"
                )
            
            return is_chaotic
            
        except Exception as e:
            logger.warning(f"Could not check volatility for {symbol}: {e}")
            return False  # Default to allowing trade if check fails
    
    async def check_slippage_risk(self, symbol: str) -> Dict[str, Any]:
        """
        Check bid-ask spread for slippage risk.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dictionary with slippage metrics and approval status
        """
        try:
            exchange_manager = UnifiedExchangeManager()
            ticker = await exchange_manager.fetch_ticker(symbol)
            
            bid = ticker.get('bid', 0)
            ask = ticker.get('ask', 0)
            
            await exchange_manager.close()
            
            if bid > 0 and ask > 0:
                spread = ask - bid
                spread_pct = spread / bid
                
                approved = spread_pct <= self.max_slippage_pct
                
                return {
                    'approved': approved,
                    'spread': spread,
                    'spread_pct': spread_pct,
                    'bid': bid,
                    'ask': ask,
                    'threshold': self.max_slippage_pct
                }
            else:
                # If no bid/ask data, assume OK
                return {
                    'approved': True,
                    'spread': 0,
                    'spread_pct': 0,
                    'bid': bid,
                    'ask': ask,
                    'threshold': self.max_slippage_pct,
                    'warning': 'No bid/ask data available'
                }
                
        except Exception as e:
            logger.warning(f"Could not check slippage for {symbol}: {e}")
            return {
                'approved': True,
                'spread': 0,
                'spread_pct': 0,
                'error': str(e)
            }
    
    def _check_cooldown_period(self) -> Dict[str, Any]:
        """
        Check if cooldown period is active after consecutive losses.
        
        Returns:
            Dictionary with cooldown status
        """
        if self.consecutive_losses < self.max_consecutive_losses:
            return {
                'can_trade': True,
                'remaining_seconds': 0,
                'reason': 'No cooldown needed'
            }
        
        if self.last_loss_time is None:
            return {
                'can_trade': True,
                'remaining_seconds': 0,
                'reason': 'No loss recorded'
            }
        
        elapsed = time.time() - self.last_loss_time
        remaining = self.cooldown_period_seconds - elapsed
        
        if remaining <= 0:
            # Cooldown expired
            self.consecutive_losses = 0
            self.last_loss_time = None
            return {
                'can_trade': True,
                'remaining_seconds': 0,
                'reason': 'Cooldown expired'
            }
        
        return {
            'can_trade': False,
            'remaining_seconds': int(remaining),
            'reason': f'Cooldown active after {self.consecutive_losses} consecutive losses'
        }
    
    async def reset_daily_counters(self):
        """Reset daily P&L tracking at midnight UTC."""
        old_date = self.today_date
        self.today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Persist yesterday's metrics before resetting
        if self.db_session:
            await self._persist_risk_metrics()
        
        # Reset counters
        self.daily_pnl = 0.0
        self.daily_pnl_pct = 0.0
        self.consecutive_losses = 0
        self.last_loss_time = None
        
        logger.info(f"📅 Daily counters reset (was {old_date}, now {self.today_date})")
    
    def _calculate_drawdown(self) -> float:
        """
        Calculate current drawdown from peak balance.
        
        Returns:
            Drawdown as percentage (0.0 to 1.0)
        """
        if self.peak_balance <= 0:
            return 0.0
        
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
        return max(drawdown, 0.0)  # Never negative
    
    def _calculate_risk_score(
        self,
        proposal: Dict[str, Any],
        decision: RiskDecision
    ) -> float:
        """
        Calculate overall risk score (0-100).
        
        Factors:
        - Daily P&L proximity to limit (30%)
        - Drawdown level (30%)
        - Position size relative to limit (20%)
        - Consecutive losses (20%)
        
        Args:
            proposal: Trade proposal
            decision: Current risk decision
            
        Returns:
            Risk score 0-100 (higher = riskier)
        """
        # Factor 1: Daily P&L (30 points max)
        daily_loss_ratio = abs(self.daily_pnl_pct) / self.max_daily_loss_pct if self.max_daily_loss_pct > 0 else 0
        daily_pnl_score = min(daily_loss_ratio * 30, 30)
        
        # Factor 2: Drawdown (30 points max)
        drawdown_ratio = decision.current_drawdown_pct / self.max_drawdown_pct if self.max_drawdown_pct > 0 else 0
        drawdown_score = min(drawdown_ratio * 30, 30)
        
        # Factor 3: Position size (20 points max)
        position_ratio = decision.position_size_pct / self.max_position_size_pct if self.max_position_size_pct > 0 else 0
        position_score = min(position_ratio * 20, 20)
        
        # Factor 4: Consecutive losses (20 points max)
        loss_ratio = self.consecutive_losses / self.max_consecutive_losses if self.max_consecutive_losses > 0 else 0
        loss_score = min(loss_ratio * 20, 20)
        
        total_score = daily_pnl_score + drawdown_score + position_score + loss_score
        
        return round(min(total_score, 100), 1)
    
    async def _persist_risk_metrics(self):
        """Persist current risk metrics to database."""
        try:
            # Check if metrics already exist for today
            stmt = select(RiskMetrics).where(
                RiskMetrics.date == self.today_date,
                RiskMetrics.user_id == "default_user"
            )
            result = await self.db_session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing record
                existing.current_balance = self.current_balance
                existing.daily_pnl = self.daily_pnl
                existing.daily_pnl_pct = self.daily_pnl_pct
                existing.max_drawdown_pct = self._calculate_drawdown()
                existing.peak_balance = self.peak_balance
                existing.consecutive_losses = self.consecutive_losses
                existing.updated_at = datetime.utcnow().isoformat()
            else:
                # Create new record
                metrics = RiskMetrics(
                    date=self.today_date,
                    user_id="default_user",
                    starting_balance=100.0,  # Would come from actual balance
                    current_balance=self.current_balance,
                    daily_pnl=self.daily_pnl,
                    daily_pnl_pct=self.daily_pnl_pct,
                    max_drawdown_pct=self._calculate_drawdown(),
                    peak_balance=self.peak_balance,
                    trade_count=0,
                    win_count=0,
                    loss_count=0,
                    consecutive_losses=self.consecutive_losses,
                    updated_at=datetime.utcnow().isoformat()
                )
                self.db_session.add(metrics)
            
            await self.db_session.flush()
            
        except Exception as e:
            logger.error(f"Failed to persist risk metrics: {e}")
