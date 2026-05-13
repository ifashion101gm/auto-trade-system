"""
Risk calculation utility functions for the Auto Trade System.

Pure functions (no side effects, no async operations) for calculating
risk management parameters including stop-loss, take-profit, position sizing,
and risk validation.

All functions are deterministic and easily testable.
"""
from typing import Dict, Any


def calculate_stop_loss_long(entry_price: float, atr: float, multiplier: float = 1.5) -> float:
    """
    Calculate stop-loss price for LONG position using ATR.
    
    Stop-loss is placed below entry price based on volatility (ATR).
    
    Args:
        entry_price: Entry price for the long position
        atr: Average True Range value
        multiplier: ATR multiplier (default 1.5)
    
    Returns:
        Stop-loss price (below entry price)
    
    Example:
        >>> sl = calculate_stop_loss_long(50000, 500, 1.5)
        >>> print(sl)  # 49250.0
    """
    return entry_price - (atr * multiplier)


def calculate_stop_loss_short(entry_price: float, atr: float, multiplier: float = 1.5) -> float:
    """
    Calculate stop-loss price for SHORT position using ATR.
    
    Stop-loss is placed above entry price based on volatility (ATR).
    
    Args:
        entry_price: Entry price for the short position
        atr: Average True Range value
        multiplier: ATR multiplier (default 1.5)
    
    Returns:
        Stop-loss price (above entry price)
    
    Example:
        >>> sl = calculate_stop_loss_short(50000, 500, 1.5)
        >>> print(sl)  # 50750.0
    """
    return entry_price + (atr * multiplier)


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    reward_risk_ratio: float = 2.0,
    side: str = 'LONG'
) -> float:
    """
    Calculate take-profit price based on reward-to-risk ratio.
    
    Take-profit is calculated to achieve the desired R:R ratio.
    For example, with 2:1 R:R and $100 risk, target profit is $200.
    
    Args:
        entry_price: Entry price
        stop_loss: Stop-loss price
        reward_risk_ratio: Desired reward-to-risk ratio (default 2.0)
        side: Position side - 'LONG' or 'SHORT'
    
    Returns:
        Take-profit price
    
    Raises:
        ValueError: If reward_risk_ratio is negative or zero
    
    Example:
        >>> tp = calculate_take_profit(50000, 49000, 2.0, 'LONG')
        >>> print(tp)  # 52000.0 ($2000 profit on $1000 risk)
    """
    if reward_risk_ratio <= 0:
        raise ValueError(f"Reward-to-risk ratio must be positive, got {reward_risk_ratio}")
    
    risk = abs(entry_price - stop_loss)
    
    if side == 'LONG':
        return entry_price + (risk * reward_risk_ratio)
    else:  # SHORT
        return entry_price - (risk * reward_risk_ratio)


def calculate_position_size(
    account_balance: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss_price: float,
    confidence: float = 1.0,
    max_leverage: int = 5
) -> Dict[str, Any]:
    """
    Calculate position size based on risk percentage.
    
    Uses the formula: position_size = (balance * risk% * confidence) / |entry - SL|
    
    This ensures that if the stop-loss is hit, the loss equals the desired
    risk percentage of the account balance.
    
    Args:
        account_balance: Total account balance in USD
        risk_per_trade_pct: Risk per trade as decimal (0.02 = 2%)
        entry_price: Entry price
        stop_loss_price: Stop-loss price
        confidence: Trade confidence (0.0-1.0), scales position size
        max_leverage: Maximum allowed leverage (default 5)
    
    Returns:
        Dictionary containing:
        - quantity: Position size in units
        - position_value: Total position value in USD
        - risk_amount: Dollar amount at risk
        - leverage: Required leverage
        - risk_per_unit: Risk per unit (|entry - SL|)
    
    Raises:
        ValueError: If prices are invalid or SL equals entry
    
    Example:
        >>> result = calculate_position_size(10000, 0.02, 50000, 49000)
        >>> print(result['quantity'])  # 0.2
        >>> print(result['risk_amount'])  # 200.0
    """
    # Validate inputs
    if entry_price <= 0 or stop_loss_price <= 0:
        raise ValueError("Prices must be positive")
    
    if entry_price == stop_loss_price:
        raise ValueError("Entry price cannot equal stop loss price")
    
    if not (0 < confidence <= 1):
        raise ValueError(f"Confidence must be between 0 and 1, got {confidence}")
    
    if not (0 < risk_per_trade_pct <= 1):
        raise ValueError(f"Risk percentage must be between 0 and 1, got {risk_per_trade_pct}")
    
    # Calculate risk amount
    risk_amount = account_balance * risk_per_trade_pct * confidence
    
    # Calculate risk per unit
    risk_per_unit = abs(entry_price - stop_loss_price)
    
    # Calculate position size
    quantity = risk_amount / risk_per_unit
    position_value = quantity * entry_price
    
    # Calculate required leverage
    leverage_needed = position_value / account_balance if account_balance > 0 else 1
    leverage = min(int(leverage_needed) + 1, max_leverage)
    
    return {
        'quantity': round(quantity, 8),
        'position_value': round(position_value, 2),
        'risk_amount': round(risk_amount, 2),
        'leverage': leverage,
        'risk_per_unit': round(risk_per_unit, 2)
    }


def validate_risk_percentage(
    risk_pct: float,
    min_pct: float = 0.001,
    max_pct: float = 0.05
) -> bool:
    """
    Validate risk percentage is within acceptable bounds.
    
    Ensures risk per trade is neither too conservative nor too aggressive.
    
    Args:
        risk_pct: Risk per trade as decimal (0.02 = 2%)
        min_pct: Minimum allowed risk (default 0.1%)
        max_pct: Maximum allowed risk (default 5%)
    
    Returns:
        True if valid
    
    Raises:
        ValueError: If risk percentage is out of bounds
    
    Example:
        >>> validate_risk_percentage(0.02)  # 2% - OK
        True
        >>> validate_risk_percentage(0.10)  # 10% - Too high
        ValueError
    """
    if not (min_pct <= risk_pct <= max_pct):
        raise ValueError(
            f"Risk percentage {risk_pct:.2%} out of bounds "
            f"(must be between {min_pct:.2%} and {max_pct:.2%})"
        )
    return True


def calculate_max_position_value(
    account_balance: float,
    max_position_pct: float
) -> float:
    """
    Calculate maximum allowed position value based on account balance.
    
    Args:
        account_balance: Total account balance
        max_position_pct: Maximum position size as percentage of balance
    
    Returns:
        Maximum position value in USD
    
    Example:
        >>> calc_max_position_value(10000, 0.015)  # 1.5% of $10k
        150.0
    """
    return account_balance * max_position_pct


def calculate_drawdown(current_balance: float, peak_balance: float) -> float:
    """
    Calculate current drawdown from peak balance.
    
    Drawdown is the percentage decline from the highest balance reached.
    
    Args:
        current_balance: Current account balance
        peak_balance: Highest balance achieved
    
    Returns:
        Drawdown as decimal (0.0 to 1.0), never negative
    
    Example:
        >>> drawdown = calculate_drawdown(9000, 10000)
        >>> print(drawdown)  # 0.10 (10% drawdown)
    """
    if peak_balance <= 0:
        return 0.0
    
    drawdown = (peak_balance - current_balance) / peak_balance
    return max(drawdown, 0.0)  # Never negative
