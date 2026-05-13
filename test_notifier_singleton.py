#!/usr/bin/env python3
"""
Test script to verify Telegram notifier singleton and deduplication behavior.
This ensures rejection reports are properly deduplicated across different instances.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from app.notifications.notifier import TelegramNotifier


def test_singleton_pattern():
    """Test that all TelegramNotifier instances are the same object."""
    print("\n" + "="*70)
    print("TEST 1: Singleton Pattern Verification")
    print("="*70)
    
    # Create multiple instances
    notifier1 = TelegramNotifier()
    notifier2 = TelegramNotifier()
    notifier3 = TelegramNotifier(bot_token="test", chat_id="test")
    
    # Verify they are the same object
    assert notifier1 is notifier2, "notifier1 and notifier2 should be the same instance"
    assert notifier2 is notifier3, "notifier2 and notifier3 should be the same instance"
    assert notifier1 is notifier3, "notifier1 and notifier3 should be the same instance"
    
    print("✅ All instances are the same object (singleton verified)")
    print(f"   Instance ID: {id(notifier1)}")
    return True


def test_shared_deduplication_state():
    """Test that deduplication state is shared across instances."""
    print("\n" + "="*70)
    print("TEST 2: Shared Deduplication State")
    print("="*70)
    
    # Get two references to the singleton
    notifier1 = TelegramNotifier()
    notifier2 = TelegramNotifier()
    
    # Clear any existing cooldowns for clean test
    notifier1._rejection_cooldowns.clear()
    
    # Record a rejection via notifier1
    notifier1._record_rejection("XAU/USDT:USDT", "Quality score below threshold", 65)
    
    # Check if notifier2 can see it
    should_send = notifier2._should_send_rejection("XAU/USDT:USDT", "Quality score below threshold", 65)
    
    assert not should_send, "notifier2 should detect duplicate from notifier1"
    print("✅ Deduplication state is shared between instances")
    print(f"   Cooldowns dict ID (notifier1): {id(notifier1._rejection_cooldowns)}")
    print(f"   Cooldowns dict ID (notifier2): {id(notifier2._rejection_cooldowns)}")
    print(f"   Same dict: {notifier1._rejection_cooldowns is notifier2._rejection_cooldowns}")
    return True


async def test_deduplication_prevents_duplicates():
    """Test that identical rejections are suppressed within cooldown period."""
    print("\n" + "="*70)
    print("TEST 3: Deduplication Prevents Duplicate Notifications")
    print("="*70)
    
    notifier = TelegramNotifier()
    notifier._rejection_cooldowns.clear()
    
    # First rejection - should be allowed
    result1 = notifier._should_send_rejection("XAU/USDT:USDT", "Quality score below threshold", 65)
    assert result1, "First rejection should be allowed"
    print("✅ First rejection: ALLOWED")
    
    # Record it
    notifier._record_rejection("XAU/USDT:USDT", "Quality score below threshold", 65)
    
    # Second rejection (same characteristics) - should be blocked
    result2 = notifier._should_send_rejection("XAU/USDT:USDT", "Quality score below threshold", 65)
    assert not result2, "Second identical rejection should be blocked"
    print("✅ Second rejection (identical): BLOCKED by deduplication")
    
    # Different symbol - should be allowed
    result3 = notifier._should_send_rejection("PAXG/USDT", "Quality score below threshold", 65)
    assert result3, "Different symbol should be allowed"
    print("✅ Rejection with different symbol: ALLOWED")
    
    # Different reason - should be allowed
    result4 = notifier._should_send_rejection("XAU/USDT:USDT", "Low confidence in signal", 65)
    assert result4, "Different reason should be allowed"
    print("✅ Rejection with different reason: ALLOWED")
    
    # Different score range - should be allowed
    result5 = notifier._should_send_rejection("XAU/USDT:USDT", "Quality score below threshold", 85)
    assert result5, "Different score range should be allowed"
    print("✅ Rejection with different score range (85 vs 65): ALLOWED")
    
    return True


async def test_cooldown_expiration():
    """Test that cooldown expires after the configured time."""
    print("\n" + "="*70)
    print("TEST 4: Cooldown Expiration")
    print("="*70)
    
    notifier = TelegramNotifier()
    notifier._rejection_cooldowns.clear()
    
    # Set a very short cooldown for testing
    original_cooldown = notifier._rejection_cooldown_seconds
    notifier._rejection_cooldown_seconds = 2  # 2 seconds for testing
    
    # Record a rejection
    notifier._record_rejection("XAU/USDT:USDT", "Quality score below threshold", 65)
    
    # Should be blocked immediately
    result1 = notifier._should_send_rejection("XAU/USDT:USDT", "Quality score below threshold", 65)
    assert not result1, "Should be blocked immediately after recording"
    print("✅ Rejection blocked immediately after recording")
    
    # Wait for cooldown to expire
    print("   Waiting 3 seconds for cooldown to expire...")
    await asyncio.sleep(3)
    
    # Should be allowed after cooldown
    result2 = notifier._should_send_rejection("XAU/USDT:USDT", "Quality score below threshold", 65)
    assert result2, "Should be allowed after cooldown expires"
    print("✅ Rejection allowed after cooldown expiration")
    
    # Restore original cooldown
    notifier._rejection_cooldown_seconds = original_cooldown
    
    return True


def test_reason_categorization():
    """Test that reason categorization works correctly."""
    print("\n" + "="*70)
    print("TEST 5: Reason Categorization")
    print("="*70)
    
    notifier = TelegramNotifier()
    
    test_cases = [
        ("Quality score below threshold (75 < 80)", "quality_threshold"),
        ("Quality score too low for execution", "quality_threshold"),
        ("Low confidence in signal (0.65 < 0.75)", "confidence_low"),
        ("Confidence below minimum threshold", "confidence_low"),
        ("Risk exceeded maximum allowed", "risk_exceeded"),
        ("High volatility detected", "volatility_high"),
        ("Insufficient liquidity for order size", "liquidity_insufficient"),
        ("Spread too wide for safe execution", "spread_too_wide"),
    ]
    
    for reason, expected_category in test_cases:
        category = notifier._get_reason_category(reason)
        assert category == expected_category, f"Expected '{expected_category}', got '{category}'"
        print(f"✅ '{reason[:50]}...' → '{category}'")
    
    return True


def test_score_range_grouping():
    """Test that score ranges are grouped correctly."""
    print("\n" + "="*70)
    print("TEST 6: Score Range Grouping")
    print("="*70)
    
    notifier = TelegramNotifier()
    
    test_cases = [
        (65, "60-69"),
        (75, "70-79"),
        (85, "80-89"),
        (95, "90-99"),
        (50, "50-59"),
        (59, "50-59"),
        (60, "60-69"),
        (69, "60-69"),
        (70, "70-79"),
    ]
    
    for score, expected_range in test_cases:
        range_str = notifier._get_score_range(score)
        assert range_str == expected_range, f"Score {score}: Expected '{expected_range}', got '{range_str}'"
        print(f"✅ Score {score:3d} → Range '{range_str}'")
    
    return True


async def test_memory_cleanup():
    """Test that old cooldown entries are cleaned up."""
    print("\n" + "="*70)
    print("TEST 7: Memory Cleanup of Old Entries")
    print("="*70)
    
    notifier = TelegramNotifier()
    notifier._rejection_cooldowns.clear()
    
    # Set short cooldown for testing
    original_cooldown = notifier._rejection_cooldown_seconds
    notifier._rejection_cooldown_seconds = 1  # 1 second for testing
    
    # Add several entries with old timestamps
    now = datetime.utcnow()
    old_time = now - timedelta(seconds=3)  # 3 seconds ago (beyond 2x cooldown)
    
    notifier._rejection_cooldowns[("SYM1", "cat1", "60-69")] = old_time
    notifier._rejection_cooldowns[("SYM2", "cat2", "70-79")] = old_time
    notifier._rejection_cooldowns[("SYM3", "cat3", "80-89")] = now  # Recent, should stay
    
    initial_count = len(notifier._rejection_cooldowns)
    print(f"   Initial entries: {initial_count}")
    
    # Trigger cleanup by recording a new rejection
    notifier._record_rejection("SYM4", "cat4", 65)
    
    final_count = len(notifier._rejection_cooldowns)
    print(f"   Final entries: {final_count}")
    
    # Old entries should be removed, recent ones kept
    assert final_count < initial_count, "Old entries should be cleaned up"
    assert ("SYM3", "cat3", "80-89") in notifier._rejection_cooldowns, "Recent entry should remain"
    assert ("SYM1", "cat1", "60-69") not in notifier._rejection_cooldowns, "Old entry should be removed"
    
    print("✅ Old entries cleaned up successfully")
    print("✅ Recent entries preserved")
    
    # Restore original cooldown
    notifier._rejection_cooldown_seconds = original_cooldown
    
    return True


async def main():
    """Run all tests."""
    print("\n" + "#"*70)
    print("# TELEGRAM NOTIFIER SINGLETON & DEDUPLICATION TESTS")
    print("#"*70)
    
    tests = [
        ("Singleton Pattern", test_singleton_pattern),
        ("Shared Deduplication State", test_shared_deduplication_state),
        ("Deduplication Prevents Duplicates", test_deduplication_prevents_duplicates),
        ("Cooldown Expiration", test_cooldown_expiration),
        ("Reason Categorization", test_reason_categorization),
        ("Score Range Grouping", test_score_range_grouping),
        ("Memory Cleanup", test_memory_cleanup),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAILED: {test_name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*70)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Deduplication mechanism is working correctly.")
        print("\nKey findings:")
        print("  ✅ Singleton pattern ensures single instance across application")
        print("  ✅ Shared deduplication state prevents duplicate notifications")
        print("  ✅ Cooldown period (10 min default) blocks identical rejections")
        print("  ✅ Different symbols/reasons/scores still get through")
        print("  ✅ Automatic memory cleanup prevents leaks")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
