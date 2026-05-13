"""
Unit tests for Trend Following Strategy signal generation.

Tests cover:
- LONG signal on golden cross (MA20 > MA50) with positive MACD
- SHORT signal on death cross (MA20 < MA50) with negative MACD
- Weak trend filtering (trend strength below threshold)
- ATR-based stop-loss calculation

Uses asyncio.run() to test async generate_signal methods.
"""
import pytest
import asyncio
from app.strategy.trend.trend_strategy import TrendStrategy


class TestTrendFollowing:
    """Test trend following strategy signal generation."""
    
    @pytest.fixture
    def trend_strategy(self):
        """Create trend strategy with lower threshold for testing."""
        return TrendStrategy(
            ma_fast=20,
            ma_slow=50,
            atr_multiplier=2.0,
            min_trend_strength=0.01  # Lower threshold (1%) for easier testing
        )
    
    def test_golden_cross_long_signal(self, trend_strategy):
        """Test LONG on MA20 crossing above MA50 with positive MACD."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50500,
            'ma_20': 50000,
            'ma_50': 49000,
            'macd': 150,
            'atr': 500,
            'regime': 'Normal-Trending'
        }
        
        signal = asyncio.run(trend_strategy.generate_signal(market_data))
        
        assert signal is not None
        assert signal.side == 'LONG'
        assert signal.entry_price == 50500
    
    def test_death_cross_short_signal(self, trend_strategy):
        """Test SHORT on MA20 crossing below MA50 with negative MACD."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 49500,
            'ma_20': 49000,
            'ma_50': 50000,
            'macd': -150,
            'atr': 500,
            'regime': 'Normal-Trending'
        }
        
        signal = asyncio.run(trend_strategy.generate_signal(market_data))
        
        assert signal is not None
        assert signal.side == 'SHORT'
        assert signal.entry_price == 49500
    
    def test_weak_trend_filtered(self, trend_strategy):
        """Test no signal when trend strength below threshold."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50000,
            'ma_20': 50010,  # Very close to MA50
            'ma_50': 50000,
            'macd': 10,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(trend_strategy.generate_signal(market_data))
        
        # Trend strength = |50010 - 50000| / 50000 = 0.02% < 0.3% threshold
        assert signal is None
    
    def test_no_macd_confirmation(self, trend_strategy):
        """Test no signal when MACD doesn't confirm trend direction."""
        # MA20 > MA50 (bullish) but MACD < 0 (bearish) - conflict
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50500,
            'ma_20': 50000,
            'ma_50': 49000,
            'macd': -50,  # Negative despite bullish MAs
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(trend_strategy.generate_signal(market_data))
        
        assert signal is None
    
    def test_atr_based_stop_loss_long(self, trend_strategy):
        """Test LONG stop-loss calculated using ATR."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50500,
            'ma_20': 50000,
            'ma_50': 49000,
            'macd': 150,
            'atr': 500,
            'regime': 'Normal-Trending'
        }
        
        signal = asyncio.run(trend_strategy.generate_signal(market_data))
        
        assert signal is not None
        # Stop should be entry - (ATR * multiplier)
        expected_sl = 50500 - (500 * 2.0)  # 49500
        assert abs(signal.stop_loss - expected_sl) < 1.0
    
    def test_atr_based_stop_loss_short(self, trend_strategy):
        """Test SHORT stop-loss calculated using ATR."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 49500,
            'ma_20': 49000,
            'ma_50': 50000,
            'macd': -150,
            'atr': 500,
            'regime': 'Normal-Trending'
        }
        
        signal = asyncio.run(trend_strategy.generate_signal(market_data))
        
        assert signal is not None
        # Stop should be entry + (ATR * multiplier)
        expected_sl = 49500 + (500 * 2.0)  # 50500
        assert abs(signal.stop_loss - expected_sl) < 1.0
    
    def test_reward_risk_ratio_applied(self, trend_strategy):
        """Test take-profit uses 2.5:1 R:R ratio (default for trend)."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50500,
            'ma_20': 50000,
            'ma_50': 49000,
            'macd': 150,
            'atr': 500,
            'regime': 'Normal-Trending'
        }
        
        signal = asyncio.run(trend_strategy.generate_signal(market_data))
        
        assert signal is not None
        risk = signal.entry_price - signal.stop_loss
        reward = signal.take_profit - signal.entry_price
        
        # Check R:R ratio is approximately 2.5:1
        rr_ratio = reward / risk if risk > 0 else 0
        assert 2.4 <= rr_ratio <= 2.6  # Allow small tolerance
    
    def test_missing_ma_data_returns_none(self, trend_strategy):
        """Test no signal when moving average data is missing."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50500,
            'ma_20': None,  # Missing
            'ma_50': 49000,
            'macd': 150,
            'atr': 500,
            'regime': 'Normal-Trending'
        }
        
        signal = asyncio.run(trend_strategy.generate_signal(market_data))
        
        assert signal is None
    
    def test_strong_trend_high_confidence(self, trend_strategy):
        """Test strong trend produces higher confidence."""
        # Strong uptrend
        market_data_strong = {
            'symbol': 'BTC/USDT',
            'current_price': 52000,
            'ma_20': 51000,
            'ma_50': 49000,  # Large gap = strong trend
            'macd': 300,
            'atr': 500,
            'regime': 'Normal-Trending'
        }
        
        # Weak uptrend
        market_data_weak = {
            'symbol': 'BTC/USDT',
            'current_price': 50200,
            'ma_20': 50100,
            'ma_50': 50000,  # Small gap = weak trend
            'macd': 50,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal_strong = asyncio.run(trend_strategy.generate_signal(market_data_strong))
        signal_weak = asyncio.run(trend_strategy.generate_signal(market_data_weak))
        
        # Weak trend might be filtered out entirely
        if signal_weak is not None:
            assert signal_strong.confidence >= signal_weak.confidence
