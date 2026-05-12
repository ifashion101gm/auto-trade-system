#!/usr/bin/env python3
"""
Test script for enhanced Telegram notification methods.
Verifies that new alert methods work correctly.

Usage:
    python scripts/test_enhanced_notifications.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.notifications.notifier import TelegramNotifier
from app.logging_config import get_logger

logger = get_logger(__name__)


async def test_order_state_alert():
    """Test order state change notification."""
    print("\n" + "="*70)
    print("TEST 1: Order State Alert")
    print("="*70)
    
    notifier = TelegramNotifier()
    
    if not notifier.enabled:
        print("⚠️  Telegram notifications disabled (missing config)")
        print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False
    
    # Test critical state change (rejection)
    result = await notifier.send_order_state_alert(
        order_id="TEST_ORD_123456",
        symbol="XAUT/USDT",
        from_state="PENDING",
        to_state="REJECTED",
        trade_id="test-trade-uuid",
        details={
            "reason": "Insufficient balance",
            "requested_qty": 0.5,
            "available_balance": 50.00
        }
    )
    
    if result:
        print("✅ Critical order state alert sent successfully")
    else:
        print("❌ Failed to send critical order state alert")
    
    # Test normal state change (fill)
    result2 = await notifier.send_order_state_alert(
        order_id="TEST_ORD_789012",
        symbol="XAUT/USDT",
        from_state="PENDING",
        to_state="FILLED",
        trade_id="test-trade-uuid-2",
        details={
            "filled_price": 3350.00,
            "quantity": 0.5
        }
    )
    
    if result2:
        print("✅ Normal order state alert sent successfully")
    else:
        print("❌ Failed to send normal order state alert")
    
    return result and result2


async def test_reconciliation_alert():
    """Test reconciliation mismatch notification."""
    print("\n" + "="*70)
    print("TEST 2: Reconciliation Alert")
    print("="*70)
    
    notifier = TelegramNotifier()
    
    if not notifier.enabled:
        print("⚠️  Telegram notifications disabled")
        return False
    
    # Test auto-repaired mismatch
    result = await notifier.send_reconciliation_alert(
        action="closed_ghost_position",
        symbol="XAUT/USDT",
        exchange="MEXC",
        mismatch_type="GHOST_POSITION",
        old_state={"size": 0.5, "status": "open", "entry_price": 3350.00},
        new_state={"size": 0, "status": "closed"},
        requires_review=False
    )
    
    if result:
        print("✅ Auto-repair reconciliation alert sent successfully")
    else:
        print("❌ Failed to send auto-repair alert")
    
    # Test mismatch requiring review
    result2 = await notifier.send_reconciliation_alert(
        action="orphaned_order_detected",
        symbol="XAUT/USDT",
        exchange="MEXC",
        mismatch_type="ORPHANED_ORDER",
        old_state={"order_id": "ORD123", "status": "open"},
        new_state=None,
        requires_review=True
    )
    
    if result2:
        print("✅ Manual review reconciliation alert sent successfully")
    else:
        print("❌ Failed to send manual review alert")
    
    return result and result2


async def test_risk_violation_alert():
    """Test risk violation notification."""
    print("\n" + "="*70)
    print("TEST 3: Risk Violation Alert")
    print("="*70)
    
    notifier = TelegramNotifier()
    
    if not notifier.enabled:
        print("⚠️  Telegram notifications disabled")
        return False
    
    # Test critical risk violation
    result = await notifier.send_risk_violation_alert(
        violation_type="MAX_POSITION_EXCEEDED",
        symbol="XAUT/USDT",
        risk_level="CRITICAL",
        description="Total exposure exceeds maximum allowed limit",
        metrics={
            "current_exposure_usd": 5500.00,
            "max_allowed_usd": 5000.00,
            "excess_amount_usd": 500.00,
            "leverage": 10
        },
        action_taken="Trade rejected, position size reduced",
        trade_id="test-trade-uuid-3"
    )
    
    if result:
        print("✅ Critical risk violation alert sent successfully")
    else:
        print("❌ Failed to send critical risk violation alert")
    
    # Test medium risk violation
    result2 = await notifier.send_risk_violation_alert(
        violation_type="HIGH_CORRELATION",
        symbol="BTC/USDT",
        risk_level="MEDIUM",
        description="New position highly correlated with existing positions",
        metrics={
            "correlation_coefficient": 0.85,
            "existing_positions": 3,
            "max_allowed_correlation": 0.70
        },
        action_taken="Warning issued, monitoring increased",
        trade_id="test-trade-uuid-4"
    )
    
    if result2:
        print("✅ Medium risk violation alert sent successfully")
    else:
        print("❌ Failed to send medium risk violation alert")
    
    return result and result2


async def test_system_alert():
    """Test basic system alert (existing method)."""
    print("\n" + "="*70)
    print("TEST 4: System Alert (Baseline)")
    print("="*70)
    
    notifier = TelegramNotifier()
    
    if not notifier.enabled:
        print("⚠️  Telegram notifications disabled")
        return False
    
    result = await notifier.send_system_alert(
        title="System Health Check",
        message="All systems operational. Position sync running normally.",
        level="info"
    )
    
    if result:
        print("✅ System alert sent successfully")
    else:
        print("❌ Failed to send system alert")
    
    return result


async def main():
    """Run all notification tests."""
    print("\n" + "="*70)
    print("ENHANCED NOTIFICATION METHODS TEST")
    print("="*70)
    print(f"Timestamp: {asyncio.get_event_loop().time()}")
    
    results = []
    
    try:
        # Test 1: Order state alerts
        result1 = await test_order_state_alert()
        results.append(("Order State Alerts", result1))
        
        # Test 2: Reconciliation alerts
        result2 = await test_reconciliation_alert()
        results.append(("Reconciliation Alerts", result2))
        
        # Test 3: Risk violation alerts
        result3 = await test_risk_violation_alert()
        results.append(("Risk Violation Alerts", result3))
        
        # Test 4: System alerts (baseline)
        result4 = await test_system_alert()
        results.append(("System Alerts", result4))
        
        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} - {test_name}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All notification methods working correctly!")
            return True
        else:
            print(f"\n⚠️  {total - passed} test(s) failed. Check configuration.")
            return False
            
    except Exception as e:
        logger.error(f"Tests failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
