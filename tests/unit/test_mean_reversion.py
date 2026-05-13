"""
Unit tests for Mean Reversion Strategy signal generation.

Tests cover:
- LONG signal when RSI < 30 and price at lower Bollinger Band
- SHORT signal when RSI > 70 and price at upper Bollinger Band
- No signal in neutral zone (RSI 30-70)
- Stop-loss and take-profit calculations

Uses asyncio.run() to test async generate_signal methods.
"""
import pytest
import asyncio
from app.strategy.mean_reversion.mean_reversion_strategy import MeanReversionStrategy


class TestMeanReversionSignals:
    """Test mean reversion strategy signal generation."""
    
    @pytest.fixture
    def mean_reversion_strategy(self):
        """Create mean reversion strategy with standard parameters."""
        return MeanReversionStrategy(
            rsi_period=14,
            rsi_oversold=30,
            rsi_overbought=70,
            bb_period=20,
            bb_std_dev=2.0
        )
    
    def test_oversold_long_signal(self, mean_reversion_strategy):
        """Test LONG signal when RSI < 30 and price at lower BB."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 49000,
            'rsi': 25,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Low-vol'
        }
        
        signal = asyncio.run(mean_reversion_strategy.generate_signal(market_data))
        
        assert signal is not None
        assert signal.side == 'LONG'
        assert signal.entry_price == 49000
        assert signal.take_profit == 50000  # Target middle band
    
    def test_overbought_short_signal(self, mean_reversion_strategy):
        """Test SHORT signal when RSI > 70 and price at upper BB."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 51000,
            'rsi': 75,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Low-vol'
        }
        
        signal = asyncio.run(mean_reversion_strategy.generate_signal(market_data))
        
        assert signal is not None
        assert signal.side == 'SHORT'
        assert signal.entry_price == 51000
        assert signal.take_profit == 50000  # Target middle band
    
    def test_no_signal_in_neutral_zone(self, mean_reversion_strategy):
        """Test no signal when RSI between 30-70."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50000,
            'rsi': 50,  # Neutral
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(mean_reversion_strategy.generate_signal(market_data))
        
        assert signal is None
    
    def test_no_signal_rsi_oversold_but_not_at_bb(self, mean_reversion_strategy):
        """Test no signal when RSI oversold but price not at lower BB."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50500,  # Above lower BB
            'rsi': 25,  # Oversold
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Low-vol'
        }
        
        signal = asyncio.run(mean_reversion_strategy.generate_signal(market_data))
        
        assert signal is None
    
    def test_no_signal_rsi_overbought_but_not_at_bb(self, mean_reversion_strategy):
        """Test no signal when RSI overbought but price not at upper BB."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50500,  # Below upper BB
            'rsi': 75,  # Overbought
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Low-vol'
        }
        
        signal = asyncio.run(mean_reversion_strategy.generate_signal(market_data))
        
        assert signal is None
    
    def test_stop_loss_below_lower_band_long(self, mean_reversion_strategy):
        """Test LONG stop-loss placed below lower Bollinger Band."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 49000,
            'rsi': 25,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Low-vol'
        }
        
        signal = asyncio.run(mean_reversion_strategy.generate_signal(market_data))
        
        assert signal is not None
        assert signal.stop_loss < 49000  # Below entry
        assert signal.stop_loss < 48900  # Below lower band * 0.99
    
    def test_stop_loss_above_upper_band_short(self, mean_reversion_strategy):
        """Test SHORT stop-loss placed above upper Bollinger Band."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 51000,
            'rsi': 75,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Low-vol'
        }
        
        signal = asyncio.run(mean_reversion_strategy.generate_signal(market_data))
        
        assert signal is not None
        assert signal.stop_loss > 51000  # Above entry
        assert signal.stop_loss > 51100  # Above upper band * 1.01
    
    def test_missing_bb_data_returns_none(self, mean_reversion_strategy):
        """Test no signal when Bollinger Bands data is missing."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50000,
            'rsi': 25,
            # Missing bb_upper, bb_middle, bb_lower
            'regime': 'Low-vol'
        }
        
        signal = asyncio.run(mean_reversion_strategy.generate_signal(market_data))
        
        assert signal is None
    
    def test_confidence_increases_with_extreme_rsi(self, mean_reversion_strategy):
        """Test confidence increases as RSI moves further from threshold."""
        # Moderately oversold
        market_data_mild = {
            'symbol': 'BTC/USDT',
            'current_price': 49000,
            'rsi': 28,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Low-vol'
        }
        
        # Extremely oversold
        market_data_extreme = {
            'symbol': 'BTC/USDT',
            'current_price': 49000,
            'rsi': 15,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Low-vol'
        }
        
        signal_mild = asyncio.run(mean_reversion_strategy.generate_signal(market_data_mild))
        signal_extreme = asyncio.run(mean_reversion_strategy.generate_signal(market_data_extreme))
        
        assert signal_mild is not None
        assert signal_extreme is not None
        assert signal_extreme.confidence > signal_mild.confidence
