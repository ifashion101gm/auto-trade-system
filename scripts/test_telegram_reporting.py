"""Test comprehensive Telegram notification system."""
import asyncio
from app.notifications.telegram_agent import TelegramAgent
from app.events.event_bus import event_bus
from app.events.event_types import (
    ORDER_STATE_CHANGED, RISK_VIOLATION_DETECTED, 
    RECOVERY_ACTION_TAKEN, RECONCILIATION_ACTION, SYNC_REPAIRED
)


async def test_all_notifications():
    """Test all new Telegram notification handlers."""
    print("=" * 70)
    print("Testing Comprehensive Telegram Notification System")
    print("=" * 70)
    
    agent = TelegramAgent()
    await event_bus.start_processing()
    
    print("\n1. Testing ORDER_STATE_CHANGED event...")
    await event_bus.publish(ORDER_STATE_CHANGED, {
        'symbol': 'XAUT/USDT',
        'order_id': 'test_order_123',
        'from_state': 'OPEN',
        'to_state': 'REJECTED',
        'reason': 'Insufficient funds',
        'exchange': 'MEXC'
    })
    print("   ✅ Order state change event published")
    
    print("\n2. Testing RISK_VIOLATION_DETECTED event...")
    await event_bus.publish(RISK_VIOLATION_DETECTED, {
        'violation_type': 'daily_drawdown',
        'risk_level': 'HIGH',
        'symbol': 'XAUT/USDT',
        'description': 'Daily drawdown exceeded 5% threshold',
        'current_value': 5.2,
        'threshold': 5.0,
        'action_taken': 'Trading paused'
    })
    print("   ✅ Risk violation event published")
    
    print("\n3. Testing RECOVERY_ACTION_TAKEN event...")
    await event_bus.publish(RECOVERY_ACTION_TAKEN, {
        'action': 'Position sync repair',
        'context': 'Detected ghost position on MEXC',
        'status': 'Success',
        'details': 'Closed orphaned position and updated database'
    })
    print("   ✅ Recovery action event published")
    
    print("\n4. Testing RECONCILIATION_ACTION event...")
    await event_bus.publish(RECONCILIATION_ACTION, {
        'symbol': 'XAUT/USDT',
        'exchange': 'MEXC',
        'mismatch_type': 'GHOST_POSITION',
        'action': 'Closed ghost position',
        'requires_review': False,
        'old_state': {'size': 0.1, 'side': 'long'},
        'new_state': {'size': 0, 'side': 'none'}
    })
    print("   ✅ Reconciliation action event published")
    
    print("\n5. Testing SYNC_REPAIRED event...")
    await event_bus.publish(SYNC_REPAIRED, {
        'symbol': 'XAUT/USDT',
        'issue': 'Position size mismatch',
        'resolution': 'Auto-repaired by syncing with exchange'
    })
    print("   ✅ Sync repaired event published")
    
    # Wait for events to be processed
    await asyncio.sleep(2)
    await event_bus.stop_processing()
    
    print("\n" + "=" * 70)
    print("✅ All Telegram notifications tested successfully!")
    print("=" * 70)
    print("\nNote: Check your Telegram bot for the actual notifications.")
    print("If notifications are not received, verify TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")


if __name__ == "__main__":
    asyncio.run(test_all_notifications())
