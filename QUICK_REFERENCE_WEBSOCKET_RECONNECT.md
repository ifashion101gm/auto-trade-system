# WebSocket Auto Reconnect Engine - Quick Reference

## Configuration (app/config.py)

```python
WEBSOCKET_HEARTBEAT_INTERVAL = 30        # Ping every 30s
WEBSOCKET_HEARTBEAT_TIMEOUT = 45         # Timeout after 45s without pong
WEBSOCKET_RECONNECT_DELAY = 2            # Initial reconnect delay
WEBSOCKET_MAX_RECONNECT_DELAY = 60       # Max delay cap
WEBSOCKET_MAX_RECONNECT_ATTEMPTS = 0     # 0 = unlimited retries
WEBSOCKET_STALE_STREAM_THRESHOLD = 120   # Force reconnect if no data for 120s
WEBSOCKET_JITTER_FACTOR = 0.1            # Add 0-10% random jitter
```

---

## Key Features

### 1. Heartbeat Monitoring
- **Ping frequency:** Every 30 seconds
- **Timeout:** 45 seconds without pong → forces reconnect
- **Failure handling:** Immediate reconnect if ping fails

### 2. Stale Stream Detection
- **Check interval:** Every 60 seconds
- **Threshold:** 120 seconds without any messages
- **Action:** Forces reconnect even if connection is technically alive
- **Catches:** Silent failures where exchange stops sending data

### 3. Exponential Backoff with Jitter
```
Attempt 1: 2.0s + jitter (0-0.2s) = 2.0-2.2s
Attempt 2: 4.0s + jitter (0-0.4s) = 4.0-4.4s
Attempt 3: 8.0s + jitter (0-0.8s) = 8.0-8.8s
Attempt 4: 16.0s + jitter = 16.0-17.6s
Attempt 5: 32.0s + jitter = 32.0-35.2s
Attempt 6+: 60.0s + jitter = 60.0-66.0s (capped)
```

**Why jitter?** Prevents thundering herd when multiple clients reconnect simultaneously.

### 4. State Recovery
- **Trigger:** `WEBSOCKET_RECONNECTED` event
- **Handler:** `PositionSyncService._on_websocket_reconnected()`
- **Action:** Runs immediate `sync_once()` to reconcile state
- **Result:** Zero drift after reconnection

---

## Metrics (get_metrics())

```python
{
    'connected': True/False,
    'subscriptions_count': 3,
    'avg_message_latency_ms': 45.2,
    'last_heartbeat_age_s': 12.5,
    'last_message_age_s': 2.3,           # ← Stale stream indicator
    'use_rest_fallback': False,
    'reconnect_attempts': 0,
    'disconnect_count': 3,
    'total_downtime_seconds': 15.7,
    'uptime_seconds': 3456.2,
    'stale_stream_threshold_s': 120
}
```

---

## Monitoring Alerts

### Critical Alerts
```
IF last_message_age_s > 120s → Stale stream detected (investigate immediately)
IF reconnect_attempts > 10 in 1 hour → Unstable connection
IF total_downtime_seconds / uptime_seconds > 1% → Poor reliability
```

### Warning Alerts
```
IF reconnect_attempts > 5 in 1 hour → Frequent disconnections
IF avg_message_latency_ms > 1000ms → Network congestion
```

---

## Troubleshooting

### Problem: Frequent Reconnections
**Symptoms:** `disconnect_count` increasing rapidly  
**Causes:**
1. Network instability
2. Exchange maintenance
3. Firewall blocking WebSocket

**Actions:**
```bash
# Check network connectivity
ping contract.mexc.com

# Check firewall rules
iptables -L | grep websocket

# Review logs
grep "WebSocket" logs/app.log | tail -50
```

---

### Problem: Stale Streams
**Symptoms:** `last_message_age_s` > 120s but `connected` = True  
**Cause:** Exchange stopped sending data but kept connection alive  

**Actions:**
1. System auto-recovers (forces reconnect)
2. If persistent, check MEXC status page
3. Consider switching to REST fallback temporarily

---

### Problem: High Latency
**Symptoms:** `avg_message_latency_ms` > 500ms  
**Causes:**
1. Network congestion
2. Server overload
3. Geographic distance

**Actions:**
```bash
# Test latency to exchange
curl -o /dev/null -s -w '%{time_total}' https://contract.mexc.com

# Check system load
top -bn1 | head -5

# Consider moving server closer to exchange (e.g., AWS Tokyo for MEXC)
```

---

## Testing

### Run Verification Tests
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python test_websocket_reconnect.py
```

**Expected Output:**
```
✅ PASS: Configuration Parameters
✅ PASS: Manager Initialization
✅ PASS: Metrics Structure
✅ PASS: Backoff Calculation
✅ PASS: Event Subscriptions

Overall: 5/5 tests passed
🎉 All tests passed! Auto Reconnect Engine is ready.
```

---

## Architecture Flow

```
┌─────────────────────────────────────────────┐
│         Application Startup                  │
│                                              │
│  1. exchange.connect()                       │
│     └→ Validates REST API connectivity       │
│                                              │
│  2. sync_agent.start_listening()             │
│     └→ Starts MEXCWebSocketManager           │
│        ├→ _monitor_heartbeat()               │
│        └→ _detect_stale_streams()            │
│                                              │
│  3. position_sync_service.start()            │
│     └→ Periodic sync (every 5s)              │
│     └→ Listens to WEBSOCKET_RECONNECTED      │
└──────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│         Disconnection Detected               │
│                                              │
│  Trigger:                                    │
│  - Connection closed                         │
│  - Heartbeat timeout                         │
│  - Stale stream (>120s no data)              │
│  - Ping failure                              │
│                                              │
│  Action:                                     │
│  1. Publish WEBSOCKET_DISCONNECTED event     │
│  2. Calculate backoff delay + jitter         │
│  3. Wait (exponential backoff)               │
│  4. Attempt reconnect                        │
└──────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│         Reconnection Success                 │
│                                              │
│  1. WebSocket connected                      │
│  2. Resubscribe to channels                  │
│  3. Restart background tasks                 │
│  4. Publish WEBSOCKET_RECONNECTED event      │
│                                              │
│  PositionSyncService receives event:         │
│  ├→ Triggers immediate sync_once()           │
│  ├→ Fetches current positions from exchange  │
│  ├→ Compares with database                   │
│  └→ Repairs any mismatches                   │
│                                              │
│  Result: Zero state drift                    │
└──────────────────────────────────────────────┘
```

---

## Tuning Guide

### Production (Conservative)
```python
WEBSOCKET_HEARTBEAT_INTERVAL = 30
WEBSOCKET_HEARTBEAT_TIMEOUT = 45
WEBSOCKET_STALE_STREAM_THRESHOLD = 120
WEBSOCKET_JITTER_FACTOR = 0.1
```

### Low-Latency Trading (Aggressive)
```python
WEBSOCKET_HEARTBEAT_INTERVAL = 10
WEBSOCKET_HEARTBEAT_TIMEOUT = 15
WEBSOCKET_STALE_STREAM_THRESHOLD = 60
WEBSOCKET_JITTER_FACTOR = 0.05
```

### Development/Testing
```python
WEBSOCKET_STALE_STREAM_THRESHOLD = 30  # Faster detection
WEBSOCKET_MAX_RECONNECT_ATTEMPTS = 5   # Limit for quicker test cycles
```

---

## Related Documentation

- **Full Implementation Details:** `WEBSOCKET_AUTO_RECONNECT_ENGINE.md`
- **Audit Report:** `EXCHANGE_EXECUTION_LAYER_AUDIT.md`
- **Implementation Summary:** `IMPLEMENTATION_SUMMARY_COMPLETE.md`
- **Test Script:** `test_websocket_reconnect.py`

---

**Last Updated:** May 12, 2026  
**Status:** ✅ Production Ready  
**Version:** 1.0
