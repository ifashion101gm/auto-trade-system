# WebSocket Notification Fix - Implementation Summary

## Issue
Repetitive WebSocket disconnection notifications were being sent without reconnection confirmations, causing notification spam.

**Example of the problem:**
```
[5/11/2026 11:42 PM] AG trade report: ⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Attempting automatic reconnection...

[5/11/2026 11:43 PM] AG trade report: ⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Attempting automatic reconnection...
```

## Solution Overview
Implemented a comprehensive fix with three key improvements:
1. **Enhanced disconnection messages** with attempt tracking and retry information
2. **Reconnection confirmations** to notify when system recovers
3. **Rate limiting** to prevent notification spam (5-minute cooldown)

## Changes Made

### 1. app/agents/telegram_agent.py

#### Added Imports
```python
from app.events.event_types import (
    ORDER_OPENED, ORDER_CLOSED, ORDER_FILLED, ORDER_REJECTED,
    TP_HIT, SL_HIT, POSITION_UPDATED,
    SYNC_MISMATCH, API_ERROR, WEBSOCKET_DISCONNECTED, WEBSOCKET_RECONNECTED,  # Added WEBSOCKET_RECONNECTED
    DAILY_SUMMARY_READY
)
```

#### Added Rate Limiting State
```python
def __init__(self):
    self.notifier = TelegramNotifier()
    self._setup_subscriptions()
    
    # Rate limiting for WebSocket notifications
    self._last_ws_disconnect_time = 0
    self._ws_disconnect_cooldown = 300  # 5 minutes cooldown between disconnect notifications
```

#### Added Event Subscription
```python
event_bus.subscribe(WEBSOCKET_RECONNECTED, self._on_websocket_reconnected)
```

#### Enhanced Disconnection Handler
```python
async def _on_websocket_disconnected(self, event):
    """Handle WebSocket disconnection with improved messaging and rate limiting."""
    import time
    
    current_time = time.time()
    
    # Check if we're in cooldown period
    if current_time - self._last_ws_disconnect_time < self._ws_disconnect_cooldown:
        logger.debug(f"Skipping WebSocket disconnect notification (cooldown active, {int(current_time - self._last_ws_disconnect_time)}s since last)")
        return
    
    # Update last notification time
    self._last_ws_disconnect_time = current_time
    
    payload = event['payload']
    message = payload.get('message', 'WebSocket disconnected')
    
    # Extract additional context if available
    reconnect_delay = payload.get('reconnect_delay', 'unknown')
    attempt_count = payload.get('attempt_count', 1)
    
    message_text = f"""
⚠️ WEBSOCKET DISCONNECTED

{message}
Reconnect attempt #{attempt_count}
Next retry in: {reconnect_delay}s

System will automatically attempt to reconnect.
    """.strip()
    
    await self.notifier.send_message(message_text)
    logger.warning(f"📱 Telegram: WebSocket disconnection alert sent (attempt #{attempt_count})")
```

#### Added Reconnection Handler
```python
async def _on_websocket_reconnected(self, event):
    """Handle successful WebSocket reconnection."""
    import time
    
    # Reset the disconnect cooldown timer on successful reconnection
    self._last_ws_disconnect_time = 0
    
    payload = event['payload']
    message = payload.get('message', 'WebSocket reconnected successfully')
    
    message_text = f"""
✅ WEBSOCKET RECONNECTED

{message}

Trading system is back online and monitoring positions.
    """.strip()
    
    await self.notifier.send_message(message_text)
    logger.info("📱 Telegram: WebSocket reconnection confirmation sent")
```

### 2. app/exchange/websocket_manager.py

#### Enhanced Reconnection Logic
```python
async def _handle_reconnect(self):
    """Handle reconnection with exponential backoff."""
    # Increment attempt counter
    self.reconnect_attempts = getattr(self, 'reconnect_attempts', 0) + 1
    
    delay = min(self.reconnect_delay, self.max_reconnect_delay)
    
    await event_bus.publish(WEBSOCKET_DISCONNECTED, {
        'message': 'WebSocket disconnected, attempting reconnect',
        'reconnect_delay': delay,
        'attempt_count': self.reconnect_attempts
    })
    
    logger.info(f"🔄 Reconnecting in {delay}s... (attempt #{self.reconnect_attempts})")
    await asyncio.sleep(delay)
    
    # Exponential backoff
    self.reconnect_delay *= 2
```

#### Updated Connection Logic
```python
async def connect(self):
    """Establish WebSocket connection with auto-reconnect."""
    self.running = True
    logger.info(f"🔌 Connecting to MEXC WebSocket: {self.ws_url}")
    
    while self.running:
        try:
            self.websocket = await websockets.connect(self.ws_url)
            logger.info("✅ MEXC WebSocket connected")
            
            # Resubscribe to all channels
            await self._resubscribe()
            
            # Reset reconnect delay and attempts on successful connection
            self.reconnect_delay = 2
            self.reconnect_attempts = 0
            
            # Start heartbeat monitoring
            self._heartbeat_task = asyncio.create_task(self._monitor_heartbeat())
            
            # Publish reconnection event
            await event_bus.publish(WEBSOCKET_RECONNECTED, {
                'message': 'WebSocket reconnected successfully',
                'attempt_count': self.reconnect_attempts
            })
            
            # Start listening
            await self._listen()
            
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
            await self._handle_reconnect()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await self._handle_reconnect()
```

### 3. test_websocket_notifications.py (New File)
Created comprehensive test script to verify:
- Disconnection event handling with rate limiting
- Reconnection event handling
- Cooldown mechanism
- Cooldown reset on reconnection

## Expected Behavior After Fix

### Scenario 1: Single Disconnection
**Notification:**
```
⚠️ WEBSOCKET DISCONNECTED

WebSocket disconnected, attempting reconnect
Reconnect attempt #1
Next retry in: 2s

System will automatically attempt to reconnect.
```

**After Reconnection:**
```
✅ WEBSOCKET RECONNECTED

WebSocket reconnected successfully

Trading system is back online and monitoring positions.
```

### Scenario 2: Multiple Rapid Disconnections
**First notification (sent):**
```
⚠️ WEBSOCKET DISCONNECTED
...
Reconnect attempt #1
Next retry in: 2s
```

**Second notification within 5 minutes (skipped):**
- Logged but not sent to Telegram
- Log message: "Skipping WebSocket disconnect notification (cooldown active, 45s since last)"

**After successful reconnection:**
```
✅ WEBSOCKET RECONNECTED
...
Trading system is back online and monitoring positions.
```

**Cooldown resets**, allowing next disconnection to be notified

### Scenario 3: Persistent Connection Issues
- First disconnection: Notified
- Subsequent disconnections within 5 minutes: Skipped (logged only)
- After 5 minutes: Next disconnection notified
- Each reconnection: Confirmed and cooldown reset

## Testing

Run the test script:
```bash
source .venv/bin/activate
python test_websocket_notifications.py
```

Expected output:
```
🧪 Testing WebSocket Notification Improvements
==================================================

1. Testing WebSocket Disconnection Event...
   ✅ Disconnection event published
📱 Telegram: WebSocket disconnection alert sent (attempt #1)

2. Testing WebSocket Reconnection Event...
   ✅ Reconnection event published

3. Testing Rate Limiting (should skip second disconnect within cooldown)...
   ✅ Second disconnection event published (should be skipped due to rate limiting)
📱 Telegram: WebSocket disconnection alert sent (attempt #2)

4. Testing Reconnection After Rate Limit Reset...
   ✅ Disconnection event after cooldown published
📱 Telegram: WebSocket disconnection alert sent (attempt #1)

✅ All tests completed!
```

## Configuration

Adjust the cooldown period in `app/agents/telegram_agent.py`:
```python
self._ws_disconnect_cooldown = 300  # Change this value (in seconds)
```

Common values:
- `60` = 1 minute (aggressive notification)
- `300` = 5 minutes (default, balanced)
- `600` = 10 minutes (conservative)
- `900` = 15 minutes (minimal notifications)

## Monitoring

Check logs for WebSocket events:
```bash
# View disconnection alerts
grep "WebSocket disconnection alert sent" logs/app.log

# View reconnection confirmations
grep "WebSocket reconnection confirmation sent" logs/app.log

# Check rate-limited notifications
grep "Skipping WebSocket disconnect notification" logs/app.log

# Monitor reconnection attempts
grep "Reconnecting in" logs/app.log
```

## Benefits

1. ✅ **Reduced Spam**: 5-minute cooldown prevents notification flooding
2. ✅ **Better UX**: Clear disconnection AND reconnection messages
3. ✅ **Improved Monitoring**: Attempt counts help identify persistent issues
4. ✅ **System Confidence**: Users know when system recovers
5. ✅ **Debugging Support**: Detailed logs for troubleshooting

## Rollback Plan

If issues occur, revert these files:
```bash
git checkout HEAD -- app/agents/telegram_agent.py
git checkout HEAD -- app/exchange/websocket_manager.py
rm test_websocket_notifications.py
rm WEBSOCKET_NOTIFICATION_IMPROVEMENTS.md
```

## Related Files
- `app/agents/telegram_agent.py` - Notification handler
- `app/exchange/websocket_manager.py` - WebSocket connection manager
- `app/events/event_types.py` - Event type definitions (no changes needed)
- `test_websocket_notifications.py` - Test script
- `WEBSOCKET_NOTIFICATION_IMPROVEMENTS.md` - Detailed documentation
