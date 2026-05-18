"""
Trade validation module that enforces trading strategy rules before execution.
Validates confidence thresholds, risk limits, leverage caps, and position constraints.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import settings
from app.database.models import PaperTrades
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of trade validation checks."""
    approved: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.0
    risk_threshold: float = 0.0
    position_value: float = 0.0
    risk_amount: float = 0.0
    account_balance: float = 0.0
    daily_drawdown_pct: float = 0.0
    open_positions_count: int = 0
    proposed_trade: Dict[str, Any] = field(default_factory=dict)


def get_active_confidence_threshold() -> float:
    """Get confidence threshold based on active trading profile."""
    if settings.TRADING_PROFILE == "safer_growth":
        return settings.SAFER_GROWTH_CONFIDENCE_THRESHOLD
    return settings.AGGRESSIVE_CONFIDENCE_THRESHOLD


def get_active_risk_per_trade() -> float:
    """Get risk per trade based on active trading profile."""
    if settings.TRADING_PROFILE == "safer_growth":
        return settings.SAFER_GROWTH_RISK_PER_TRADE
    return settings.AGGRESSIVE_RISK_PER_TRADE


def get_active_max_positions() -> int:
    """Get maximum open positions based on active trading profile."""
    if settings.TRADING_PROFILE == "safer_growth":
        return settings.SAFER_GROWTH_MAX_POSITIONS
    return settings.AGGRESSIVE_MAX_POSITIONS


def get_active_max_daily_drawdown() -> float:
    """Get maximum daily drawdown based on active trading profile."""
    if settings.TRADING_PROFILE == "safer_growth":
        return settings.SAFER_GROWTH_MAX_DAILY_DRAWDOWN
    return settings.AGGRESSIVE_MAX_DAILY_DRAWDOWN


class TradeValidator:
    """
    Validates trade proposals against active configuration rules.
    
    Performs pre-execution checks:
    - Confidence threshold (profile-based)
    - Risk per trade limit
    - Maximum leverage
    - Maximum open positions
    - Daily drawdown limit
    - Execution mode compliance
    """
    
    async def validate_trade(
        self,
        proposal: Dict[str, Any],
        user_id: str,
        db_session: AsyncSession,
        exchange: str = "mexc",
        symbol: str = "XAUT/USDT",
        account_balance: Optional[float] = None
    ) -> ValidationResult:
        """
        Validate a trade proposal against all active rules.
        
        Args:
            proposal: Trade proposal dictionary from AI orchestrator
            user_id: User identifier for tracking
            db_session: Database session for querying current state
            exchange: Exchange name (mexc, binance, etc.)
            symbol: Trading pair symbol
            account_balance: Current account balance for risk validation (optional)
            
        Returns:
            ValidationResult with approval status and any violations
        """
        result = ValidationResult(
            approved=True,
            proposed_trade={
                'symbol': symbol,
                'side': proposal.get('side'),
                'entry_price': proposal.get('entry_price', 0),
                'quantity': proposal.get('quantity', 0),
                'leverage': proposal.get('leverage', 1),
                'confidence': proposal.get('confidence', 0)
            }
        )
        
        # Run all validation checks
        await self._validate_confidence(proposal, result, symbol)
        await self._validate_risk_per_trade(proposal, result, exchange, symbol, account_balance)
        await self._validate_leverage(proposal, result, symbol)
        await self._validate_open_positions(user_id, db_session, result)
        await self._validate_daily_drawdown(user_id, db_session, result)
        await self._validate_execution_mode(proposal, result)
        
        # Set overall approval status
        result.approved = len(result.violations) == 0
        
        # Log validation result
        if result.approved:
            status = "APPROVED"
            if result.warnings:
                logger.info(
                    f"✅ Trade {status} with warnings for {symbol}: "
                    f"{len(result.warnings)} warnings"
                )
            else:
                logger.info(f"✅ Trade {status} for {symbol}")
        else:
            logger.warning(
                f"❌ Trade REJECTED for {symbol}: "
                f"{len(result.violations)} violations"
            )
            for violation in result.violations:
                logger.warning(f"   - {violation}")
        
        return result
    
    async def _validate_confidence(
        self,
        proposal: Dict[str, Any],
        result: ValidationResult,
        symbol: str
    ):
        """Validate confidence against profile threshold."""
        confidence = proposal.get('confidence', 0)
        
        # Determine effective threshold
        if 'GOLD' in symbol.upper() or 'XAUT' in symbol.upper() or 'PAXG' in symbol.upper():
            # Gold-specific minimum
            threshold = max(
                get_active_confidence_threshold(),
                settings.GOLD_MIN_CONFIDENCE
            )
        else:
            threshold = get_active_confidence_threshold()
        
        result.confidence_threshold = threshold
        
        if confidence < threshold:
            result.violations.append(
                f"Confidence {confidence:.2%} below threshold {threshold:.2%} "
                f"(profile: {settings.TRADING_PROFILE})"
            )
        elif confidence < threshold + 0.1:
            result.warnings.append(
                f"Confidence {confidence:.2%} is close to threshold {threshold:.2%}"
            )
    
    async def _validate_risk_per_trade(
        self,
        proposal: Dict[str, Any],
        result: ValidationResult,
        exchange: str,
        symbol: str,
        account_balance: Optional[float] = None
    ):
        """Validate risk per trade against limits.
        
        Uses ACCOUNT-BASED risk model (professional standard):
        - Risk is calculated as percentage of account balance
        - NOT as percentage of position value
        - This ensures consistency with position sizing logic
        """
        entry_price = proposal.get('entry_price', 0)
        stop_loss = proposal.get('stop_loss')
        quantity = proposal.get('quantity', 0)
        leverage = proposal.get('leverage', 1)
        
        if not stop_loss or entry_price <= 0 or quantity <= 0:
            result.warnings.append(
                "Cannot calculate risk: missing stop loss, entry price, or quantity"
            )
            return
        
        # Calculate position value and risk
        position_value = entry_price * quantity
        result.position_value = position_value
        
        # Calculate risk amount (distance to stop loss)
        risk_per_unit = abs(entry_price - stop_loss)
        risk_amount = risk_per_unit * quantity * leverage
        result.risk_amount = risk_amount
        
        # Store account balance for reference
        if account_balance:
            result.account_balance = account_balance
        
        # CRITICAL FIX: Use account-based risk model (not position-based)
        # This matches how positions are sized in the system
        if account_balance and account_balance > 0:
            # Calculate risk as percentage of ACCOUNT BALANCE
            risk_pct = risk_amount / account_balance
            logger.debug(
                f"Risk validation (account-based): "
                f"${risk_amount:.2f} / ${account_balance:.2f} = {risk_pct:.2%}"
            )
        else:
            # Fallback to position-based if no balance provided
            # This maintains backward compatibility
            risk_pct = risk_amount / position_value if position_value > 0 else 0
            logger.warning(
                f"No account balance provided, using position-based risk: "
                f"${risk_amount:.2f} / ${position_value:.2f} = {risk_pct:.2%}"
            )
        
        # Determine effective risk threshold
        if 'GOLD' in symbol.upper() or 'XAUT' in symbol.upper() or 'PAXG' in symbol.upper():
            # Gold-specific risk limit
            threshold = max(get_active_risk_per_trade(), settings.GOLD_RISK_PER_TRADE)
        else:
            threshold = get_active_risk_per_trade()
        
        result.risk_threshold = threshold
        
        if risk_pct > threshold:
            # Provide clear error message showing which model is being used
            if account_balance and account_balance > 0:
                violation_msg = (
                    f"Risk {risk_pct:.2%} (${risk_amount:.2f}) exceeds "
                    f"limit {threshold:.2%} of account balance ${account_balance:.2f}"
                )
            else:
                violation_msg = (
                    f"Risk {risk_pct:.2%} (${risk_amount:.2f}) exceeds "
                    f"limit {threshold:.2%} of position value ${position_value:.2f}"
                )
            result.violations.append(violation_msg)
    
    async def _validate_leverage(
        self,
        proposal: Dict[str, Any],
        result: ValidationResult,
        symbol: str
    ):
        """Validate leverage against maximum limits."""
        leverage = proposal.get('leverage', 1)
        
        # Gold-specific leverage limit
        if 'GOLD' in symbol.upper() or 'XAUT' in symbol.upper() or 'PAXG' in symbol.upper():
            max_leverage = settings.GOLD_MAX_LEVERAGE
            
            if leverage > max_leverage:
                result.violations.append(
                    f"Leverage {leverage}x exceeds Gold maximum {max_leverage}x"
                )
        # General leverage limit (configurable, default to 10x)
        elif leverage > 10:
            result.warnings.append(
                f"High leverage {leverage}x - consider reducing risk"
            )
    
    async def _validate_open_positions(
        self,
        user_id: str,
        db_session: AsyncSession,
        result: ValidationResult
    ):
        """Validate against maximum open positions limit."""
        # Query open positions count
        stmt = select(func.count(PaperTrades.id)).where(
            PaperTrades.user_id == user_id,
            PaperTrades.status == 'open'
        )
        query_result = await db_session.execute(stmt)
        open_count = query_result.scalar() or 0
        
        result.open_positions_count = open_count
        
        max_positions = get_active_max_positions()
        
        if open_count >= max_positions:
            result.violations.append(
                f"Already have {open_count} open positions, "
                f"maximum is {max_positions} (profile: {settings.TRADING_PROFILE})"
            )
        elif open_count >= max_positions - 1:
            result.warnings.append(
                f"Approaching position limit: {open_count}/{max_positions} open positions"
            )
    
    async def _validate_daily_drawdown(
        self,
        user_id: str,
        db_session: AsyncSession,
        result: ValidationResult
    ):
        """Validate against daily drawdown limit."""
        # Get today's closed trades
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        stmt = select(PaperTrades).where(
            PaperTrades.user_id == user_id,
            PaperTrades.status == 'closed',
            PaperTrades.ts_close >= today_start.isoformat()
        ).order_by(PaperTrades.ts_close)
        
        query_result = await db_session.execute(stmt)
        trades = query_result.scalars().all()
        
        if not trades:
            return  # No trades today, no drawdown to check
        
        # Calculate daily P&L and drawdown
        initial_balance = 100.0  # Starting balance assumption
        balance = initial_balance
        peak_balance = initial_balance
        max_drawdown = 0.0
        
        for trade in trades:
            if trade.profit:
                balance += trade.profit
                if balance > peak_balance:
                    peak_balance = balance
                
                drawdown = (peak_balance - balance) / peak_balance * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        result.daily_drawdown_pct = max_drawdown
        
        max_daily_drawdown = get_active_max_daily_drawdown() * 100  # Convert to percentage
        
        if max_drawdown > max_daily_drawdown:
            result.violations.append(
                f"Daily drawdown {max_drawdown:.2f}% exceeds limit {max_daily_drawdown:.2f}% "
                f"(profile: {settings.TRADING_PROFILE})"
            )
        elif max_drawdown > max_daily_drawdown * 0.75:
            result.warnings.append(
                f"Daily drawdown approaching limit: {max_drawdown:.2f}% / {max_daily_drawdown:.2f}%"
            )
    
    async def _validate_execution_mode(
        self,
        proposal: Dict[str, Any],
        result: ValidationResult
    ):
        """Validate execution mode compliance."""
        position_value = result.position_value
        
        if settings.EXECUTION_MODE == 'proposal':
            result.warnings.append(
                "Execution mode is 'proposal' - trade will not auto-execute"
            )
        elif settings.EXECUTION_MODE == 'semi-auto':
            threshold = settings.AUTO_EXECUTE_THRESHOLD_USD
            if position_value > threshold:
                result.warnings.append(
                    f"Position value ${position_value:.2f} exceeds "
                    f"auto-execute threshold ${threshold:.2f} - manual confirmation required"
                )
