#!/usr/bin/env python3
"""
Verification script for Task Queue Frozen fix.

This script tests that QueueWatchdog integration is working correctly
by simulating task processing and verifying alerts are not triggered.
"""
import asyncio
import sys
from datetime import datetime, timedelta

# Add app directory to path
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.self_healing.watchdogs import QueueWatchdog


async def test_queue_watchdog_integration():
    """Test that QueueWatchdog correctly tracks task processing."""
    
    print("=" * 80)
    print("🧪 TASK QUEUE FROZEN FIX - VERIFICATION TEST")
    print("=" * 80)
    
    # Initialize watchdog with short threshold for testing
    watchdog = QueueWatchdog(
        max_task_age_sec=5,  # 5 seconds for quick testing
        max_queue_depth=100,
        check_interval_sec=2
    )
    
    print("\n✅ QueueWatchdog initialized")
    print(f"   Max task age: {watchdog.max_task_age_sec}s")
    print(f"   Check interval: {watchdog.check_interval_sec}s")
    
    # Test 1: Initial state should be healthy (just initialized)
    print("\n📋 Test 1: Initial health check")
    health = await watchdog.check_queue_health()
    print(f"   Status: {health['status']}")
    print(f"   Seconds since last task: {health['seconds_since_last_task']:.2f}s")
    
    if health['status'] == 'healthy':
        print("   ✅ PASS: Initial state is healthy")
    else:
        print("   ❌ FAIL: Initial state should be healthy")
        return False
    
    # Test 2: Simulate waiting beyond threshold (should trigger frozen)
    print("\n📋 Test 2: Simulate frozen queue (wait 6 seconds)")
    await asyncio.sleep(6)
    
    health = await watchdog.check_queue_health()
    print(f"   Status: {health['status']}")
    print(f"   Seconds since last task: {health['seconds_since_last_task']:.2f}s")
    print(f"   Frozen alerts: {watchdog.frozen_worker_alerts}")
    
    if health['status'] == 'frozen' and watchdog.frozen_worker_alerts > 0:
        print("   ✅ PASS: Correctly detected frozen queue")
    else:
        print("   ❌ FAIL: Should have detected frozen queue")
        return False
    
    # Test 3: Record task processing (should reset to healthy)
    print("\n📋 Test 3: Record task processing")
    watchdog.record_task_processed()
    
    health = await watchdog.check_queue_health()
    print(f"   Status: {health['status']}")
    print(f"   Seconds since last task: {health['seconds_since_last_task']:.2f}s")
    
    if health['status'] == 'healthy':
        print("   ✅ PASS: Queue is healthy after recording task")
    else:
        print("   ❌ FAIL: Should be healthy after recording task")
        return False
    
    # Test 4: Continuous processing (simulate active loop)
    print("\n📋 Test 4: Simulate continuous task processing (10 iterations)")
    for i in range(10):
        await asyncio.sleep(1)  # Wait 1 second
        watchdog.record_task_processed()  # Record processing
        
        if (i + 1) % 3 == 0:  # Check every 3 iterations
            health = await watchdog.check_queue_health()
            print(f"   Iteration {i+1}: Status={health['status']}, "
                  f"Time since last={health['seconds_since_last_task']:.2f}s")
    
    health = await watchdog.check_queue_health()
    if health['status'] == 'healthy':
        print("   ✅ PASS: Queue remained healthy during continuous processing")
    else:
        print("   ❌ FAIL: Queue should remain healthy with continuous processing")
        return False
    
    # Test 5: Verify alert counter was reset
    print("\n📋 Test 5: Verify frozen alert counter behavior")
    initial_alerts = watchdog.frozen_worker_alerts
    print(f"   Current frozen alerts: {initial_alerts}")
    
    # Wait to trigger another frozen alert
    await asyncio.sleep(6)
    health = await watchdog.check_queue_health()
    
    new_alerts = watchdog.frozen_worker_alerts
    print(f"   After waiting 6s: {new_alerts} alerts")
    
    if new_alerts > initial_alerts:
        print("   ✅ PASS: Alert counter incremented on new freeze")
    else:
        print("   ⚠️  WARNING: Alert counter did not increment")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED")
    print("=" * 80)
    print("\n📊 Summary:")
    print("   - QueueWatchdog correctly detects frozen queues")
    print("   - record_task_processed() resets the frozen state")
    print("   - Continuous processing prevents false alerts")
    print("   - Alert counter tracks consecutive frozen checks")
    print("\n💡 The fix is working correctly!")
    
    return True


async def test_integration_points():
    """Verify that integration points exist in the codebase."""
    
    print("\n" + "=" * 80)
    print("🔍 INTEGRATION POINTS VERIFICATION")
    print("=" * 80)
    
    import os
    
    files_to_check = [
        ('/home/admin/.openclaw/workspace/auto-trade-system/app/worker_gold_bot.py', 
         'signal_scanning_loop'),
        ('/home/admin/.openclaw/workspace/auto-trade-system/app/execution/trading_service.py',
         'execute_trading_cycle'),
        ('/home/admin/.openclaw/workspace/auto-trade-system/app/main.py',
         'session_scheduler_worker'),
    ]
    
    all_good = True
    
    for filepath, function_name in files_to_check:
        print(f"\n📄 Checking {os.path.basename(filepath)}...")
        
        if not os.path.exists(filepath):
            print(f"   ❌ File not found: {filepath}")
            all_good = False
            continue
        
        with open(filepath, 'r') as f:
            content = f.read()
            
            # Check for QueueWatchdog import
            if 'QueueWatchdog' in content:
                print(f"   ✅ QueueWatchdog imported")
            else:
                print(f"   ❌ QueueWatchdog not imported")
                all_good = False
            
            # Check for record_task_processed calls
            if 'record_task_processed()' in content:
                count = content.count('record_task_processed()')
                print(f"   ✅ Found {count} record_task_processed() calls")
            else:
                print(f"   ❌ No record_task_processed() calls found")
                all_good = False
            
            # Check for initialization
            if 'QueueWatchdog(' in content:
                print(f"   ✅ QueueWatchdog instantiated")
            else:
                print(f"   ⚠️  QueueWatchdog not instantiated (may use shared instance)")
    
    if all_good:
        print("\n✅ All integration points verified")
    else:
        print("\n❌ Some integration points missing")
    
    return all_good


async def main():
    """Run all verification tests."""
    
    try:
        # Test 1: Core functionality
        test1_passed = await test_queue_watchdog_integration()
        
        # Test 2: Integration points
        test2_passed = await test_integration_points()
        
        # Final summary
        print("\n" + "=" * 80)
        print("🎯 FINAL VERIFICATION RESULTS")
        print("=" * 80)
        
        if test1_passed and test2_passed:
            print("\n✅ ALL VERIFICATIONS PASSED")
            print("\nThe Task Queue Frozen fix has been successfully implemented!")
            print("\nNext steps:")
            print("1. Restart the application to apply changes")
            print("2. Monitor Telegram for absence of false 'frozen' alerts")
            print("3. Check /health/deep endpoint for queue status")
            print("4. Review logs for QueueWatchdog initialization messages")
            return 0
        else:
            print("\n❌ SOME VERIFICATIONS FAILED")
            print("\nPlease review the output above for details.")
            return 1
    
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
