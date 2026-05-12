# WebSocket Notification Quick Reference

## Problem Solved
Fixed repetitive "WEBSOCKET DISCONNECTED" notifications that were spamming Telegram without reconnection confirmations.

## What Changed

### Before ❌
```
[11:42 PM] ⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Attempting automatic reconnection...

[11:43 PM] ⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Attempting automatic reconnection...

[11:44 PM] ⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Attempting automatic reconnection...
```

### After ✅
```
[11:42 PM] ⚠️ WEBSOCKET DISCONNECTED
WebSocket disconnected, attempting reconnect
Reconnect attempt #1
Next retry in: 2s

System will automatically attempt to reconnect.

[11:43 PM] ✅ WEBSOCKET RECONNECTED
WebSocket reconnected successfully

Trading system is back online and monitoring positions.
```

## Key Features

1. **Rate Limiting**: Max 1 disconnection notification per 5 minutes
2. **Attempt Tracking**: Shows which reconnection attempt (#1, #2, etc.)
3. **Retry Info**: Displays next retry delay (2s, 4s, 8s, etc.)
4. **Reconnection Confirmation**: Notifies when system recovers
5. **Auto-Reset**: Cooldown resets after successful reconnection

## Configuration

Edit cooldown period in `app/agents/telegram_agent.py`:
```python
self._ws_disconnect_cooldown = 300  # seconds (default: 5 minutes)
```

## Testing

```bash
source .venv/bin/activate
python test_websocket_notifications.py
```

## Monitoring Commands

```bash
# Check disconnection alerts
grep "WebSocket disconnection alert sent" logs/app.log

# Check reconnection confirmations  
grep "WebSocket reconnection confirmation sent" logs/app.log

# Check rate-limited (skipped) notifications
grep "Skipping WebSocket disconnect notification" logs/app.log

# Monitor reconnection attempts
grep "Reconnecting in" logs/app.log
```

## Files Modified

- ✅ `app/agents/telegram_agent.py` - Enhanced notification handlers
- ✅ `app/exchange/websocket_manager.py` - Added attempt tracking
- ✅ `test_websocket_notifications.py` - New test script
- ✅ `WEBSOCKET_FIX_SUMMARY.md` - Detailed documentation
- ✅ `WEBSOCKET_NOTIFICATION_IMPROVEMENTS.md` - Full implementation guide

## Quick Troubleshooting

**Issue**: Still getting too many notifications
**Solution**: Increase cooldown period (e.g., change 300 to 600)

**Issue**: Not getting reconnection notifications
**Solution**: Check that `WEBSOCKET_RECONNECTED` event is being published (verify websocket_manager.py)

**Issue**: No notifications at all
**Solution**: Verify Telegram bot token is configured in `.env` file

## Expected Behavior Summary

| Scenario | Notification Sent? | Notes |
|----------|-------------------|-------|
| First disconnection | ✅ Yes | Shows attempt #1 |
| Second disconnection (< 5 min) | ❌ No | Rate limited, logged only |
| After 5 minutes | ✅ Yes | Cooldown expired |
| Successful reconnection | ✅ Yes | Always notified |
| After reconnection | ✅ Yes | Cooldown reset |
