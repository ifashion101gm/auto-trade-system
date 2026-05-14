"""
Comprehensive unit tests for SignalProposal data structure.

Tests cover:
- SignalProposal creation with all fields
- Serialization (to_dict) and deserialization
- Default values and optional fields
- Validation of required fields
- Edge cases (None values, extreme prices)
"""
import pytest
from datetime import datetime
from app.strategy.signal_proposal import SignalProposal


class TestSignalProposalCreation:
    """Test SignalProposal instantiation and field validation."""
    
    def test_create_minimal_signal(self):
        """Test creating signal with only required fields."""
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01
        )
        
        assert signal.symbol == "BTC/USDT"
        assert signal.side == "LONG"
        assert signal.entry_price == 50000.0
        assert signal.stop_loss == 49000.0
        assert signal.take_profit == 52000.0
        assert signal.quantity == 0.01
        
        # Check defaults
        assert signal.leverage == 1
        assert signal.confidence == 0.5
        assert signal.strategy_name == "unknown"
        assert signal.regime == "Normal"
        assert signal.timestamp is None
        assert signal.indicators == {}
        assert signal.metadata == {}
    
    def test_create_full_signal(self):
        """Test creating signal with all fields populated."""
        now = datetime.utcnow()
        
        signal = SignalProposal(
            symbol="ETH/USDT",
            side="SHORT",
            entry_price=3000.0,
            stop_loss=3100.0,
            take_profit=2800.0,
            quantity=0.5,
            leverage=5,
            confidence=0.85,
            strategy_name="breakout",
            regime="High-vol",
            indicators={
                'rsi': 75,
                'volume_ratio': 2.5
            },
            timestamp=now,
            metadata={
                'lookback_period': 20,
                'breakout_type': 'bearish'
            }
        )
        
        assert signal.symbol == "ETH/USDT"
        assert signal.side == "SHORT"
        assert signal.leverage == 5
        assert signal.confidence == 0.85
        assert signal.strategy_name == "breakout"
        assert signal.regime == "High-vol"
        assert signal.indicators['rsi'] == 75
        assert signal.timestamp == now
        assert signal.metadata['lookback_period'] == 20
    
    def test_optional_stop_loss_none(self):
        """Test signal with no stop-loss (should be allowed)."""
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=None,
            take_profit=52000.0,
            quantity=0.01
        )
        
        assert signal.stop_loss is None
    
    def test_optional_take_profit_none(self):
        """Test signal with no take-profit (should be allowed)."""
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=None,
            quantity=0.01
        )
        
        assert signal.take_profit is None


class TestSignalProposalSerialization:
    """Test SignalProposal serialization to dictionary."""
    
    def test_to_dict_basic(self):
        """Test basic serialization."""
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01
        )
        
        result = signal.to_dict()
        
        assert isinstance(result, dict)
        assert result['symbol'] == "BTC/USDT"
        assert result['side'] == "LONG"
        assert result['entry_price'] == 50000.0
        assert result['stop_loss'] == 49000.0
        assert result['take_profit'] == 52000.0
        assert result['quantity'] == 0.01
        assert result['leverage'] == 1
        assert result['confidence'] == 0.5
        assert result['strategy_name'] == "unknown"
        assert result['regime'] == "Normal"
    
    def test_to_dict_with_timestamp(self):
        """Test serialization includes ISO format timestamp."""
        now = datetime.utcnow()
        
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            timestamp=now
        )
        
        result = signal.to_dict()
        
        assert result['timestamp'] == now.isoformat()
    
    def test_to_dict_without_timestamp(self):
        """Test serialization handles None timestamp."""
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            timestamp=None
        )
        
        result = signal.to_dict()
        
        assert result['timestamp'] is None
    
    def test_to_dict_preserves_indicators(self):
        """Test serialization preserves indicator dictionary."""
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            indicators={
                'ma_20': 50000,
                'ma_50': 49000,
                'macd': 150
            }
        )
        
        result = signal.to_dict()
        
        assert result['indicators']['ma_20'] == 50000
        assert result['indicators']['ma_50'] == 49000
        assert result['indicators']['macd'] == 150
    
    def test_to_dict_preserves_metadata(self):
        """Test serialization preserves metadata dictionary."""
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            metadata={
                'test_key': 'test_value',
                'nested': {'key': 'value'}
            }
        )
        
        result = signal.to_dict()
        
        assert result['metadata']['test_key'] == 'test_value'
        assert result['metadata']['nested']['key'] == 'value'


class TestSignalProposalValidation:
    """Test SignalProposal field validation and edge cases."""
    
    def test_valid_sides(self):
        """Test both LONG and SHORT sides are valid."""
        long_signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01
        )
        
        short_signal = SignalProposal(
            symbol="BTC/USDT",
            side="SHORT",
            entry_price=50000.0,
            stop_loss=51000.0,
            take_profit=48000.0,
            quantity=0.01
        )
        
        assert long_signal.side == "LONG"
        assert short_signal.side == "SHORT"
    
    def test_confidence_range(self):
        """Test confidence accepts values in [0.0, 1.0] range."""
        low_confidence = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.1
        )
        
        high_confidence = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.95
        )
        
        assert low_confidence.confidence == 0.1
        assert high_confidence.confidence == 0.95
    
    def test_leverage_values(self):
        """Test various leverage values."""
        no_leverage = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            leverage=1
        )
        
        high_leverage = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            leverage=20
        )
        
        assert no_leverage.leverage == 1
        assert high_leverage.leverage == 20
    
    def test_extreme_prices(self):
        """Test signal with very small and very large prices."""
        small_price = SignalProposal(
            symbol="DOGE/USDT",
            side="LONG",
            entry_price=0.08,
            stop_loss=0.075,
            take_profit=0.09,
            quantity=10000
        )
        
        large_price = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=100000.0,
            stop_loss=95000.0,
            take_profit=110000.0,
            quantity=0.001
        )
        
        assert small_price.entry_price == 0.08
        assert large_price.entry_price == 100000.0
    
    def test_various_symbols(self):
        """Test different trading pair formats."""
        symbols = ["BTC/USDT", "ETH/USDT", "XAUUSD", "EURUSD", "BTC-USDT"]
        
        for symbol in symbols:
            signal = SignalProposal(
                symbol=symbol,
                side="LONG",
                entry_price=50000.0,
                stop_loss=49000.0,
                take_profit=52000.0,
                quantity=0.01
            )
            
            assert signal.symbol == symbol


class TestSignalProposalImmutability:
    """Test that SignalProposal fields behave as expected after creation."""
    
    def test_fields_accessible_after_creation(self):
        """Test all fields remain accessible after creation."""
        signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            leverage=5,
            confidence=0.85,
            strategy_name="trend",
            regime="Normal-Trending"
        )
        
        # All fields should be readable
        _ = signal.symbol
        _ = signal.side
        _ = signal.entry_price
        _ = signal.stop_loss
        _ = signal.take_profit
        _ = signal.quantity
        _ = signal.leverage
        _ = signal.confidence
        _ = signal.strategy_name
        _ = signal.regime
        _ = signal.indicators
        _ = signal.timestamp
        _ = signal.metadata
        
        assert True  # If we got here, all fields are accessible
    
    def test_dataclass_equality(self):
        """Test two signals with same values are equal."""
        signal1 = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01
        )
        
        signal2 = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01
        )
        
        # Dataclasses compare by value
        assert signal1 == signal2


# ============================================================================
# Run Configuration
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
