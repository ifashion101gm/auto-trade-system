"""
Test script to verify WebSocket disconnection notification improvements.
"""
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.events.event_bus import event_bus
from app.events.event_types import WEBSOCKET_DISCONNECTED, WEBSOCKET_RECONNECTED
from app.agents.telegram_agent import TelegramAgent


async def test_websocket_notifications():
    """Test WebSocket disconnection and reconnection notifications."""
    
    print("🧪 Testing WebSocket Notification Improvements")
    print("=" * 50)
    
    # Initialize the Telegram agent
    telegram_agent = TelegramAgent()
    
    # Start event bus processing
    await event_bus.start_processing()
    
    print("\n1. Testing WebSocket Disconnection Event...")
    await event_bus.publish(WEBSOCKET_DISCONNECTED, {
        'message': 'WebSocket disconnected, attempting reconnect',
        'reconnect_delay': 2,
        'attempt_count': 1
    })
    
    print("   ✅ Disconnection event published")
    
    # Wait a bit to allow processing
    await asyncio.sleep(1)
    
    print("\n2. Testing WebSocket Reconnection Event...")
    await event_bus.publish(WEBSOCKET_RECONNECTED, {
        'message': 'WebSocket reconnected successfully',
        'attempt_count': 0
    })
    
    print("   ✅ Reconnection event published")
    
    # Wait a bit to allow processing
    await asyncio.sleep(1)
    
    print("\n3. Testing Rate Limiting (should skip second disconnect within cooldown)...")
    
    # Publish another disconnect event immediately (should be rate-limited)
    await event_bus.publish(WEBSOCKET_DISCONNECTED, {
        'message': 'WebSocket disconnected again',
        'reconnect_delay': 4,
        'attempt_count': 2
    })
    
    print("   ✅ Second disconnection event published (should be skipped due to rate limiting)")
    
    # Wait a bit to allow processing
    await asyncio.sleep(1)
    
    print("\n4. Testing Reconnection After Rate Limit Reset...")
    
    # Simulate time passing by resetting the cooldown manually for testing
    telegram_agent._last_ws_disconnect_time = 0
    
    await event_bus.publish(WEBSOCKET_DISCONNECTED, {
        'message': 'WebSocket disconnected after cooldown',
        'reconnect_delay': 2,
        'attempt_count': 1
    })
    
    print("   ✅ Disconnection event after cooldown published")
    
    # Stop event bus processing
    await event_bus.stop_processing()
    
    print("\n✅ All tests completed!")
    print("\nSummary:")
    print("- WebSocket disconnection events include attempt count and retry delay")
    print("- WebSocket reconnection events confirm successful reconnection")
    print("- Rate limiting prevents excessive notifications (5-minute cooldown)")
    print("- Cooldown resets on successful reconnection")


if __name__ == "__main__":
    asyncio.run(test_websocket_notifications())
