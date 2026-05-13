"""
Technical indicator calculation functions for the Auto Trade System.

Pure functions (no side effects, no async operations) for calculating
common technical indicators used in trading strategies. All functions
are deterministic and easily testable.

Indicators included:
- ATR (Average True Range)
- RSI (Relative Strength Index)
- SMA (Simple Moving Average)
- EMA (Exponential Moving Average)
"""
from typing import List


def calculate_true_range(high: float, low: float, prev_close: float) -> float:
    """
    Calculate True Range for a single period.
    
    True Range is the greatest of:
    1. Current high minus current low
    2. Absolute value of current high minus previous close
    3. Absolute value of current low minus previous close
    
    Args:
        high: Current period high price
        low: Current period low price
        prev_close: Previous period close price
    
    Returns:
        True Range value
    """
    return max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close)
    )


def calculate_atr(ohlcv: List[List[float]], period: int = 14) -> float:
    """
    Calculate Average True Range (ATR).
    
    ATR measures market volatility by averaging true ranges over a period.
    Higher ATR indicates higher volatility.
    
    Args:
        ohlcv: List of candles in format [timestamp, open, high, low, close, volume]
        period: ATR calculation period (default 14)
    
    Returns:
        ATR value
    
    Raises:
        ValueError: If insufficient data points (< period + 1 candles)
    
    Example:
        >>> ohlcv = [[1, 100, 105, 95, 100, 1000], ...]
        >>> atr = calculate_atr(ohlcv, period=14)
    """
    if len(ohlcv) < period + 1:
        raise ValueError(f"Need at least {period + 1} candles for ATR calculation with period {period}")
    
    # Calculate true ranges for all periods
    true_ranges = []
    for i in range(1, len(ohlcv)):
        prev_close = ohlcv[i-1][4]  # Close price from previous candle
        high = ohlcv[i][2]           # High price from current candle
        low = ohlcv[i][3]            # Low price from current candle
        tr = calculate_true_range(high, low, prev_close)
        true_ranges.append(tr)
    
    # Return simple average of last N true ranges
    return sum(true_ranges[-period:]) / period


def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """
    Calculate Relative Strength Index (RSI).
    
    RSI is a momentum oscillator that measures the speed and magnitude of
    recent price changes. Values range from 0 to 100.
    
    - RSI > 70: Overbought condition (potential sell signal)
    - RSI < 30: Oversold condition (potential buy signal)
    - RSI ~ 50: Neutral
    
    Args:
        closes: List of closing prices
        period: RSI calculation period (default 14)
    
    Returns:
        RSI value (0-100)
    
    Raises:
        ValueError: If insufficient data points (< period + 1 closes)
    
    Example:
        >>> closes = [100, 102, 104, 106, ...]
        >>> rsi = calculate_rsi(closes, period=14)
    """
    if len(closes) < period + 1:
        raise ValueError(f"Need at least {period + 1} closing prices for RSI calculation with period {period}")
    
    # Calculate price changes
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    
    # Separate gains and losses for the specified period
    gains = [max(0, d) for d in deltas[-period:]]
    losses = [abs(min(0, d)) for d in deltas[-period:]]
    
    # Calculate average gain and loss
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    # Handle edge case where there are no losses
    if avg_loss == 0:
        return 100.0
    
    # Calculate RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_sma(prices: List[float], period: int) -> float:
    """
    Calculate Simple Moving Average (SMA).
    
    SMA is the arithmetic mean of prices over a specified period.
    All prices are weighted equally.
    
    Args:
        prices: List of prices (typically closing prices)
        period: Number of periods for the moving average
    
    Returns:
        SMA value
    
    Raises:
        ValueError: If insufficient data points (< period prices)
    
    Example:
        >>> prices = [10, 20, 30, 40, 50]
        >>> sma = calculate_sma(prices, period=3)  # Returns 40.0
    """
    if len(prices) < period:
        raise ValueError(f"Need at least {period} prices for SMA calculation")
    
    return sum(prices[-period:]) / period


def calculate_ema(prices: List[float], period: int) -> float:
    """
    Calculate Exponential Moving Average (EMA).
    
    EMA gives more weight to recent prices, making it more responsive
    to new information compared to SMA.
    
    Formula:
        EMA_today = (Price_today * multiplier) + (EMA_yesterday * (1 - multiplier))
        where multiplier = 2 / (period + 1)
    
    Args:
        prices: List of prices (typically closing prices)
        period: Number of periods for the moving average
    
    Returns:
        EMA value
    
    Raises:
        ValueError: If insufficient data points (< period prices)
    
    Example:
        >>> prices = [100, 100, 100, 100, 100, 150]
        >>> ema = calculate_ema(prices, period=5)  # EMA will be > SMA due to recent spike
    """
    if len(prices) < period:
        raise ValueError(f"Need at least {period} prices for EMA calculation")
    
    # Calculate multiplier
    multiplier = 2 / (period + 1)
    
    # Initialize EMA with SMA of first 'period' prices
    ema = sum(prices[:period]) / period
    
    # Calculate EMA for remaining prices
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    
    return ema


def calculate_bollinger_bands(
    prices: List[float],
    period: int = 20,
    num_std_dev: float = 2.0
) -> tuple:
    """
    Calculate Bollinger Bands.
    
    Bollinger Bands consist of:
    - Middle band: SMA of prices
    - Upper band: SMA + (standard deviation * num_std_dev)
    - Lower band: SMA - (standard deviation * num_std_dev)
    
    Args:
        prices: List of closing prices
        period: Period for SMA calculation (default 20)
        num_std_dev: Number of standard deviations for bands (default 2.0)
    
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    
    Raises:
        ValueError: If insufficient data points
    
    Example:
        >>> upper, middle, lower = calculate_bollinger_bands(prices, period=20)
    """
    if len(prices) < period:
        raise ValueError(f"Need at least {period} prices for Bollinger Bands calculation")
    
    # Calculate middle band (SMA)
    middle_band = calculate_sma(prices, period)
    
    # Calculate standard deviation
    recent_prices = prices[-period:]
    variance = sum((p - middle_band) ** 2 for p in recent_prices) / period
    std_dev = variance ** 0.5
    
    # Calculate upper and lower bands
    upper_band = middle_band + (std_dev * num_std_dev)
    lower_band = middle_band - (std_dev * num_std_dev)
    
    return (upper_band, middle_band, lower_band)
