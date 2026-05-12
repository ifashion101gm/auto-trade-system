# WebSocket Disconnection Notification Improvements

## Problem
The original implementation was sending repetitive "WEBSOCKET DISCONNECTED" notifications without:
1. Confirmation when the WebSocket successfully reconnects
2. Rate limiting to prevent spam during frequent disconnections
3. Detailed information about reconnection attempts

Example of the problematic notifications:
```
[5/11/2026 11:42 PM] AG trade report: ⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Attempting automatic reconnection...

[5/11/2026 11:43 PM] AG trade report: ⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Attempting automatic reconnection...
```

## Solution Implemented

### 1. Enhanced Disconnection Notifications
- Added attempt count to track reconnection attempts
- Included retry delay information
- Improved message clarity

**Before:**
```
⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Attempting automatic reconnection...
```

**After:**
```
⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Reconnect attempt #1
Next retry in: 2s

System will automatically attempt to reconnect.
```

### 2. Added Reconnection Confirmation
- New event handler for `WEBSOCKET_RECONNECTED` events
- Sends confirmation when WebSocket successfully reconnects
- Provides reassurance that the system is back online

**New Message:**
```
✅ WEBSOCKET RECONNECTED
WebSocket reconnected successfully

Trading system is back online and monitoring positions.
```

### 3. Rate Limiting
- Implemented 5-minute cooldown between disconnection notifications
- Prevents spam during periods of unstable connectivity
- Cooldown resets on successful reconnection
- Logs skipped notifications for debugging

### 4. Improved Event Data
- WebSocket manager now includes:
  - `attempt_count`: Number of reconnection attempts
  - `reconnect_delay`: Time until next retry
  - Better context for notification messages

## Files Modified

### 1. `app/agents/telegram_agent.py`
- Added import for `WEBSOCKET_RECONNECTED` event type
- Added subscription to `WEBSOCKET_RECONNECTED` events
- Enhanced `_on_websocket_disconnected()` with:
  - Rate limiting logic (5-minute cooldown)
  - Better message formatting with attempt count and retry delay
  - Logging of notification attempts
- Added new `_on_websocket_reconnected()` handler:
  - Sends confirmation message on successful reconnection
  - Resets the disconnect cooldown timer
  - Provides reassurance that trading is resumed

### 2. `app/exchange/websocket_manager.py`
- Enhanced `_handle_reconnect()` method:
  - Tracks reconnection attempts with `reconnect_attempts` counter
  - Includes attempt count and delay in disconnection event payload
  - Improved logging with attempt number
- Updated `connect()` method:
  - Resets `reconnect_delay` and `reconnect_attempts` on successful connection
  - Includes attempt count in reconnection event payload

### 3. `test_websocket_notifications.py` (New)
- Comprehensive test script to verify:
  - Disconnection event handling with rate limiting
  - Reconnection event handling
  - Cooldown mechanism
  - Cooldown reset on reconnection

## Configuration

The rate limiting cooldown can be adjusted in `app/agents/telegram_agent.py`:

```python
self._ws_disconnect_cooldown = 300  # 5 minutes cooldown between disconnect notifications
```

Change the value (in seconds) to adjust the cooldown period.

## Benefits

1. **Reduced Notification Spam**: Rate limiting prevents excessive notifications during unstable connections
2. **Better User Experience**: Clear indication of both disconnection and reconnection events
3. **Improved Monitoring**: Attempt counts help identify persistent connectivity issues
4. **System Confidence**: Reconnection confirmations reassure users that the system has recovered
5. **Debugging Support**: Detailed logs help troubleshoot connectivity issues

## Testing

Run the test script to verify the implementation:

```bash
source .venv/bin/activate
python test_websocket_notifications.py
```

Expected output shows:
- Disconnection notifications with attempt counts
- Reconnection confirmations
- Rate limiting in action (skipped notifications)
- Cooldown reset after reconnection

## Monitoring

Check logs for WebSocket-related events:

```bash
# Monitor WebSocket disconnections
grep "WebSocket disconnection alert sent" logs/app.log

# Monitor WebSocket reconnections
grep "WebSocket reconnection confirmation sent" logs/app.log

# Check for rate-limited notifications
grep "Skipping WebSocket disconnect notification" logs/app.log
```

## Future Enhancements

Potential improvements for future iterations:

1. **Adaptive Cooldown**: Increase cooldown period after repeated disconnections
2. **Severity Levels**: Different notification urgency based on disconnection frequency
3. **Dashboard Integration**: Show WebSocket status in web UI
4. **Alert Escalation**: Notify admin after N consecutive failed reconnection attempts
5. **Historical Tracking**: Log disconnection patterns for analysis
