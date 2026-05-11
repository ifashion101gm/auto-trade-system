#!/usr/bin/env python3
"""
Quick validation script for execution layer upgrade.
Tests all new components without requiring live trades.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.exchange.exchange_adapter import ExchangeAdapter, CircuitBreaker, RateLimiter
from app.events.event_bus import EventBus
from app.events.event_store import EventStore
from app.services.execution_states import ExecutionState, is_valid_transition, get_valid_next_states
from app.logging_config import setup_logging

setup_logging()


async def test_circuit_breaker():
    """Test circuit breaker state transitions."""
    print("\n🧪 Testing Circuit Breaker...")
    
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=2)
    
    # Test CLOSED state
    assert cb.can_execute() == True
    print("  ✅ Initial state: CLOSED (can execute)")
    
    # Record failures
    cb.record_failure()
    cb.record_failure()
    print(f"  ✅ After 2 failures: {cb.state} (failure_count={cb.failure_count})")
    
    # Third failure should open circuit
    cb.record_failure()
    assert cb.state == 'OPEN'
    assert cb.can_execute() == False
    print("  ✅ After 3 failures: OPEN (cannot execute)")
    
    # Wait for recovery timeout
    import time
    time.sleep(2.1)
    assert cb.can_execute() == True  # Should transition to HALF_OPEN
    print("  ✅ After timeout: HALF_OPEN (testing recovery)")
    
    # Success should close circuit
    cb.record_success()
    assert cb.state == 'CLOSED'
    print("  ✅ After success: CLOSED (recovered)")
    
    print("✅ Circuit breaker test passed!\n")


async def test_rate_limiter():
    """Test rate limiter."""
    print("🧪 Testing Rate Limiter...")
    
    rl = RateLimiter(max_calls=5, time_window=1.0)
    
    # Make 5 calls (should be fast)
    start = asyncio.get_event_loop().time()
    for i in range(5):
        await rl.wait_if_needed()
    elapsed = asyncio.get_event_loop().time() - start
    
    assert elapsed < 0.5, f"First 5 calls took {elapsed}s (should be <0.5s)"
    print(f"  ✅ First 5 calls completed in {elapsed*1000:.0f}ms")
    
    # 6th call should wait
    start = asyncio.get_event_loop().time()
    await rl.wait_if_needed()
    elapsed = asyncio.get_event_loop().time() - start
    
    assert elapsed > 0.5, f"6th call didn't wait (elapsed={elapsed}s)"
    print(f"  ✅ 6th call waited {elapsed*1000:.0f}ms (rate limited)")
    
    print("✅ Rate limiter test passed!\n")


async def test_event_bus():
    """Test event bus priority processing."""
    print("🧪 Testing Event Bus...")
    
    bus = EventBus(max_queue_size=100)
    
    received_events = []
    
    async def handler(event):
        received_events.append(event)
    
    # Subscribe with different priorities
    bus.subscribe('TEST_EVENT', handler, priority=10)
    bus.subscribe('TEST_EVENT', handler, priority=5)
    bus.subscribe('TEST_EVENT', handler, priority=1)
    
    # Start processing
    await bus.start_processing()
    
    # Publish events
    await bus.publish('TEST_EVENT', {'data': 'test1'}, priority=10)
    await bus.publish('TEST_EVENT', {'data': 'test2'}, priority=1)
    await bus.publish('TEST_EVENT', {'data': 'test3'}, priority=5)
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Check metrics
    metrics = bus.get_metrics()
    assert metrics['events_published'] == 3
    assert metrics['events_processed'] == 9  # 3 events × 3 handlers
    print(f"  ✅ Published: {metrics['events_published']} events")
    print(f"  ✅ Processed: {metrics['events_processed']} handler calls")
    
    # Stop processing
    await bus.stop_processing()
    
    print("✅ Event bus test passed!\n")


async def test_state_machine():
    """Test state machine transitions."""
    print("🧪 Testing State Machine...")
    
    # Test valid transitions
    assert is_valid_transition(ExecutionState.IDLE, ExecutionState.FETCHING_DATA)
    print("  ✅ IDLE → FETCHING_DATA: Valid")
    
    assert is_valid_transition(ExecutionState.FETCHING_DATA, ExecutionState.ANALYZING)
    print("  ✅ FETCHING_DATA → ANALYZING: Valid")
    
    assert is_valid_transition(ExecutionState.ANALYZING, ExecutionState.PROPOSING)
    print("  ✅ ANALYZING → PROPOSING: Valid")
    
    # Test invalid transition
    assert not is_valid_transition(ExecutionState.IDLE, ExecutionState.EXECUTING)
    print("  ✅ IDLE → EXECUTING: Invalid (correctly rejected)")
    
    # Get valid next states
    next_states = get_valid_next_states(ExecutionState.EXECUTING)
    assert ExecutionState.MONITORING in next_states
    assert ExecutionState.ERROR in next_states
    print(f"  ✅ From EXECUTING can go to: {[s.value for s in next_states]}")
    
    print("✅ State machine test passed!\n")


async def test_exchange_adapter_mock():
    """Test exchange adapter with mock client."""
    print("🧪 Testing Exchange Adapter (Mock)...")
    
    # Create a mock exchange
    class MockExchange:
        def __init__(self):
            self.call_count = 0
            self.mode = 'DEMO'
            self.has_watch_ohlcv = False
            self.has_create_stop_loss_limit = True
        
        async def fetch_ticker(self, symbol):
            self.call_count += 1
            if self.call_count <= 2:
                raise Exception("Network error")
            return {'last_price': 2000}
        
        async def close(self):
            pass
        
        def calculate_fee(self, *args, **kwargs):
            return 0.001
        
        async def validate_symbol(self, symbol):
            return True
        
        # Stub other required methods
        async def fetch_ohlcv(self, *args, **kwargs): return []
        async def fetch_markets(self): return []
        async def get_balance(self): return {}
        async def create_market_order(self, *args, **kwargs): return {}
        async def create_limit_order(self, *args, **kwargs): return {}
        async def cancel_order(self, *args, **kwargs): return {}
        async def fetch_order_status(self, *args, **kwargs): return {}
        async def fetch_open_orders(self, *args, **kwargs): return []
        async def fetch_order_history(self, *args, **kwargs): return []
        async def get_positions(self): return []
        async def close_position(self, *args, **kwargs): return {}
        async def set_leverage(self, *args, **kwargs): return {}
    
    mock_exchange = MockExchange()
    adapter = ExchangeAdapter(
        exchange=mock_exchange,
        max_retries=3,
        base_delay=0.1  # Fast retries for testing
    )
    
    # First call should fail twice then succeed (retry logic)
    try:
        result = await adapter.fetch_ticker('XAUT/USDT')
        print(f"  ✅ Fetch succeeded after retries: {result}")
        print(f"  ✅ Total API calls: {mock_exchange.call_count} (2 failed + 1 success)")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        raise
    
    # Check metrics
    metrics = adapter.get_metrics()
    print(f"  ✅ Request count: {metrics['request_count']}")
    print(f"  ✅ Error count: {metrics['error_count']}")
    print(f"  ✅ Circuit breaker: {metrics['circuit_breaker_state']}")
    
    print("✅ Exchange adapter test passed!\n")


async def main():
    """Run all tests."""
    print("=" * 70)
    print("🚀 Execution Layer Upgrade - Validation Tests")
    print("=" * 70)
    
    try:
        await test_circuit_breaker()
        await test_rate_limiter()
        await test_event_bus()
        await test_state_machine()
        await test_exchange_adapter_mock()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\n🎉 Execution layer upgrade is working correctly!")
        print("\nNext steps:")
        print("  1. Review QUICK_REFERENCE_EXECUTION_LAYER.md for usage examples")
        print("  2. Check IMPLEMENTATION_COMPLETE.md for full documentation")
        print("  3. Integrate components into your trading service")
        print("  4. Test with MEXC/Binance testnet")
        
    except Exception as e:
        print("=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
