"""
Unit tests for Breakout Strategy signal generation.

Tests cover:
- Bullish breakout detection above resistance
- Bearish breakout detection below support
- Volume confirmation requirements
- ATR-based stop-loss calculation
- No signal when price within range

Uses asyncio.run() to test async generate_signal methods.
"""
import pytest
import asyncio
from app.strategy.breakout.breakout_strategy import BreakoutStrategy


class TestBreakoutDetection:
    """Test breakout strategy signal generation."""
    
    @pytest.fixture
    def breakout_strategy(self):
        """Create breakout strategy with standard parameters."""
        return BreakoutStrategy(
            lookback_period=20,
            volume_multiplier=1.5,
            atr_multiplier=1.5,
            reward_risk_ratio=2.0
        )
    
    def test_bullish_breakout_detected(self, breakout_strategy):
        """Test bullish breakout above resistance with volume confirmation."""
        # Create OHLCV where current candle breaks above previous highs
        ohlcv = self._create_bullish_breakout_data()
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50200,  # Above resistance (50100)
            'ohlcv': ohlcv,
            'volume_24h': 2000000,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(breakout_strategy.generate_signal(market_data))
        
        assert signal is not None
        assert signal.side == 'LONG'
        assert signal.entry_price == 50200
        assert signal.stop_loss < 50200  # Below entry
        assert signal.take_profit > 50200  # Above entry
    
    def test_bearish_breakout_detected(self, breakout_strategy):
        """Test bearish breakout below support with volume confirmation."""
        ohlcv = self._create_bearish_breakout_data()
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 49800,  # Below support (49900)
            'ohlcv': ohlcv,
            'volume_24h': 2000000,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(breakout_strategy.generate_signal(market_data))
        
        assert signal is not None
        assert signal.side == 'SHORT'
        assert signal.entry_price == 49800
        assert signal.stop_loss > 49800  # Above entry
        assert signal.take_profit < 49800  # Below entry
    
    def test_no_breakout_no_signal(self, breakout_strategy):
        """Test no signal when price within consolidation range."""
        ohlcv = self._create_consolidation_data()
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50050,  # Within range [49900, 50100]
            'ohlcv': ohlcv,
            'volume_24h': 1000000,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(breakout_strategy.generate_signal(market_data))
        
        assert signal is None
    
    def test_volume_confirmation_required(self, breakout_strategy):
        """Test breakout rejected without volume confirmation."""
        ohlcv = self._create_bullish_breakout_low_volume()
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50200,  # Above resistance
            'ohlcv': ohlcv,
            'volume_24h': 1000000,  # Low volume
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(breakout_strategy.generate_signal(market_data))
        
        # Should be None due to insufficient volume
        assert signal is None
    
    def test_atr_based_stop_loss_long(self, breakout_strategy):
        """Test LONG stop-loss calculated using ATR."""
        ohlcv = self._create_bullish_breakout_data()
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50200,
            'ohlcv': ohlcv,
            'volume_24h': 2000000,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(breakout_strategy.generate_signal(market_data))
        
        assert signal is not None
        # Stop should be entry - (ATR * multiplier)
        expected_sl = 50200 - (500 * 1.5)  # 49450
        assert abs(signal.stop_loss - expected_sl) < 1.0  # Allow small rounding
    
    def test_atr_based_stop_loss_short(self, breakout_strategy):
        """Test SHORT stop-loss calculated using ATR."""
        ohlcv = self._create_bearish_breakout_data()
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 49800,
            'ohlcv': ohlcv,
            'volume_24h': 2000000,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(breakout_strategy.generate_signal(market_data))
        
        assert signal is not None
        # Stop should be entry + (ATR * multiplier)
        expected_sl = 49800 + (500 * 1.5)  # 50550
        assert abs(signal.stop_loss - expected_sl) < 1.0
    
    def test_reward_risk_ratio_applied(self, breakout_strategy):
        """Test take-profit uses configured R:R ratio."""
        ohlcv = self._create_bullish_breakout_data()
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50200,
            'ohlcv': ohlcv,
            'volume_24h': 2000000,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(breakout_strategy.generate_signal(market_data))
        
        assert signal is not None
        risk = signal.entry_price - signal.stop_loss
        reward = signal.take_profit - signal.entry_price
        
        # Check R:R ratio is approximately 2:1
        rr_ratio = reward / risk if risk > 0 else 0
        assert 1.9 <= rr_ratio <= 2.1  # Allow small tolerance
    
    def test_insufficient_data_returns_none(self, breakout_strategy):
        """Test strategy returns None with insufficient OHLCV data."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50000,
            'ohlcv': [[i, 50000, 50100, 49900, 50050, 1000] for i in range(5)],  # Only 5 candles
            'volume_24h': 1000000,
            'atr': 500,
            'regime': 'Normal'
        }
        
        signal = asyncio.run(breakout_strategy.generate_signal(market_data))
        
        assert signal is None
    
    def _create_bullish_breakout_data(self):
        """Helper to create OHLCV data with clear bullish breakout pattern."""
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
        
        # Breakout candle with high volume
        ohlcv.append([
            20,
            base_price + 50,
            base_price + 250,
            base_price + 50,
            base_price + 200,  # Close above resistance
            5000  # Volume spike (5x average)
        ])
        
        return ohlcv
    
    def _create_bearish_breakout_data(self):
        """Helper to create OHLCV data with clear bearish breakout pattern."""
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
        
        # Breakdown candle with high volume
        ohlcv.append([
            20,
            base_price - 50,
            base_price - 50,
            base_price - 250,
            base_price - 200,  # Close below support
            5000  # Volume spike
        ])
        
        return ohlcv
    
    def _create_consolidation_data(self):
        """Helper to create OHLCV data with price in range."""
        ohlcv = []
        base_price = 50000
        
        for i in range(25):
            ohlcv.append([
                i,
                base_price,
                base_price + 100,
                base_price - 100,
                base_price + (i % 3 - 1) * 50,  # Oscillate within range
                1000
            ])
        
        return ohlcv
    
    def _create_bullish_breakout_low_volume(self):
        """Helper to create breakout without volume confirmation."""
        ohlcv = []
        base_price = 50000
        
        # Consolidation phase
        for i in range(20):
            ohlcv.append([
                i,
                base_price,
                base_price + 100,
                base_price - 100,
                base_price + 50,
                1000
            ])
        
        # Breakout candle with LOW volume (no confirmation)
        ohlcv.append([
            20,
            base_price + 50,
            base_price + 250,
            base_price + 50,
            base_price + 200,
            1200  # Only 1.2x average, need 1.5x
        ])
        
        return ohlcv
