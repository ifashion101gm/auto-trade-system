"""
Shared test fixtures and utilities for Auto Trade System unit tests.

Provides common test data, helper functions, and mock objects used across
all unit test modules to ensure consistency and reduce duplication.
"""
from typing import List, Dict, Any
import pytest


@pytest.fixture
def sample_ohlcv_data() -> List[List[float]]:
    """
    Return 50 candles of realistic OHLCV data with gradual uptrend.
    
    Format: [timestamp, open, high, low, close, volume]
    Prices start at $50,000 and increase by ~$10 per candle.
    """
    return [
        [1000000 + i*3600, 50000+i*10, 50100+i*10, 49900+i*10, 50050+i*10, 1000+i*10]
        for i in range(50)
    ]


@pytest.fixture
def sample_market_data() -> Dict[str, Any]:
    """
    Complete market data snapshot for strategy testing.
    
    Represents a typical BTC/USDT market state with all indicators populated.
    """
    return {
        'symbol': 'BTC/USDT',
        'current_price': 50000.0,
        'rsi': 58.3,
        'ma_20': 49500.0,
        'ma_50': 48800.0,
        'macd': 125.7,
        'atr': 500.0,
        'volume_24h': 1000000,
        'bb_upper': 51000.0,
        'bb_middle': 50000.0,
        'bb_lower': 49000.0,
        'regime': 'Normal'
    }


@pytest.fixture
def volatile_ohlcv_data() -> List[List[float]]:
    """
    Return OHLCV data with high volatility (large price swings).
    
    Useful for testing ATR calculations and volatility-sensitive strategies.
    """
    ohlcv = []
    base_price = 50000
    for i in range(30):
        # Alternate between large up and down moves
        if i % 2 == 0:
            high = base_price + 500
            low = base_price - 200
            close = base_price + 300
        else:
            high = base_price + 200
            low = base_price - 500
            close = base_price - 300
        
        ohlcv.append([
            1000000 + i*3600,
            base_price,
            high,
            low,
            close,
            2000  # High volume
        ])
        base_price = close
    
    return ohlcv


@pytest.fixture
def calm_ohlcv_data() -> List[List[float]]:
    """
    Return OHLCV data with low volatility (small price movements).
    
    Useful for testing ATR calculations in quiet market conditions.
    """
    ohlcv = []
    base_price = 50000
    for i in range(30):
        # Small random-like movements
        high = base_price + 50
        low = base_price - 50
        close = base_price + (i % 3 - 1) * 20  # Oscillate slightly
        
        ohlcv.append([
            1000000 + i*3600,
            base_price,
            high,
            low,
            close,
            500  # Low volume
        ])
        base_price = close
    
    return ohlcv


@pytest.fixture
def bullish_breakout_ohlcv() -> List[List[float]]:
    """
    Create OHLCV data showing a clear bullish breakout pattern.
    
    First 20 candles: consolidation around $50,000
    Last 5 candles: breakout above $50,200 resistance with volume spike
    """
    ohlcv = []
    base_price = 50000
    
    # Consolidation phase (20 candles)
    for i in range(20):
        ohlcv.append([
            i,
            base_price,
            base_price + 100,  # Resistance at 50100
            base_price - 100,  # Support at 49900
            base_price + 50,
            1000  # Normal volume
        ])
    
    # Breakout phase (5 candles with increasing volume)
    for i in range(20, 25):
        breakout_strength = (i - 20 + 1) * 50
        ohlcv.append([
            i,
            base_price + 50,
            base_price + 200 + breakout_strength,
            base_price + 50,
            base_price + 150 + breakout_strength,
            5000 + (i - 20) * 2000  # Volume spike
        ])
    
    return ohlcv


@pytest.fixture
def bearish_breakout_ohlcv() -> List[List[float]]:
    """
    Create OHLCV data showing a clear bearish breakout pattern.
    
    First 20 candles: consolidation around $50,000
    Last 5 candles: breakdown below $49,800 support with volume spike
    """
    ohlcv = []
    base_price = 50000
    
    # Consolidation phase (20 candles)
    for i in range(20):
        ohlcv.append([
            i,
            base_price,
            base_price + 100,
            base_price - 100,  # Support at 49900
            base_price - 50,
            1000
        ])
    
    # Breakdown phase (5 candles)
    for i in range(20, 25):
        breakdown_strength = (i - 20 + 1) * 50
        ohlcv.append([
            i,
            base_price - 50,
            base_price - 50,
            base_price - 200 - breakdown_strength,
            base_price - 150 - breakdown_strength,
            5000 + (i - 20) * 2000
        ])
    
    return ohlcv


def assert_approx_equal(actual: float, expected: float, tolerance: float = 0.01):
    """
    Assert two floats are approximately equal within tolerance.
    
    Args:
        actual: Actual value from calculation
        expected: Expected value
        tolerance: Maximum allowed difference (default 0.01)
    
    Raises:
        AssertionError if values differ by more than tolerance
    """
    assert abs(actual - expected) <= tolerance, \
        f"Expected {expected}, got {actual} (difference: {abs(actual - expected)}, tolerance: {tolerance})"


def create_volatile_ohlcv(gap: float = 50, num_candles: int = 30) -> List[List[float]]:
    """
    Helper function to create volatile OHLCV data programmatically.
    
    Args:
        gap: Price gap between high/low and open/close
        num_candles: Number of candles to generate
    
    Returns:
        List of OHLCV candles
    """
    ohlcv = []
    base_price = 50000
    for i in range(num_candles):
        direction = 1 if i % 2 == 0 else -1
        high = base_price + abs(gap * direction)
        low = base_price - abs(gap * direction)
        close = base_price + gap * direction
        
        ohlcv.append([
            1000000 + i*3600,
            base_price,
            high,
            low,
            close,
            2000
        ])
        base_price = close
    
    return ohlcv


def create_calm_ohlcv(gap: float = 5, num_candles: int = 30) -> List[List[float]]:
    """
    Helper function to create calm OHLCV data programmatically.
    
    Args:
        gap: Small price gap between high/low and open/close
        num_candles: Number of candles to generate
    
    Returns:
        List of OHLCV candles
    """
    ohlcv = []
    base_price = 50000
    for i in range(num_candles):
        high = base_price + gap
        low = base_price - gap
        close = base_price + (i % 3 - 1) * (gap / 2)
        
        ohlcv.append([
            1000000 + i*3600,
            base_price,
            high,
            low,
            close,
            500
        ])
        base_price = close
    
    return ohlcv
