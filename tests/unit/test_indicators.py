"""
Unit tests for technical indicator calculations.

Tests cover:
- ATR (Average True Range) calculation
- RSI (Relative Strength Index) calculation
- SMA (Simple Moving Average) calculation
- EMA (Exponential Moving Average) calculation
- Bollinger Bands calculation

All tests use deterministic, static data with known expected outputs.
No external dependencies or network calls.
"""
import pytest
from app.strategy.indicators import (
    calculate_true_range,
    calculate_atr,
    calculate_rsi,
    calculate_sma,
    calculate_ema,
    calculate_bollinger_bands
)
from tests.conftest import assert_approx_equal


class TestTrueRange:
    """Test True Range calculation for single periods."""
    
    def test_true_range_basic(self):
        """Test basic true range calculation."""
        # High-Low is largest
        tr = calculate_true_range(high=105, low=95, prev_close=100)
        assert tr == 10  # 105 - 95
    
    def test_true_range_high_prev_close(self):
        """Test true range when |high - prev_close| is largest."""
        tr = calculate_true_range(high=110, low=100, prev_close=95)
        assert tr == 15  # |110 - 95|
    
    def test_true_range_low_prev_close(self):
        """Test true range when |low - prev_close| is largest."""
        tr = calculate_true_range(high=100, low=90, prev_close=105)
        assert tr == 15  # |90 - 105|
    
    def test_true_range_zero_movement(self):
        """Test true range with no price movement."""
        tr = calculate_true_range(high=100, low=100, prev_close=100)
        assert tr == 0.0


class TestATRCalculation:
    """Test Average True Range calculation."""
    
    def test_atr_basic_calculation(self):
        """Test ATR with simple price movements."""
        ohlcv = [
            [1, 100, 105, 95, 100, 1000],
            [2, 100, 110, 98, 105, 1200],
            [3, 105, 108, 102, 103, 1100],
            [4, 103, 107, 100, 106, 1300],
            [5, 106, 112, 104, 110, 1400],
        ]
        atr = calculate_atr(ohlcv, period=3)
        assert atr > 0
        assert isinstance(atr, float)
    
    def test_atr_high_volatility(self):
        """Test ATR increases with volatility."""
        volatile_ohlcv = [
            [i, 50000, 50500, 49500, 50000 + (i % 2 * 500), 2000]
            for i in range(20)
        ]
        calm_ohlcv = [
            [i, 50000, 50050, 49950, 50000 + (i % 3 * 20), 500]
            for i in range(20)
        ]
        
        atr_volatile = calculate_atr(volatile_ohlcv, period=14)
        atr_calm = calculate_atr(calm_ohlcv, period=14)
        
        assert atr_volatile > atr_calm
    
    def test_atr_insufficient_data_raises_error(self):
        """Test ATR raises error with insufficient data."""
        ohlcv = [[1, 100, 105, 95, 100, 1000]]  # Only 1 candle
        with pytest.raises(ValueError, match="Need at least"):
            calculate_atr(ohlcv, period=14)
    
    def test_atr_constant_prices(self):
        """Test ATR with no price movement."""
        ohlcv = [[i, 100, 100, 100, 100, 1000] for i in range(20)]
        atr = calculate_atr(ohlcv, period=14)
        assert atr == 0.0
    
    def test_atr_different_periods(self):
        """Test ATR with different period values."""
        ohlcv = [
            [i, 50000 + i*10, 50100 + i*10, 49900 + i*10, 50050 + i*10, 1000]
            for i in range(30)
        ]
        
        atr_short = calculate_atr(ohlcv, period=7)
        atr_long = calculate_atr(ohlcv, period=14)
        
        # Both should be positive and reasonable
        assert atr_short > 0
        assert atr_long > 0


class TestRSICalculation:
    """Test Relative Strength Index calculation."""
    
    def test_rsi_oversold(self):
        """Test RSI in oversold territory (<30)."""
        # Declining prices
        closes = [100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 80, 78, 76, 74, 72]
        rsi = calculate_rsi(closes, period=14)
        assert rsi < 30
    
    def test_rsi_overbought(self):
        """Test RSI in overbought territory (>70)."""
        # Rising prices
        closes = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122, 124, 126, 128]
        rsi = calculate_rsi(closes, period=14)
        assert rsi > 70
    
    def test_rsi_neutral(self):
        """Test RSI near 50 with sideways movement."""
        closes = [100, 101, 99, 100, 101, 99, 100, 101, 99, 100, 101, 99, 100, 101, 100]
        rsi = calculate_rsi(closes, period=14)
        assert 40 <= rsi <= 60
    
    def test_rsi_all_gains(self):
        """Test RSI = 100 when all price changes are gains."""
        closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
        rsi = calculate_rsi(closes, period=14)
        assert rsi == 100.0
    
    def test_rsi_insufficient_data_raises_error(self):
        """Test RSI raises error with insufficient data."""
        closes = [100, 101, 102]  # Only 3 prices
        with pytest.raises(ValueError, match="Need at least"):
            calculate_rsi(closes, period=14)
    
    def test_rsi_range_bounds(self):
        """Test RSI always returns value between 0 and 100."""
        # Test with various price patterns
        test_cases = [
            [100 + i for i in range(20)],  # Steady increase
            [100 - i for i in range(20)],  # Steady decrease
            [100 + (i % 5) * 2 for i in range(20)],  # Oscillating
        ]
        
        for closes in test_cases:
            rsi = calculate_rsi(closes, period=14)
            assert 0 <= rsi <= 100


class TestMovingAverages:
    """Test Simple and Exponential Moving Average calculations."""
    
    def test_sma_basic(self):
        """Test basic SMA calculation."""
        prices = [10, 20, 30, 40, 50]
        sma = calculate_sma(prices, period=3)
        assert_approx_equal(sma, 40.0)  # (30+40+50)/3
    
    def test_sma_full_period(self):
        """Test SMA using all available data."""
        prices = [100, 200, 300, 400, 500]
        sma = calculate_sma(prices, period=5)
        assert_approx_equal(sma, 300.0)  # Average of all
    
    def test_sma_insufficient_data_raises(self):
        """Test SMA raises error with insufficient data."""
        prices = [10, 20, 30]
        with pytest.raises(ValueError, match="Need at least"):
            calculate_sma(prices, period=5)
    
    def test_ema_responsiveness(self):
        """EMA should react faster than SMA to recent changes."""
        prices = [100, 100, 100, 100, 100, 150]  # Sharp increase at end
        sma = calculate_sma(prices, period=5)
        ema = calculate_ema(prices, period=5)
        assert ema > sma  # EMA weights recent price more
    
    def test_ema_basic_calculation(self):
        """Test basic EMA calculation."""
        prices = [10, 20, 30, 40, 50, 60, 70]
        ema = calculate_ema(prices, period=5)
        assert ema > 0
        assert isinstance(ema, float)
    
    def test_ema_insufficient_data_raises(self):
        """Test EMA raises error with insufficient data."""
        prices = [10, 20, 30]
        with pytest.raises(ValueError, match="Need at least"):
            calculate_ema(prices, period=5)
    
    def test_ema_vs_sma_trending_market(self):
        """In uptrend, EMA should be above or equal to SMA."""
        prices = [100, 110, 120, 130, 140, 150, 160, 170, 180, 190]
        sma = calculate_sma(prices, period=5)
        ema = calculate_ema(prices, period=5)
        assert ema >= sma  # EMA weights recent prices more
    
    def test_ema_vs_sma_downtrending_market(self):
        """In downtrend, EMA should be below or equal to SMA."""
        prices = [190, 180, 170, 160, 150, 140, 130, 120, 110, 100]
        sma = calculate_sma(prices, period=5)
        ema = calculate_ema(prices, period=5)
        assert ema <= sma  # EMA weights recent (lower) prices more


class TestBollingerBands:
    """Test Bollinger Bands calculation."""
    
    def test_bollinger_bands_basic(self):
        """Test basic Bollinger Bands calculation."""
        prices = [100 + i*2 for i in range(25)]  # Uptrend
        upper, middle, lower = calculate_bollinger_bands(prices, period=20)
        
        assert upper > middle > lower
        assert isinstance(upper, float)
        assert isinstance(middle, float)
        assert isinstance(lower, float)
    
    def test_bollinger_bands_middle_is_sma(self):
        """Test that middle band equals SMA."""
        prices = [50, 55, 60, 65, 70, 75, 80, 85, 90, 95] * 3
        upper, middle, lower = calculate_bollinger_bands(prices, period=10)
        sma = calculate_sma(prices, period=10)
        
        assert_approx_equal(middle, sma)
    
    def test_bollinger_bands_width_with_volatility(self):
        """Test bands widen with increased volatility."""
        calm_prices = [100 + (i % 3) for i in range(25)]
        volatile_prices = [100 + (i % 3) * 10 for i in range(25)]
        
        _, _, lower_calm = calculate_bollinger_bands(calm_prices, period=20)
        upper_calm, _, _ = calculate_bollinger_bands(calm_prices, period=20)
        
        _, _, lower_volatile = calculate_bollinger_bands(volatile_prices, period=20)
        upper_volatile, _, _ = calculate_bollinger_bands(volatile_prices, period=20)
        
        band_width_calm = upper_calm - lower_calm
        band_width_volatile = upper_volatile - lower_volatile
        
        assert band_width_volatile > band_width_calm
    
    def test_bollinger_bands_insufficient_data_raises(self):
        """Test Bollinger Bands raises error with insufficient data."""
        prices = [100, 101, 102]
        with pytest.raises(ValueError, match="Need at least"):
            calculate_bollinger_bands(prices, period=20)
    
    def test_bollinger_bands_custom_std_dev(self):
        """Test Bollinger Bands with custom standard deviation multiplier."""
        prices = [100 + i for i in range(25)]
        
        upper_1, middle_1, lower_1 = calculate_bollinger_bands(prices, period=20, num_std_dev=1.0)
        upper_2, middle_2, lower_2 = calculate_bollinger_bands(prices, period=20, num_std_dev=2.0)
        
        # Higher std_dev should create wider bands
        assert (upper_2 - lower_2) > (upper_1 - lower_1)
        # Middle band should be the same
        assert_approx_equal(middle_1, middle_2)
