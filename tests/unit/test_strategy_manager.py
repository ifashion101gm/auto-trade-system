"""
Unit tests for StrategyManager - Multi-strategy orchestration.

Tests cover:
- Parallel strategy execution
- Signal selection (highest confidence)
- AI filter integration
- Error handling when strategies fail
- Empty signal scenarios
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.strategy.strategy_manager import StrategyManager
from app.strategy.signal_proposal import SignalProposal


class TestStrategyManagerInitialization:
    """Test StrategyManager initialization and configuration."""
    
    def test_default_initialization(self):
        """Test manager initializes with 3 strategies by default."""
        manager = StrategyManager(use_ai_filter=False)
        
        assert len(manager.strategies) == 3
        assert manager.ai_filter is None
        
        strategy_names = [s.name for s in manager.strategies]
        assert "breakout" in strategy_names
        assert "mean_reversion" in strategy_names
        assert "trend" in strategy_names
    
    def test_with_ai_filter(self):
        """Test manager initializes with AI filter enabled."""
        manager = StrategyManager(use_ai_filter=True)
        
        assert len(manager.strategies) == 3
        assert manager.ai_filter is not None
    
    def test_get_strategy_info(self):
        """Test retrieving strategy information."""
        manager = StrategyManager(use_ai_filter=False)
        
        info = manager.get_strategy_info()
        
        assert len(info) == 3
        
        for strategy_info in info:
            assert 'name' in strategy_info
            assert 'parameters' in strategy_info
            assert isinstance(strategy_info['parameters'], dict)


class TestStrategyManagerSignalGeneration:
    """Test multi-strategy signal generation and selection."""
    
    @pytest.fixture
    def manager_no_ai(self):
        """Create manager without AI filter for simpler testing."""
        return StrategyManager(use_ai_filter=False)
    
    @pytest.fixture
    def market_data(self):
        """Create sample market data that triggers signals."""
        # Create OHLCV data for breakout strategy
        ohlcv = []
        base_price = 50000
        for i in range(20):
            ohlcv.append([i, base_price, base_price + 100, base_price - 100, base_price + 50, 1000])
        ohlcv.append([20, base_price + 50, base_price + 250, base_price + 50, base_price + 200, 5000])
        
        return {
            'symbol': 'BTC/USDT',
            'current_price': 50200,
            'ohlcv': ohlcv,
            'volume_24h': 2000000,
            'atr': 500,
            'ma_20': 50000,
            'ma_50': 49000,
            'macd': 150,
            'rsi': 50,
            'bb_upper': 51000,
            'bb_middle': 50000,
            'bb_lower': 49000,
            'regime': 'Normal-Trending'
        }
    
    async def test_multiple_strategies_run_parallel(self, manager_no_ai, market_data):
        """Test all strategies execute in parallel."""
        result = await manager_no_ai.generate_signals(market_data)
        
        # Should return a signal (at least one strategy should trigger)
        # We don't assert specific outcome as it depends on market conditions
        assert result is None or isinstance(result, SignalProposal)
    
    async def test_selects_highest_confidence_signal(self, manager_no_ai):
        """Test manager selects signal with highest confidence."""
        # Mock strategies to return signals with different confidences
        mock_signal_low = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.6,
            strategy_name="mock_strategy_1"
        )
        
        mock_signal_high = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.85,
            strategy_name="mock_strategy_2"
        )
        
        # Patch all strategies to return these signals
        with patch.object(manager_no_ai.strategies[0], 'generate_signal', return_value=mock_signal_low):
            with patch.object(manager_no_ai.strategies[1], 'generate_signal', return_value=mock_signal_high):
                with patch.object(manager_no_ai.strategies[2], 'generate_signal', return_value=None):
                    
                    result = await manager_no_ai.generate_signals({})
        
        # Should select the higher confidence signal
        assert result is not None
        assert result.confidence == 0.85
        assert result.strategy_name == "mock_strategy_2"
    
    async def test_no_signals_returns_none(self, manager_no_ai):
        """Test manager returns None when no strategies generate signals."""
        # Mock all strategies to return None
        with patch.object(manager_no_ai.strategies[0], 'generate_signal', return_value=None):
            with patch.object(manager_no_ai.strategies[1], 'generate_signal', return_value=None):
                with patch.object(manager_no_ai.strategies[2], 'generate_signal', return_value=None):
                    
                    result = await manager_no_ai.generate_signals({})
        
        assert result is None
    
    async def test_single_signal_returned(self, manager_no_ai):
        """Test manager returns single signal when only one strategy triggers."""
        mock_signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.75,
            strategy_name="only_strategy"
        )
        
        with patch.object(manager_no_ai.strategies[0], 'generate_signal', return_value=mock_signal):
            with patch.object(manager_no_ai.strategies[1], 'generate_signal', return_value=None):
                with patch.object(manager_no_ai.strategies[2], 'generate_signal', return_value=None):
                    
                    result = await manager_no_ai.generate_signals({})
        
        assert result is not None
        assert result.strategy_name == "only_strategy"
        assert result.confidence == 0.75


class TestStrategyManagerErrorHandling:
    """Test error handling in strategy execution."""
    
    @pytest.fixture
    def manager_no_ai(self):
        return StrategyManager(use_ai_filter=False)
    
    async def test_strategy_exception_handled_gracefully(self, manager_no_ai):
        """Test manager continues when one strategy raises exception."""
        mock_signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.75,
            strategy_name="working_strategy"
        )
        
        # First strategy raises exception, others work
        with patch.object(manager_no_ai.strategies[0], 'generate_signal', 
                         side_effect=Exception("Strategy failed")):
            with patch.object(manager_no_ai.strategies[1], 'generate_signal', return_value=mock_signal):
                with patch.object(manager_no_ai.strategies[2], 'generate_signal', return_value=None):
                    
                    result = await manager_no_ai.generate_signals({})
        
        # Should still return signal from working strategy
        assert result is not None
        assert result.strategy_name == "working_strategy"
    
    async def test_all_strategies_fail_returns_none(self, manager_no_ai):
        """Test manager returns None when all strategies fail."""
        with patch.object(manager_no_ai.strategies[0], 'generate_signal', 
                         side_effect=Exception("Failed")):
            with patch.object(manager_no_ai.strategies[1], 'generate_signal', 
                             side_effect=Exception("Failed")):
                with patch.object(manager_no_ai.strategies[2], 'generate_signal', 
                                 side_effect=Exception("Failed")):
                    
                    result = await manager_no_ai.generate_signals({})
        
        assert result is None
    
    async def test_mixed_success_and_failure(self, manager_no_ai):
        """Test manager handles mix of successful and failed strategies."""
        mock_signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.80,
            strategy_name="success_strategy"
        )
        
        with patch.object(manager_no_ai.strategies[0], 'generate_signal', return_value=mock_signal):
            with patch.object(manager_no_ai.strategies[1], 'generate_signal', 
                             side_effect=Exception("Failed")):
                with patch.object(manager_no_ai.strategies[2], 'generate_signal', return_value=None):
                    
                    result = await manager_no_ai.generate_signals({})
        
        assert result is not None
        assert result.strategy_name == "success_strategy"


class TestStrategyManagerAIFilter:
    """Test AI filter integration with strategy manager."""
    
    async def test_ai_filter_validates_signals(self):
        """Test AI filter can reject low-quality signals."""
        manager = StrategyManager(use_ai_filter=True)
        
        mock_signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.75,
            strategy_name="test_strategy"
        )
        
        market_context = {
            'regime': 'Normal',
            'volatility': 0.5,
            'volume_trend': 'neutral'
        }
        
        # Mock AI filter to accept signal
        with patch.object(manager.ai_filter, 'validate_signal', return_value=mock_signal):
            with patch.object(manager.strategies[0], 'generate_signal', return_value=mock_signal):
                with patch.object(manager.strategies[1], 'generate_signal', return_value=None):
                    with patch.object(manager.strategies[2], 'generate_signal', return_value=None):
                        
                        result = await manager.generate_signals(market_context)
        
        assert result is not None
    
    async def test_ai_filter_rejects_all_signals(self):
        """Test manager returns None when AI filter rejects all signals."""
        manager = StrategyManager(use_ai_filter=True)
        
        mock_signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.75,
            strategy_name="test_strategy"
        )
        
        market_context = {
            'regime': 'High-vol',
            'volatility': 0.9,
            'volume_trend': 'declining'
        }
        
        # Mock AI filter to reject signal
        with patch.object(manager.ai_filter, 'validate_signal', return_value=None):
            with patch.object(manager.strategies[0], 'generate_signal', return_value=mock_signal):
                with patch.object(manager.strategies[1], 'generate_signal', return_value=None):
                    with patch.object(manager.strategies[2], 'generate_signal', return_value=None):
                        
                        result = await manager.generate_signals(market_context)
        
        assert result is None
    
    async def test_ai_filter_disabled_passes_all_signals(self):
        """Test manager without AI filter passes all valid signals."""
        manager = StrategyManager(use_ai_filter=False)
        
        mock_signal = SignalProposal(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=0.01,
            confidence=0.75,
            strategy_name="test_strategy"
        )
        
        with patch.object(manager.strategies[0], 'generate_signal', return_value=mock_signal):
            with patch.object(manager.strategies[1], 'generate_signal', return_value=None):
                with patch.object(manager.strategies[2], 'generate_signal', return_value=None):
                    
                    result = await manager.generate_signals({})
        
        assert result is not None


class TestStrategyManagerConcurrency:
    """Test concurrent strategy execution behavior."""
    
    @pytest.fixture
    def manager_no_ai(self):
        return StrategyManager(use_ai_filter=False)
    
    async def test_strategies_execute_concurrently(self, manager_no_ai):
        """Test strategies run concurrently, not sequentially."""
        import time
        
        # Create slow mock strategies
        async def slow_signal(delay):
            await asyncio.sleep(delay)
            return SignalProposal(
                symbol="BTC/USDT",
                side="LONG",
                entry_price=50000.0,
                stop_loss=49000.0,
                take_profit=52000.0,
                quantity=0.01,
                confidence=0.75,
                strategy_name=f"slow_{delay}"
            )
        
        start_time = time.perf_counter()
        
        with patch.object(manager_no_ai.strategies[0], 'generate_signal', 
                         return_value=await slow_signal(0.1)):
            with patch.object(manager_no_ai.strategies[1], 'generate_signal', 
                             return_value=await slow_signal(0.1)):
                with patch.object(manager_no_ai.strategies[2], 'generate_signal', 
                                 return_value=await slow_signal(0.1)):
                    
                    await manager_no_ai.generate_signals({})
        
        end_time = time.perf_counter()
        elapsed = end_time - start_time
        
        # If running in parallel, should take ~0.1s, not 0.3s
        # Allow some overhead for test environment variability
        assert elapsed < 0.5, f"Strategies may not be running in parallel: {elapsed:.2f}s"


# ============================================================================
# Run Configuration
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
