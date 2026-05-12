#!/usr/bin/env python3
"""
Test script to verify trade rejection deduplication mechanism.
Tests that identical rejection reports are suppressed within cooldown period.
"""
import asyncio
from datetime import datetime, timedelta
from app.notifications.notifier import TelegramNotifier


def test_deduplication_logic():
    """Test the deduplication helper methods without sending actual messages."""
    print("="*80)
    print("Testing Trade Rejection Deduplication Logic")
    print("="*80)
    
    # Create notifier instance (won't send messages - no token needed for this test)
    notifier = TelegramNotifier(bot_token=None, chat_id=None)
    
    # Test 1: Reason categorization
    print("\n📋 Test 1: Reason Categorization")
    print("-" * 80)
    
    test_reasons = [
        ("Quality score below threshold of 80", "quality_threshold"),
        ("Quality score too low", "quality_threshold"),
        ("Low confidence in signal", "confidence_low"),
        ("Risk exceeded maximum allowed", "risk_exceeded"),
        ("High volatility detected", "volatility_high"),
        ("Insufficient liquidity", "liquidity_insufficient"),
        ("Spread too wide", "spread_too_wide"),
        ("Some unknown reason here", "some_unknown_reason"),
    ]
    
    all_passed = True
    for reason, expected_category in test_reasons:
        result = notifier._get_reason_category(reason)
        status = "✅ PASS" if result == expected_category else "❌ FAIL"
        if result != expected_category:
            all_passed = False
        print(f"{status}: '{reason[:40]}...' -> {result} (expected: {expected_category})")
    
    # Test 2: Score range grouping
    print("\n📊 Test 2: Score Range Grouping")
    print("-" * 80)
    
    test_scores = [
        (75, "70-79"),
        (79, "70-79"),
        (70, "70-79"),
        (80, "80-89"),
        (85, "80-89"),
        (65, "60-69"),
        (95, "90-99"),
    ]
    
    for score, expected_range in test_scores:
        result = notifier._get_score_range(score)
        status = "✅ PASS" if result == expected_range else "❌ FAIL"
        if result != expected_range:
            all_passed = False
        print(f"{status}: Score {score} -> {result} (expected: {expected_range})")
    
    # Test 3: Cooldown logic simulation
    print("\n⏱️  Test 3: Cooldown Logic Simulation")
    print("-" * 80)
    
    symbol = "PAXG/USDT"
    reason = "Quality score below threshold"
    quality_score = 75
    
    # First rejection should be allowed
    should_send_1 = notifier._should_send_rejection(symbol, reason, quality_score)
    print(f"{'✅ PASS' if should_send_1 else '❌ FAIL'}: First rejection allowed: {should_send_1}")
    if not should_send_1:
        all_passed = False
    
    # Record it
    notifier._record_rejection(symbol, reason, quality_score)
    
    # Second rejection immediately after should be blocked
    should_send_2 = notifier._should_send_rejection(symbol, reason, quality_score)
    print(f"{'✅ PASS' if not should_send_2 else '❌ FAIL'}: Second rejection blocked: {not should_send_2}")
    if should_send_2:
        all_passed = False
    
    # Different symbol should be allowed
    should_send_3 = notifier._should_send_rejection("XAUT/USDT", reason, quality_score)
    print(f"{'✅ PASS' if should_send_3 else '❌ FAIL'}: Different symbol allowed: {should_send_3}")
    if not should_send_3:
        all_passed = False
    
    # Different reason category should be allowed
    should_send_4 = notifier._should_send_rejection(symbol, "Low confidence", quality_score)
    print(f"{'✅ PASS' if should_send_4 else '❌ FAIL'}: Different reason allowed: {should_send_4}")
    if not should_send_4:
        all_passed = False
    
    # Different score range should be allowed
    should_send_5 = notifier._should_send_rejection(symbol, reason, 85)
    print(f"{'✅ PASS' if should_send_5 else '❌ FAIL'}: Different score range allowed: {should_send_5}")
    if not should_send_5:
        all_passed = False
    
    # Test 4: Cooldown expiration
    print("\n⏰ Test 4: Cooldown Expiration")
    print("-" * 80)
    
    # Manually set a past timestamp
    past_time = datetime.utcnow() - timedelta(seconds=700)  # 700 seconds ago (> 600s cooldown)
    dedup_key = (symbol, notifier._get_reason_category(reason), notifier._get_score_range(quality_score))
    notifier._rejection_cooldowns[dedup_key] = past_time
    
    should_send_expired = notifier._should_send_rejection(symbol, reason, quality_score)
    print(f"{'✅ PASS' if should_send_expired else '❌ FAIL'}: Expired cooldown allows new report: {should_send_expired}")
    if not should_send_expired:
        all_passed = False
    
    # Test 5: Cleanup old entries
    print("\n🧹 Test 5: Cleanup Old Entries")
    print("-" * 80)
    
    # Add some old entries
    old_time = datetime.utcnow() - timedelta(seconds=1500)  # Very old
    notifier._rejection_cooldowns[("OLD/SYMBOL", "test", "0-9")] = old_time
    notifier._rejection_cooldowns[("OLDER/SYMBOL", "test", "10-19")] = old_time
    
    initial_count = len(notifier._rejection_cooldowns)
    notifier._cleanup_old_cooldowns(datetime.utcnow())
    final_count = len(notifier._rejection_cooldowns)
    
    cleaned_count = initial_count - final_count
    print(f"{'✅ PASS' if cleaned_count > 0 else '❌ FAIL'}: Cleaned {cleaned_count} old entries ({initial_count} -> {final_count})")
    if cleaned_count == 0:
        all_passed = False
    
    # Final summary
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED - Deduplication mechanism working correctly!")
    else:
        print("❌ SOME TESTS FAILED - Review output above")
    print("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = test_deduplication_logic()
    exit(0 if success else 1)
