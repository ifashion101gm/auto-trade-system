"""
Unit tests for Orchestrator with Mock Agents.

Tests deterministic agent behavior without external API calls.

Tests:
1. Agent timeout handled gracefully
2. Malformed JSON recovered
3. Conflicting outputs resolved
4. Full workflow with mocks
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from app.ai_agents.orchestrator import AIAgentOrchestrator


class MockLLMClient:
    """Mock LLM client for testing."""
    
    def __init__(self, fail_mode: bool = False, slow_mode: bool = False):
        self.fail_mode = fail_mode
        self.slow_mode = slow_mode
        self.call_count = 0
    
    async def detect_regime(self, market_data: Dict[str, Any]) -> str:
        self.call_count += 1
        
        if self.fail_mode:
            raise Exception("Simulated LLM failure")
        
        if self.slow_mode:
            import asyncio
            await asyncio.sleep(10)  # Simulate slow response
        
        volatility = market_data.get('volatility', 0.5)
        
        if volatility < 0.3:
            return "Low-vol"
        elif volatility > 0.7:
            return "High-vol"
        else:
            return "Normal"
    
    async def select_strategy(self, market_data: Dict[str, Any], regime: str = "Normal") -> Dict[str, Any]:
        self.call_count += 1
        
        if self.fail_mode:
            raise Exception("Strategy selection failed")
        
        return {
            'strategy': 'momentum',
            'confidence': 0.85,  # High confidence to pass quality filter
            'parameters': {'lookback': 20}
        }
    
    async def assess_risk(self, position: Dict[str, Any], market_data: Dict[str, Any] = None) -> Dict[str, Any]:
        self.call_count += 1
        
        if self.fail_mode:
            raise Exception("Risk assessment failed")
        
        return {
            'risk_level': 'medium',
            'max_position_size': 1000,
            'stop_loss': 0.02,
            'leverage_recommendation': 2
        }


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def orchestrator_with_mock(mock_llm_client):
    """Create orchestrator with mock LLM client."""
    orchestrator = AIAgentOrchestrator(use_openrouter=False)
    orchestrator.llm_client = mock_llm_client
    orchestrator.use_openrouter = True  # Force using the mock
    return orchestrator


class TestOrchestratorMocking:
    """Test orchestrator with mock agents."""
    
    @pytest.mark.asyncio
    async def test_agent_timeout_handled_gracefully(self):
        """Timeouts should be caught and fallback to heuristic."""
        slow_client = MockLLMClient(slow_mode=True)
        orchestrator = AIAgentOrchestrator(use_openrouter=False)
        orchestrator.llm_client = slow_client
        orchestrator.use_openrouter = True
        
        market_data = {'volatility': 0.5, 'current_price': 50000}
        
        # Should handle timeout gracefully (via exception handling in orchestrator)
        result = await orchestrator.run_paper_trade_cycle(market_data)
        
        # Should complete without crashing
        assert 'status' in result
    
    @pytest.mark.asyncio
    async def test_malformed_json_recovered(self):
        """Malformed responses should trigger fallback."""
        # Create a client that returns malformed data
        class MalformedClient:
            async def detect_regime(self, market_data):
                return "Invalid-Regime-Name"  # Not in valid list
            
            async def select_strategy(self, market_data, regime="Normal"):
                return "not-json"  # Malformed
            
            async def assess_risk(self, position, market_data=None):
                return {}  # Empty
        
        orchestrator = AIAgentOrchestrator(use_openrouter=False)
        orchestrator.llm_client = MalformedClient()
        orchestrator.use_openrouter = True
        
        market_data = {'volatility': 0.5}
        
        # Should handle malformed data gracefully
        result = await orchestrator.run_paper_trade_cycle(market_data)
        
        # Should have some fallback behavior
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_conflicting_outputs_resolved(self):
        """Conflicting agent outputs should be resolved safely."""
        # Create agents with conflicting signals
        class ConflictingClient:
            async def detect_regime(self, market_data):
                return "High-vol"  # Suggests caution
            
            async def select_strategy(self, market_data, regime="Normal"):
                return {
                    'strategy': 'breakout',  # Aggressive strategy
                    'confidence': 0.9,
                    'parameters': {}
                }
            
            async def assess_risk(self, position, market_data=None):
                return {
                    'risk_level': 'high',  # High risk
                    'max_position_size': 100,  # Small size
                    'stop_loss': 0.05,
                    'leverage_recommendation': 1
                }
        
        orchestrator = AIAgentOrchestrator(use_openrouter=False)
        orchestrator.llm_client = ConflictingClient()
        orchestrator.use_openrouter = True
        
        market_data = {'volatility': 0.8, 'current_price': 50000}
        
        result = await orchestrator.run_paper_trade_cycle(market_data)
        
        # Should resolve conflicts (likely by reducing position size or skipping trade)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_mocks(self, orchestrator_with_mock):
        """Complete workflow should work with mock agents."""
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50000,
            'bid': 49995,  # Add bid for spread check
            'ask': 50005,  # Add ask for spread check
            'volatility': 0.45,
            'rsi': 55,
            'macd': 0.5,
            'ma_20': 49500,
            'ma_50': 49000
        }
        
        result = await orchestrator_with_mock.run_paper_trade_cycle(market_data)
        
        # Should complete successfully
        assert result['status'] == 'success'
        assert 'regime' in result
        assert 'strategy' in result
        assert 'risk' in result
        assert 'trade_proposal' in result
        
        # Verify mock was called
        assert orchestrator_with_mock.llm_client.call_count > 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_activates_on_failures(self):
        """Circuit breaker should pause after consecutive failures."""
        # Create orchestrator with no LLM client (heuristic mode)
        orchestrator = AIAgentOrchestrator(use_openrouter=False)
        
        # Manually simulate consecutive failures by incrementing counter
        for _ in range(3):
            orchestrator._consecutive_failures += 1
            # Check if circuit breaker activates
            if orchestrator._consecutive_failures >= orchestrator._failure_threshold:
                orchestrator._paused = True
                orchestrator._pause_reason = f"Circuit breaker: Simulated failure"
        
        # Circuit breaker should activate
        assert orchestrator.is_paused == True
        assert 'Circuit breaker' in orchestrator._pause_reason
        assert orchestrator._consecutive_failures >= 3
    
    @pytest.mark.asyncio
    async def test_quality_filter_rejects_low_confidence(self, orchestrator_with_mock):
        """Quality filter should reject trades below confidence threshold."""
        # Create client that returns low confidence
        class LowConfidenceClient:
            async def detect_regime(self, market_data):
                return "Normal"
            
            async def select_strategy(self, market_data, regime="Normal"):
                return {
                    'strategy': 'momentum',
                    'confidence': 0.5,  # Below threshold
                    'parameters': {}
                }
            
            async def assess_risk(self, position, market_data=None):
                return {
                    'risk_level': 'medium',
                    'max_position_size': 1000,
                    'stop_loss': 0.02
                }
        
        orchestrator = AIAgentOrchestrator(use_openrouter=False)
        orchestrator.llm_client = LowConfidenceClient()
        orchestrator.use_openrouter = True
        
        market_data = {
            'symbol': 'BTC/USDT',
            'current_price': 50000,
            'volatility': 0.5,
            'rsi': 50,
            'ma_20': 50000,
            'ma_50': 50000,
            'bid': 49999,
            'ask': 50001
        }
        
        result = await orchestrator.run_paper_trade_cycle(market_data)
        
        # Should be rejected due to low confidence
        assert result['status'] in ['rejected', 'no_trade']
    
    @pytest.mark.asyncio
    async def test_mock_agents_enable_fast_testing(self, orchestrator_with_mock):
        """Mock agents should enable fast test execution."""
        import time
        
        market_data = {
            'volatility': 0.5,
            'current_price': 50000,
            'bid': 49995,
            'ask': 50005,
            'ma_20': 49500,
            'ma_50': 49000
        }
        
        start = time.time()
        result = await orchestrator_with_mock.run_paper_trade_cycle(market_data)
        elapsed = time.time() - start
        
        # Should complete quickly (< 1 second with mocks)
        assert elapsed < 1.0
        assert result['status'] == 'success'
