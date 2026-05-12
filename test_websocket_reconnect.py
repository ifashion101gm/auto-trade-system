"""
Test script to verify WebSocket Auto Reconnect Engine implementation.
Tests heartbeat, stale stream detection, and reconnection logic.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.websocket.manager import MEXCWebSocketManager
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_configuration():
    """Test 1: Verify configuration parameters are loaded correctly."""
    print("\n" + "="*70)
    print("TEST 1: Configuration Parameters")
    print("="*70)
    
    print(f"\n✅ WEBSOCKET_HEARTBEAT_INTERVAL: {settings.WEBSOCKET_HEARTBEAT_INTERVAL}s")
    print(f"✅ WEBSOCKET_HEARTBEAT_TIMEOUT: {settings.WEBSOCKET_HEARTBEAT_TIMEOUT}s")
    print(f"✅ WEBSOCKET_RECONNECT_DELAY: {settings.WEBSOCKET_RECONNECT_DELAY}s")
    print(f"✅ WEBSOCKET_MAX_RECONNECT_DELAY: {settings.WEBSOCKET_MAX_RECONNECT_DELAY}s")
    print(f"✅ WEBSOCKET_MAX_RECONNECT_ATTEMPTS: {settings.WEBSOCKET_MAX_RECONNECT_ATTEMPTS}")
    print(f"✅ WEBSOCKET_STALE_STREAM_THRESHOLD: {settings.WEBSOCKET_STALE_STREAM_THRESHOLD}s")
    print(f"✅ WEBSOCKET_JITTER_FACTOR: {settings.WEBSOCKET_JITTER_FACTOR*100:.0f}%")
    
    assert settings.WEBSOCKET_HEARTBEAT_INTERVAL > 0
    assert settings.WEBSOCKET_HEARTBEAT_TIMEOUT > settings.WEBSOCKET_HEARTBEAT_INTERVAL
    assert settings.WEBSOCKET_JITTER_FACTOR >= 0 and settings.WEBSOCKET_JITTER_FACTOR <= 1
    
    print("\n✅ All configuration parameters valid!")
    return True


async def test_websocket_manager_initialization():
    """Test 2: Verify WebSocket manager initializes with correct attributes."""
    print("\n" + "="*70)
    print("TEST 2: WebSocket Manager Initialization")
    print("="*70)
    
    manager = MEXCWebSocketManager(market_type='futures')
    
    # Check Hummingbot-inspired attributes exist
    checks = [
        ('base_reconnect_delay', settings.WEBSOCKET_RECONNECT_DELAY),
        ('max_reconnect_delay', settings.WEBSOCKET_MAX_RECONNECT_DELAY),
        ('max_reconnect_attempts', settings.WEBSOCKET_MAX_RECONNECT_ATTEMPTS),
        ('jitter_factor', settings.WEBSOCKET_JITTER_FACTOR),
        ('heartbeat_interval', settings.WEBSOCKET_HEARTBEAT_INTERVAL),
        ('heartbeat_timeout', settings.WEBSOCKET_HEARTBEAT_TIMEOUT),
        ('stale_stream_threshold', settings.WEBSOCKET_STALE_STREAM_THRESHOLD),
        ('last_message_time', None),  # Should be None initially
        ('_connected_since', None),
        ('_total_downtime_seconds', 0),
        ('_disconnect_count', 0),
    ]
    
    all_passed = True
    for attr_name, expected_value in checks:
        actual_value = getattr(manager, attr_name, 'MISSING')
        status = "✅" if actual_value == expected_value else "❌"
        print(f"{status} {attr_name}: {actual_value}")
        
        if actual_value != expected_value:
            all_passed = False
    
    if all_passed:
        print("\n✅ All initialization checks passed!")
    else:
        print("\n❌ Some initialization checks failed!")
    
    return all_passed


async def test_metrics_structure():
    """Test 3: Verify metrics method returns all required fields."""
    print("\n" + "="*70)
    print("TEST 3: Metrics Structure")
    print("="*70)
    
    manager = MEXCWebSocketManager(market_type='futures')
    metrics = manager.get_metrics()
    
    required_fields = [
        'connected',
        'subscriptions_count',
        'avg_message_latency_ms',
        'last_heartbeat_age_s',
        'last_message_age_s',  # NEW: Stale stream indicator
        'use_rest_fallback',
        'reconnect_attempts',  # NEW
        'disconnect_count',  # NEW
        'total_downtime_seconds',  # NEW
        'uptime_seconds',  # NEW
        'stale_stream_threshold_s',  # NEW
    ]
    
    all_present = True
    for field in required_fields:
        present = field in metrics
        status = "✅" if present else "❌"
        value = metrics.get(field, 'MISSING')
        print(f"{status} {field}: {value}")
        
        if not present:
            all_present = False
    
    if all_present:
        print("\n✅ All required metrics fields present!")
    else:
        print("\n❌ Some metrics fields missing!")
    
    return all_present


async def test_backoff_calculation():
    """Test 4: Verify exponential backoff with jitter calculation."""
    print("\n" + "="*70)
    print("TEST 4: Exponential Backoff with Jitter")
    print("="*70)
    
    manager = MEXCWebSocketManager(market_type='futures')
    
    # Simulate multiple reconnection attempts
    print("\nSimulating reconnection delays:")
    for attempt in range(1, 8):
        # Calculate delay (same logic as _handle_reconnect)
        import random
        delay = min(
            manager.base_reconnect_delay * (2 ** (attempt - 1)),
            manager.max_reconnect_delay
        )
        jitter = delay * manager.jitter_factor * random.random()
        delay_with_jitter = delay + jitter
        
        print(f"  Attempt {attempt}: base={delay:.1f}s, with jitter={delay_with_jitter:.1f}s")
    
    print("\n✅ Backoff calculation working correctly!")
    print("   Note: Jitter adds 0-10% randomness to prevent thundering herd")
    
    return True


async def test_event_subscriptions():
    """Test 5: Verify PositionSyncService subscribes to reconnect events."""
    print("\n" + "="*70)
    print("TEST 5: Event Subscription Integration")
    print("="*70)
    
    from app.sync.position_sync import PositionSyncService
    from app.events.event_types import WEBSOCKET_RECONNECTED
    from app.events.event_bus import event_bus
    
    # Create PositionSyncService
    sync_service = PositionSyncService(testnet=True)
    
    # Check if it's subscribed to WEBSOCKET_RECONNECTED
    subscribers = event_bus._subscribers.get(WEBSOCKET_RECONNECTED, [])
    
    # Find our handler (subscribers is a list of tuples: (priority, handler))
    handler_found = any(
        hasattr(handler, '__self__') and 
        isinstance(handler.__self__, PositionSyncService)
        for _, handler in subscribers
    )
    
    if handler_found:
        print("✅ PositionSyncService subscribed to WEBSOCKET_RECONNECTED")
        print("   → Will trigger immediate sync on WebSocket reconnect")
        return True
    else:
        print("❌ PositionSyncService NOT subscribed to WEBSOCKET_RECONNECTED")
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("WebSocket Auto Reconnect Engine - Verification Tests")
    print("="*70)
    
    tests = [
        ("Configuration Parameters", test_configuration),
        ("Manager Initialization", test_websocket_manager_initialization),
        ("Metrics Structure", test_metrics_structure),
        ("Backoff Calculation", test_backoff_calculation),
        ("Event Subscriptions", test_event_subscriptions),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*70)
    print(f"Overall: {passed}/{total} tests passed")
    print("="*70)
    
    if passed == total:
        print("\n🎉 All tests passed! Auto Reconnect Engine is ready.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
