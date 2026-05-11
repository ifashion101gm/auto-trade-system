"""
Risk Agent - Validates trades against risk rules before execution.
Implements kill switches, daily limits, correlation checks.
"""
from app.infra.trade_validator import TradeValidator
from app.events.event_bus import event_bus
from app.events.event_types import RISK_CHECK_PASSED, RISK_CHECK_FAILED
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


class RiskAgent:
    """
    Validates trades against risk rules before execution.
    Implements kill switches, daily limits, correlation checks.
    """
    
    def __init__(self):
        self.validator = TradeValidator()
        self.daily_pnl = 0.0
        self.max_daily_loss = -200.0  # $200 max loss
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3
    
    async def validate_trade(self, proposal, user_id="system", db_session: AsyncSession = None):
        """Comprehensive risk validation."""
        logger.info("⚖️  Risk Agent: Validating trade...")
        
        # Check daily loss limit
        if self.daily_pnl <= self.max_daily_loss:
            await event_bus.publish(RISK_CHECK_FAILED, {
                'reason': 'Daily loss limit reached',
                'daily_pnl': self.daily_pnl
            })
            return False, "Daily loss limit reached"
        
        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            await event_bus.publish(RISK_CHECK_FAILED, {
                'reason': 'Max consecutive losses reached',
                'count': self.consecutive_losses
            })
            return False, "Too many consecutive losses"
        
        # Run validator checks
        validation = await self.validator.validate_trade(
            proposal=proposal,
            user_id=user_id,
            db_session=db_session,
            exchange='mexc',
            symbol=proposal['symbol']
        )
        
        if not validation.approved:
            await event_bus.publish(RISK_CHECK_FAILED, {
                'violations': validation.violations
            })
            return False, f"Validation failed: {validation.violations}"
        
        # Passed all checks
        await event_bus.publish(RISK_CHECK_PASSED, {
            'warnings': validation.warnings
        })
        return True, "Approved"
    
    def update_performance(self, won: bool):
        """Update risk metrics after trade closes."""
        if won:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
