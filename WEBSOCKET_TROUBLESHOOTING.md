# WebSocket Troubleshooting Guide

## Problem
MEXC WebSocket experiencing persistent disconnections with 160+ reconnect attempts over ~2.7 hours.

---

## Immediate Actions Taken ✅

### 1. Diagnostic Script Created
**File:** `scripts/diagnose_websocket.py`

This script performs comprehensive diagnostics:
- API credential validation
- REST API connectivity test  
- WebSocket connection test
- Subscription & message reception test
- Network latency measurement
- Firewall/port check

**Usage:**
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python scripts/diagnose_websocket.py
```

### 2. Enhanced Error Logging
**File:** `app/websocket/manager.py`

Added detailed logging for:
- Connection closed codes and reasons
- HTTP status codes on rejection (301, 403, etc.)
- Full exception tracebacks
- Reconnect attempt details with timing breakdown
- Circuit breaker status

**What you'll see in logs now:**
```
⚠️  WEBSOCKET DISCONNECTED
============================================================
Reconnect attempt #161
Base delay: 2s
Calculated delay: 60.0s (capped at 60s)
Jitter: 3.2s (10%)
Next retry in: 63.2s
Total disconnects so far: 161
Circuit breaker: ACTIVE 🚨
============================================================
```

### 3. Circuit Breaker Implementation
**Threshold:** 50 consecutive failures

When activated:
- Sends Telegram alert with diagnostic instructions
- Logs critical error with emoji markers
- Continues retrying (doesn't stop the system)
- Resets automatically on successful reconnect
- Alert cooldown: 1 hour (prevents spam)

**Telegram Alert Example:**
```
🚨 WEBSOCKET CIRCUIT BREAKER ACTIVATED

MEXC WebSocket has failed 50 consecutive reconnection attempts.

This indicates a persistent issue:
• Invalid API credentials
• Firewall blocking WSS connections
• MEXC service outage
• IP address banned

Action required: Run diagnostic script
`python scripts/diagnose_websocket.py`

System will continue retrying but you should investigate.
```

### 4. REST Polling Fallback (Future Enhancement)
Currently declared but not fully implemented. Can be added if needed for critical position monitoring during extended outages.

---

## Root Cause Analysis

Based on the diagnostic output showing **HTTP 301 redirect**, the most likely causes are:

### 🔴 High Probability:
1. **MEXC WebSocket URL Changed** - The endpoint `wss://contract.mexc.com/ws` may have been deprecated or moved
2. **Firewall/Proxy Blocking** - VPS firewall or ISP blocking WSS connections on port 443
3. **IP Address Banned** - Too many rapid reconnections triggered rate limiting

### 🟡 Medium Probability:
4. **Invalid API Credentials** - Expired or revoked API keys
5. **MEXC Service Outage** - Temporary exchange maintenance

### 🟢 Low Probability:
6. **DNS Resolution Issues** - Incorrect DNS resolving to wrong IP
7. **Network Configuration** - Routing issues on VPS

---

## Step-by-Step Troubleshooting

### Step 1: Run Diagnostic Script
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python scripts/diagnose_websocket.py
```

**Expected Output:**
- ✅ All tests pass → Issue resolved
- ❌ API credentials fail → Check .env file
- ❌ WebSocket connection fails → Check firewall/network
- ⚠️ Subscription inconclusive → May need authentication

### Step 2: Check API Credentials
```bash
# Verify credentials are set
grep MEXC_API /home/admin/.openclaw/workspace/auto-trade-system/.env

# Test credentials manually
python -c "from app.config import settings; print('Key:', settings.MEXC_API_KEY[:8] + '***' if settings.MEXC_API_KEY else 'NOT SET')"
```

**If invalid:**
1. Log into MEXC account
2. Generate new API key with futures trading permissions
3. Update `.env` file
4. Restart service: `sudo systemctl restart vmassit.service`

### Step 3: Check Firewall Rules
```bash
# Check current firewall status
sudo ufw status

# Allow outbound WSS (port 443)
sudo ufw allow out 443/tcp

# Reload firewall
sudo ufw reload

# Verify
sudo ufw status verbose
```

### Step 4: Test Network Connectivity
```bash
# Test DNS resolution
nslookup contract.mexc.com

# Test TCP connection
timeout 5 bash -c 'echo > /dev/tcp/contract.mexc.com/443' && echo "Port 443 OPEN" || echo "Port 443 BLOCKED"

# Test from different network (if possible)
# Try connecting from your local machine to rule out VPS-specific issues
```

### Step 5: Check MEXC Status
Visit: https://status.mexc.com or check MEXC Twitter for outage announcements

### Step 6: Restart Service
```bash
# Stop service
sudo systemctl stop vmassit.service

# Wait 10 seconds
sleep 10

# Start service
sudo systemctl start vmassit.service

# Monitor logs
sudo journalctl -u vmassit.service -f --since "2 minutes ago"
```

---

## If Problem Persists

### Option A: Switch to Binance
If MEXC continues having issues, consider switching to Binance which has more stable infrastructure:

```bash
# Edit .env
ACTIVE_EXCHANGE=binance
BINANCE_TESTNET=true  # or false for live

# Restart
sudo systemctl restart vmassit.service
```

### Option B: Implement REST Polling Fallback
I can implement a REST API polling mechanism that:
- Activates after 100 WebSocket failures
- Polls positions every 30 seconds via REST
- Maintains position sync without WebSocket
- Automatically switches back when WebSocket recovers

Let me know if you want this implemented.

### Option C: Contact MEXC Support
If all else fails:
- Email: support@mexc.com
- Include: Your IP address, API key (first 8 chars), error logs
- Request: WebSocket connectivity troubleshooting

---

## Monitoring Commands

### Watch Logs in Real-Time
```bash
sudo journalctl -u vmassit.service -f | grep -i websocket
```

### Check Service Status
```bash
sudo systemctl status vmassit.service
```

### View Recent Disconnects
```bash
sudo journalctl -u vmassit.service --since "1 hour ago" | grep "WEBSOCKET DISCONNECTED" | wc -l
```

### Check Circuit Breaker Status
```bash
sudo journalctl -u vmassit.service --since "30 minutes ago" | grep "CIRCUIT BREAKER"
```

---

## Prevention

### 1. Rate Limit Reconnections
Current config already implements exponential backoff with max 60s delay.

### 2. Add Health Check Endpoint
Consider adding a `/health` endpoint that reports WebSocket status for external monitoring.

### 3. Set Up External Monitoring
Use services like UptimeRobot or Pingdom to monitor your trading bot's health endpoint.

### 4. Regular Credential Rotation
Rotate API keys every 90 days as security best practice.

---

## Summary of Changes Made

| File | Change | Purpose |
|------|--------|---------|
| `scripts/diagnose_websocket.py` | NEW | Comprehensive diagnostic tool |
| `app/websocket/manager.py` | Enhanced logging | Better error visibility |
| `app/websocket/manager.py` | Circuit breaker | Alert on persistent failures |
| `app/websocket/manager.py` | Detailed reconnect info | Debug timing and delays |

All changes are backward compatible and don't require configuration updates.

---

## Next Steps

1. **Run diagnostic script** to identify exact failure point
2. **Check logs** for enhanced error messages
3. **Verify firewall** allows outbound port 443
4. **Test API credentials** are valid
5. **Monitor circuit breaker** alerts via Telegram

The system will continue retrying automatically, but now you have better visibility and tools to diagnose the root cause.
