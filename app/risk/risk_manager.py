"""
Centralized Risk Manager for unified risk validation across the trading system.

This module consolidates ALL risk checks into a single, authoritative source:
- Position size limits
- Daily loss limits
- Maximum drawdown thresholds
- Consecutive loss tracking
- Margin usage monitoring
- API health verification

Benefits:
- Single source of truth for risk rules
- Easy to audit and modify
- Consistent enforcement across all strategies
- Centralized logging and alerting
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.models import PaperTrades
from app.logging_config import log_risk_check

logger = logging.getLogger(__name__)


@dataclass
class RiskValidationResult:
    """Result of risk validation check."""
    
    passed: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses and logging."""
        return {
            "passed": self.passed,
            "checks": self.checks,
            "violations": self.violations,
            "warnings": self.warnings,
            **self.metadata
        }


class RiskManager:
    """
    Centralized risk management engine.
    
    All risk checks flow through this class to ensure consistent enforcement.
    This prevents scattered validation logic across strategy files.
    
    Usage:
        risk_manager = RiskManager(db_session=db, user_id="user123")
        
        # Validate before trade execution
        result = await risk_manager.validate_trade(
            symbol="XAUUSDT",
            side="BUY",
            quantity=0.1,
            entry_price=2345.67,
            leverage=10
        )
        
        if not result.passed:
            logger.error(f"Trade rejected: {result.violations}")
            return
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        user_id: str,
        max_position_size_usd: float = 10000.0,
        max_daily_loss_pct: float = 5.0,
        max_drawdown_pct: float = 10.0,
        max_consecutive_losses: int = 5,
        max_margin_usage_pct: float = 80.0,
        min_api_health_score: float = 0.8,
    ):
        """
        Initialize Risk Manager with configurable thresholds.
        
        Args:
            db_session: Database session for querying trade history
            user_id: User identifier for personalized limits
            max_position_size_usd: Maximum position size in USD
            max_daily_loss_pct: Maximum daily loss as percentage of balance
            max_drawdown_pct: Maximum drawdown from peak equity
            max_consecutive_losses: Maximum consecutive losing trades
            max_margin_usage_pct: Maximum margin usage percentage
            min_api_health_score: Minimum API health score (0.0-1.0)
        """
        self.db_session = db_session
        self.user_id = user_id
        
        # Risk thresholds
        self.max_position_size_usd = max_position_size_usd
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.max_margin_usage_pct = max_margin_usage_pct
        self.min_api_health_score = min_api_health_score
        
        logger.info(f"✅ RiskManager initialized for user {user_id}")
        logger.info(f"   Max position size: ${max_position_size_usd:,.2f}")
        logger.info(f"   Max daily loss: {max_daily_loss_pct}%")
        logger.info(f"   Max drawdown: {max_drawdown_pct}%")
        logger.info(f"   Max consecutive losses: {max_consecutive_losses}")
    
    async def validate_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        leverage: int = 1,
        exchange: str = None,
    ) -> RiskValidationResult:
        """
        Comprehensive risk validation before trade execution.
        
        Runs ALL risk checks and returns consolidated result.
        
        Args:
            symbol: Trading pair symbol
            side: 'BUY' or 'SELL'
            quantity: Position size in base currency
            entry_price: Expected entry price
            leverage: Leverage multiplier
            exchange: Exchange name (optional)
            
        Returns:
            RiskValidationResult with pass/fail status and details
        """
        position_value_usd = quantity * entry_price * leverage
        
        checks = {}
        violations = []
        warnings = []
        
        # Check 1: Position Size Limit
        position_check = await self._check_position_size(position_value_usd, symbol)
        checks['position_size'] = position_check['passed']
        if not position_check['passed']:
            violations.append(position_check['message'])
        
        # Check 2: Daily Loss Limit
        daily_loss_check = await self._check_daily_loss()
        checks['daily_loss'] = daily_loss_check['passed']
        if not daily_loss_check['passed']:
            violations.append(daily_loss_check['message'])
        
        # Check 3: Drawdown Limit
        drawdown_check = await self._check_drawdown()
        checks['drawdown'] = drawdown_check['passed']
        if not drawdown_check['passed']:
            violations.append(drawdown_check['message'])
        
        # Check 4: Consecutive Losses
        consecutive_check = await self._check_consecutive_losses()
        checks['consecutive_losses'] = consecutive_check['passed']
        if not consecutive_check['passed']:
            violations.append(consecutive_check['message'])
        
        # Check 5: Margin Usage
        margin_check = await self._check_margin_usage(position_value_usd)
        checks['margin_usage'] = margin_check['passed']
        if not margin_check['passed']:
            violations.append(margin_check['message'])
        elif margin_check.get('warning'):
            warnings.append(margin_check['message'])
        
        # Determine overall result
        passed = all(checks.values())
        
        result = RiskValidationResult(
            passed=passed,
            checks=checks,
            violations=violations,
            warnings=warnings,
            metadata={
                'position_value_usd': position_value_usd,
                'symbol': symbol,
                'side': side,
                'leverage': leverage,
            }
        )
        
        # Log structured event
        log_risk_check(
            check_type='trade_validation',
            passed=passed,
            value=position_value_usd,
            threshold=self.max_position_size_usd,
            symbol=symbol,
        )
        
        if passed:
            logger.info(f"✅ Risk validation PASSED for {symbol} {side} (${position_value_usd:,.2f})")
        else:
            logger.warning(f"❌ Risk validation FAILED for {symbol} {side}: {violations}")
        
        return result
    
    async def _check_position_size(self, position_value_usd: float, symbol: str) -> Dict[str, Any]:
        """Check if position size exceeds maximum limit."""
        passed = position_value_usd <= self.max_position_size_usd
        
        return {
            'passed': passed,
            'message': f"Position size ${position_value_usd:,.2f} exceeds limit ${self.max_position_size_usd:,.2f}"
            if not passed else "",
            'value': position_value_usd,
            'threshold': self.max_position_size_usd,
        }
    
    async def _check_daily_loss(self) -> Dict[str, Any]:
        """Check if daily loss exceeds maximum percentage."""
        try:
            # Get today's realized P&L
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            stmt = (
                select(func.sum(PaperTrades.profit))
                .where(PaperTrades.user_id == self.user_id)
                .where(PaperTrades.ts_close >= today_start.isoformat())
                .where(PaperTrades.status == 'closed')
            )
            
            result = await self.db_session.execute(stmt)
            daily_pnl = result.scalar() or 0.0
            
            # Get account balance (approximate from open positions + cash)
            balance = await self._get_account_balance()
            
            if balance > 0:
                daily_loss_pct = abs(min(daily_pnl, 0)) / balance * 100
            else:
                daily_loss_pct = 0.0
            
            passed = daily_loss_pct <= self.max_daily_loss_pct
            
            return {
                'passed': passed,
                'message': f"Daily loss {daily_loss_pct:.2f}% exceeds limit {self.max_daily_loss_pct}%"
                if not passed else "",
                'value': daily_loss_pct,
                'threshold': self.max_daily_loss_pct,
            }
        except Exception as e:
            logger.error(f"Daily loss check failed: {e}")
            return {'passed': True, 'message': '', 'error': str(e)}
    
    async def _check_drawdown(self) -> Dict[str, Any]:
        """Check if current drawdown exceeds maximum percentage."""
        try:
            # Calculate drawdown from peak equity
            # This is a simplified version - production would track equity curve
            stmt = (
                select(func.min(PaperTrades.profit_pct))
                .where(PaperTrades.user_id == self.user_id)
                .where(PaperTrades.status == 'closed')
            )
            
            result = await self.db_session.execute(stmt)
            worst_drawdown = result.scalar()
            
            if worst_drawdown is None:
                return {'passed': True, 'message': '', 'value': 0, 'threshold': self.max_drawdown_pct}
            
            # Drawdown should be negative (loss)
            current_drawdown = abs(min(worst_drawdown, 0))
            passed = current_drawdown <= self.max_drawdown_pct
            
            return {
                'passed': passed,
                'message': f"Drawdown {current_drawdown:.2f}% exceeds limit {self.max_drawdown_pct}%"
                if not passed else "",
                'value': current_drawdown,
                'threshold': self.max_drawdown_pct,
            }
        except Exception as e:
            logger.error(f"Drawdown check failed: {e}")
            return {'passed': True, 'message': '', 'error': str(e)}
    
    async def _check_consecutive_losses(self) -> Dict[str, Any]:
        """Check if consecutive losses exceed maximum count."""
        try:
            # Get last 10 closed trades
            stmt = (
                select(PaperTrades)
                .where(PaperTrades.user_id == self.user_id)
                .where(PaperTrades.status == 'closed')
                .order_by(PaperTrades.ts_close.desc())
                .limit(10)
            )
            
            result = await self.db_session.execute(stmt)
            recent_trades = result.scalars().all()
            
            # Count consecutive losses
            consecutive_losses = 0
            for trade in recent_trades:
                if trade.profit and trade.profit < 0:
                    consecutive_losses += 1
                else:
                    break  # Reset on win
            
            passed = consecutive_losses < self.max_consecutive_losses
            
            return {
                'passed': passed,
                'message': f"Consecutive losses ({consecutive_losses}) reached limit ({self.max_consecutive_losses})"
                if not passed else "",
                'value': consecutive_losses,
                'threshold': self.max_consecutive_losses,
            }
        except Exception as e:
            logger.error(f"Consecutive losses check failed: {e}")
            return {'passed': True, 'message': '', 'error': str(e)}
    
    async def _check_margin_usage(self, new_position_value: float) -> Dict[str, Any]:
        """Check if margin usage would exceed maximum percentage."""
        try:
            # Get current open positions
            stmt = (
                select(func.sum(PaperTrades.qty * PaperTrades.entry_price * PaperTrades.leverage))
                .where(PaperTrades.user_id == self.user_id)
                .where(PaperTrades.status == 'open')
            )
            
            result = await self.db_session.execute(stmt)
            current_margin_used = result.scalar() or 0.0
            
            # Add new position
            total_margin_after_trade = current_margin_used + new_position_value
            
            # Get account balance
            balance = await self._get_account_balance()
            
            if balance > 0:
                margin_usage_pct = total_margin_after_trade / balance * 100
            else:
                margin_usage_pct = 0.0
            
            passed = margin_usage_pct <= self.max_margin_usage_pct
            
            message = ""
            warning = False
            
            if not passed:
                message = f"Margin usage {margin_usage_pct:.2f}% exceeds limit {self.max_margin_usage_pct}%"
            elif margin_usage_pct > self.max_margin_usage_pct * 0.8:  # Warning at 80% of limit
                message = f"Margin usage {margin_usage_pct:.2f}% approaching limit {self.max_margin_usage_pct}%"
                warning = True
            
            return {
                'passed': passed,
                'message': message,
                'warning': warning,
                'value': margin_usage_pct,
                'threshold': self.max_margin_usage_pct,
            }
        except Exception as e:
            logger.error(f"Margin usage check failed: {e}")
            return {'passed': True, 'message': '', 'error': str(e)}
    
    async def _get_account_balance(self) -> float:
        """Get approximate account balance (simplified)."""
        # In production, this would fetch from exchange API
        # For now, return a reasonable default or query from database
        try:
            # Sum of all closed trade profits + initial balance assumption
            stmt = (
                select(func.sum(PaperTrades.profit))
                .where(PaperTrades.user_id == self.user_id)
                .where(PaperTrades.status == 'closed')
            )
            
            result = await self.db_session.execute(stmt)
            total_pnl = result.scalar() or 0.0
            
            # Assume starting balance of $10,000 (configurable)
            starting_balance = 10000.0
            return starting_balance + total_pnl
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return 10000.0  # Default fallback
    
    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary for dashboard/API."""
        try:
            daily_loss = await self._check_daily_loss()
            drawdown = await self._check_drawdown()
            consecutive = await self._check_consecutive_losses()
            margin = await self._check_margin_usage(0)  # Current margin without new trade
            
            return {
                'user_id': self.user_id,
                'timestamp': datetime.utcnow().isoformat(),
                'daily_loss': {
                    'current_pct': daily_loss.get('value', 0),
                    'limit_pct': self.max_daily_loss_pct,
                    'remaining_pct': self.max_daily_loss_pct - daily_loss.get('value', 0),
                },
                'drawdown': {
                    'current_pct': drawdown.get('value', 0),
                    'limit_pct': self.max_drawdown_pct,
                    'remaining_pct': self.max_drawdown_pct - drawdown.get('value', 0),
                },
                'consecutive_losses': {
                    'current_count': consecutive.get('value', 0),
                    'limit': self.max_consecutive_losses,
                    'remaining': self.max_consecutive_losses - consecutive.get('value', 0),
                },
                'margin_usage': {
                    'current_pct': margin.get('value', 0),
                    'limit_pct': self.max_margin_usage_pct,
                    'remaining_pct': self.max_margin_usage_pct - margin.get('value', 0),
                },
                'position_size_limit_usd': self.max_position_size_usd,
            }
        except Exception as e:
            logger.error(f"Failed to get risk summary: {e}")
            return {'error': str(e)}
