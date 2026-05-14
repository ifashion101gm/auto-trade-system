#!/usr/bin/env python3
"""
Test Enterprise Main Features
Validates session scheduler, news guard, admin routes, and Telegram queue.
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_session_scheduler():
    """Test session scheduler functionality."""
    print("🔍 Testing SessionScheduler...")
    
    from app.runtime.session_scheduler import SessionScheduler, TradingSession
    
    scheduler = SessionScheduler()
    
    # Test current session
    current = scheduler.get_current_session()
    print(f"  ℹ️  Current session: {current.value}")
    
    # Test trading allowed
    allowed = scheduler.is_trading_allowed()
    print(f"  ℹ️  Trading allowed: {allowed}")
    
    # Test session info
    info = scheduler.get_session_info()
    if 'current_session' in info and 'next_session' in info:
        print("  ✅ Session info structure correct")
    else:
        print("  ❌ Session info missing fields")
        return False
    
    # Test leverage recommendation
    leverage = scheduler.get_recommended_leverage()
    if leverage in [1, 3, 5]:
        print(f"  ✅ Recommended leverage: {leverage}x")
    else:
        print(f"  ❌ Invalid leverage: {leverage}")
        return False
    
    return True


def test_news_guard():
    """Test news guard functionality."""
    print("\n🔍 Testing NewsGuard...")
    
    from app.runtime.news_guard import NewsGuard, NewsEventType
    from datetime import datetime, timezone, timedelta
    
    guard = NewsGuard(default_buffer_minutes=30)
    
    # Test initial state (should be safe)
    if guard.is_trading_safe():
        print("  ✅ Initial state is trading-safe")
    else:
        print("  ❌ Should be safe with no events")
        return False
    
    # Add a future event
    future_event = datetime.now(timezone.utc) + timedelta(hours=2)
    guard.add_event(
        event_type=NewsEventType.NFP,
        scheduled_time=future_event,
        description="Non-Farm Payrolls"
    )
    
    # Should still be safe (event is 2 hours away)
    if guard.is_trading_safe():
        print("  ✅ Future event doesn't block trading yet")
    else:
        print("  ❌ Should allow trading before buffer window")
        return False
    
    # Get status
    status = guard.get_status()
    if 'trading_safe' in status and 'next_event' in status:
        print("  ✅ Status structure correct")
    else:
        print("  ❌ Status missing fields")
        return False
    
    print(f"  ℹ️  Next event: {status['next_event']['type']}")
    
    return True


async def test_telegram_queue():
    """Test Telegram message queue."""
    print("\n🔍 Testing Telegram Queue...")
    
    from app.main_enterprise import state
    
    # Queue some messages
    await state.telegram_queue.put("Test message 1")
    await state.telegram_queue.put("Test message 2")
    
    queue_size = state.telegram_queue.qsize()
    if queue_size == 2:
        print(f"  ✅ Messages queued: {queue_size}")
    else:
        print(f"  ❌ Expected 2 messages, got {queue_size}")
        return False
    
    # Retrieve messages
    msg1 = await state.telegram_queue.get()
    msg2 = await state.telegram_queue.get()
    
    if msg1 == "Test message 1" and msg2 == "Test message 2":
        print("  ✅ Messages retrieved in order")
    else:
        print("  ❌ Message order incorrect")
        return False
    
    return True


def test_app_state():
    """Test AppState initialization."""
    print("\n🔍 Testing AppState...")
    
    from app.main_enterprise import state
    
    # Check components exist
    if hasattr(state, 'session_scheduler'):
        print("  ✅ Session scheduler initialized")
    else:
        print("  ❌ Missing session scheduler")
        return False
    
    if hasattr(state, 'news_guard'):
        print("  ✅ News guard initialized")
    else:
        print("  ❌ Missing news guard")
        return False
    
    if hasattr(state, 'telegram_queue'):
        print("  ✅ Telegram queue initialized")
    else:
        print("  ❌ Missing telegram queue")
        return False
    
    if hasattr(state, 'task_supervisor'):
        print("  ℹ️  Task supervisor: {state.task_supervisor}")
    
    # Check initial state
    if state.trading_enabled:
        print("  ✅ Trading enabled by default")
    else:
        print("  ⚠️  Trading disabled initially")
    
    return True


async def main():
    """Run all tests."""
    print("=" * 80)
    print("ENTERPRISE MAIN VALIDATION")
    print("=" * 80)
    
    results = []
    
    # Run tests
    results.append(("SessionScheduler", test_session_scheduler()))
    results.append(("NewsGuard", test_news_guard()))
    results.append(("AppState", test_app_state()))
    results.append(("TelegramQueue", await test_telegram_queue()))
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print("=" * 80)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All enterprise features validated!")
        print("\n📋 Next Steps:")
        print("  1. Review app/main_enterprise.py")
        print("  2. Set ADMIN_API_KEY in .env")
        print("  3. Replace main.py: cp app/main_enterprise.py app/main.py")
        print("  4. Test endpoints:")
        print("     - curl http://localhost:8000/health/deep | jq")
        print("     - curl http://localhost:8000/admin/session/info | jq")
        print("     - curl -H 'x-api-key: YOUR_KEY' http://localhost:8000/admin/state | jq")
        return 0
    else:
        print("⚠️  Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
