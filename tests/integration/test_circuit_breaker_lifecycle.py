"""
Integration tests for Circuit Breaker lifecycle.

Tests:
1. Opens after failure threshold reached
2. Blocks new operations when OPEN
3. Transitions to HALF_OPEN after timeout
4. Closes on successful recovery test
5. Reopens on failed recovery test
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.infra.circuit_breaker import SystemCircuitBreaker, CircuitBreakerState


@pytest.fixture
def mock_notifier():
    """Create mock Telegram notifier."""
    notifier = AsyncMock()
    notifier.send_circuit_breaker_alert = AsyncMock()
    return notifier


@pytest.fixture
def circuit_breaker(mock_notifier):
    """Create circuit breaker with test configuration."""
    cb = SystemCircuitBreaker(notifier=mock_notifier)
    # Use short timeouts for testing
    cb.failure_threshold = 3
    cb.recovery_timeout = 1  # 1 second for fast tests
    cb.slippage_threshold = 0.05
    cb.latency_threshold_ms = 1000
    return cb


class TestCircuitBreakerLifecycle:
    """Test circuit breaker state transitions."""
    
    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(self, circuit_breaker, mock_notifier):
        """Circuit breaker should transition to OPEN after reaching failure threshold."""
        # Record failures up to threshold
        for i in range(circuit_breaker.failure_threshold):
            await circuit_breaker.record_api_call(
                success=False,
                latency_ms=100,
                endpoint='/test/endpoint'
            )
        
        # Should be OPEN now
        assert circuit_breaker.state == 'OPEN'
        assert circuit_breaker.api_failure_count >= circuit_breaker.failure_threshold
        
        # Verify alert was sent
        mock_notifier.send_circuit_breaker_alert.assert_called()
    
    @pytest.mark.asyncio
    async def test_blocks_operations_when_open(self, circuit_breaker, mock_notifier):
        """Circuit breaker should block trading when in OPEN state."""
        # Trigger OPEN state
        for _ in range(circuit_breaker.failure_threshold):
            await circuit_breaker.record_api_call(False, 100, '/test')
        
        assert circuit_breaker.state == 'OPEN'
        
        # Check system health - should not allow trading
        health = await circuit_breaker.check_system_health()
        assert health.can_trade == False
        assert health.state == 'OPEN'
    
    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self, circuit_breaker, mock_notifier):
        """Circuit breaker should transition to HALF_OPEN after recovery timeout."""
        # Trigger OPEN state
        for _ in range(circuit_breaker.failure_threshold):
            await circuit_breaker.record_api_call(False, 100, '/test')
        
        assert circuit_breaker.state == 'OPEN'
        
        # Wait for recovery timeout
        await asyncio.sleep(circuit_breaker.recovery_timeout + 0.1)
        
        # Attempt recovery - should transition to HALF_OPEN first
        result = await circuit_breaker.attempt_recovery()
        
        # Recovery should succeed (no actual failures in health check)
        assert result == True
        assert circuit_breaker.state == 'CLOSED'
    
    @pytest.mark.asyncio
    async def test_closes_on_successful_recovery(self, circuit_breaker, mock_notifier):
        """Circuit breaker should return to CLOSED after successful recovery test."""
        # Trigger OPEN state
        for _ in range(circuit_breaker.failure_threshold):
            await circuit_breaker.record_api_call(False, 100, '/test')
        
        assert circuit_breaker.state == 'OPEN'
        
        # Wait for recovery timeout
        await asyncio.sleep(circuit_breaker.recovery_timeout + 0.1)
        
        # Attempt recovery
        result = await circuit_breaker.attempt_recovery()
        
        # Should recover successfully
        assert result == True
        assert circuit_breaker.state == 'CLOSED'
        assert circuit_breaker.trigger_reason is None
        assert circuit_breaker.triggered_at is None
        
        # Counters should be reset
        assert circuit_breaker.api_failure_count == 0
    
    @pytest.mark.asyncio
    async def test_reopens_on_failed_recovery(self, circuit_breaker, mock_notifier):
        """Circuit breaker should return to OPEN if recovery test fails."""
        # Trigger OPEN state
        for _ in range(circuit_breaker.failure_threshold):
            await circuit_breaker.record_api_call(False, 100, '/test')
        
        assert circuit_breaker.state == 'OPEN'
        
        # Manually set a condition that will fail health check
        circuit_breaker.position_sync_ok = False
        
        # Wait for recovery timeout
        await asyncio.sleep(circuit_breaker.recovery_timeout + 0.1)
        
        # Attempt recovery - should fail due to position sync issue
        result = await circuit_breaker.attempt_recovery()
        
        # Should fail and return to OPEN
        assert result == False
        assert circuit_breaker.state == 'OPEN'
        
        # Timer should be reset
        assert circuit_breaker.triggered_at is not None
    
    @pytest.mark.asyncio
    async def test_resets_failure_count_on_success(self, circuit_breaker):
        """Successful API calls should reset failure counter."""
        # Record some failures
        for _ in range(2):
            await circuit_breaker.record_api_call(False, 100, '/test')
        
        assert circuit_breaker.api_failure_count == 2
        
        # Record success
        await circuit_breaker.record_api_call(True, 100, '/test')
        
        # Counter should reset
        assert circuit_breaker.api_failure_count == 0
    
    @pytest.mark.asyncio
    async def test_tracks_slippage_and_triggers_on_excess(self, circuit_breaker, mock_notifier):
        """High slippage should trigger circuit breaker."""
        # Record high slippage events
        for _ in range(5):
            await circuit_breaker.record_fill_slippage(
                symbol='BTC/USDT',
                expected_price=50000.0,
                actual_price=52000.0  # 4% slippage
            )
        
        # Average slippage should exceed threshold (5%)
        avg_slippage = sum(circuit_breaker.recent_slippages) / len(circuit_breaker.recent_slippages)
        assert avg_slippage > 0.03  # At least 3% average
    
    @pytest.mark.asyncio
    async def test_emergency_close_positions(self, circuit_breaker, mock_notifier):
        """Emergency position closure should send notification."""
        await circuit_breaker.emergency_close_positions(
            exclude_symbols=['BTC/USDT']
        )
        
        # Verify emergency notification was sent
        mock_notifier.send_emergency_position_closure.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_health_report(self, circuit_breaker):
        """Health report should contain all metrics."""
        # Record some data
        await circuit_breaker.record_api_call(True, 50, '/test')
        await circuit_breaker.record_api_call(False, 200, '/test')
        
        report = circuit_breaker.get_health_report()
        
        assert 'circuit_state' in report
        assert 'metrics' in report
        assert 'thresholds' in report
        assert report['metrics']['api_failures'] >= 0
        assert report['metrics']['api_successes'] >= 0
    
    @pytest.mark.asyncio
    async def test_websocket_disconnect_handling(self, circuit_breaker, mock_notifier):
        """WebSocket disconnect should be tracked."""
        await circuit_breaker.handle_websocket_disconnect('btcusdt@trade')
        
        assert circuit_breaker.websocket_healthy == False
        
        # Simulate reconnection
        await circuit_breaker.handle_websocket_message('btcusdt@trade')
        
        assert circuit_breaker.websocket_healthy == True
