# MEXC to Bybit Migration - Configuration Changes

## Overview
All MEXC-related trading configurations, WebSocket connections, and background services have been disabled. The system now exclusively uses **Bybit Demo Trading** for all operations.

## Changes Made

### 1. Configuration (`app/config.py`)
- ✅ Set `ACTIVE_EXCHANGE = "bybit"` (changed from `"mexc"`)
- ✅ Commented out all MEXC API credential fields to prevent accidental usage
- ✅ Bybit Demo Trading credentials remain active and configured

### 2. Sync Agent (`app/sync/sync_agent.py`)
- ✅ Replaced `MEXCWebSocketManager` with `BybitConnector`
- ✅ Updated to use Bybit Demo Trading mode (`demo_trading=True`)
- ✅ Changed symbol subscription from `'XAUT/USDT'` to `'XAU/USDT:USDT'` (Bybit format)
- ✅ Added handler methods for Bybit WebSocket position and order updates

### 3. Position Sync Service (`app/sync/position_sync.py`)
- ✅ Already configured to use `BybitConnector(demo_trading=True)`
- ✅ Added explicit comments confirming Bybit-only operation
- ✅ Added initialization log message for clarity

### 4. Main Application (`app/main.py`)
- ✅ Updated sync agent initialization to use Bybit Gold symbol: `'XAU/USDT:USDT'`
- ✅ Updated log messages to reflect Bybit Demo Trading
- ✅ Position sync service confirmed using Bybit demo mode

## Current Configuration Status

### Active Exchange
- **Exchange**: Bybit Demo Trading
- **Domain**: `api-demo.bybit.com`
- **Symbol**: `XAU/USDT:USDT` (Gold perpetual swap)
- **API Keys**: Configured in `.env` file (lines 74-75)

### Disabled Components
- ❌ MEXC WebSocket Manager (`MEXCWebSocketManager`)
- ❌ MEXC API Client (`MEXCClient`)
- ❌ All MEXC background services
- ❌ MEXC diagnostic scripts (not auto-triggered)

### Remaining Active Services
- ✅ Bybit WebSocket connection (via `WebSocketManager` in `BybitConnector`)
- ✅ Position synchronization (every 5 seconds)
- ✅ Trade reconciliation (every 2 minutes)
- ✅ Event bus processing
- ✅ Telegram notifications

## Environment Variables (.env)

### Bybit Configuration (Active)
```bash
BYBIT_DEMO_API_KEY="BjNUnKliw5cSsChLJz"
BYBIT_DEMO_API_SECRET="ckQ4BdRV2d5a0r2TM0MebqDeTTg0fmopDloW"
BYBIT_USE_DEMO_DOMAIN=true
```

### MEXC Configuration (Disabled)
MEXC credentials remain in `.env` but are **NOT USED** by the application since:
1. `ACTIVE_EXCHANGE` is set to `"bybit"`
2. No code paths initialize MEXC clients when Bybit is active
3. MEXC config fields are commented out in `config.py`

## Restart Instructions

### Option 1: Using systemd (Recommended for Production)
```bash
# Stop the current service
sudo systemctl stop auto-trade-system

# Verify it's stopped
sudo systemctl status auto-trade-system

# Start with new configuration
sudo systemctl start auto-trade-system

# Check logs for any errors
sudo journalctl -u auto-trade-system -f --since "5 minutes ago"
```

### Option 2: Direct Python Execution (Development)
```bash
# Navigate to project directory
cd /home/admin/.openclaw/workspace/auto-trade-system

# Activate virtual environment (if not already active)
source .venv/bin/activate

# Stop any running instance (Ctrl+C if running in terminal)

# Start the application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option 3: Using Start Script
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
./start_services.sh
```

## Verification Steps

After restarting, verify the following:

### 1. Check Startup Logs
Look for these success messages:
```
✅ BybitConnector initialized in DEMO mode (api-demo.bybit.com)
✅ Sync Agent started with Bybit
✅ Position sync service started (5s interval, Bybit Demo mode)
```

### 2. Verify NO MEXC Errors
You should **NOT** see:
- ❌ "WEBSOCKET CIRCUIT BREAKER ACTIVATED" (MEXC-related)
- ❌ "MEXCWebSocketManager" initialization errors
- ❌ Connection attempts to `contract.mexc.com`

### 3. Monitor Bybit Connection
Expected logs:
```
🔌 Connecting to Bybit DEMO...
✅ Bybit DEMO connected with WebSocket streams
🔄 Position update received for XAU/USDT:USDT
```

### 4. Check System Health
```bash
# API health check
curl http://localhost:8000/health

# Metrics endpoint (Prometheus format)
curl http://localhost:8000/metrics/prometheus
```

## Troubleshooting

### If you still see MEXC errors:
1. **Check for old processes**:
   ```bash
   ps aux | grep python | grep -i trade
   # Kill any remaining processes
   kill -9 <PID>
   ```

2. **Clear Python cache**:
   ```bash
   find /home/admin/.openclaw/workspace/auto-trade-system -type d -name __pycache__ -exec rm -rf {} +
   ```

3. **Verify ACTIVE_EXCHANGE setting**:
   ```bash
   grep ACTIVE_EXCHANGE app/config.py
   # Should show: ACTIVE_EXCHANGE: str = "bybit"
   ```

4. **Check .env file is loaded**:
   ```bash
   grep BYBIT_USE_DEMO_DOMAIN .env
   # Should show: BYBIT_USE_DEMO_DOMAIN=true
   ```

### If Bybit connection fails:
1. **Verify API keys are valid**:
   - Log into https://www.bybit.com/en/trade/demo
   - Confirm API keys are generated in demo mode
   - Check keys haven't expired

2. **Test connectivity manually**:
   ```bash
   python scripts/test_bybit_demo_api_quick.py
   ```

3. **Check network access**:
   ```bash
   curl -I https://api-demo.bybit.com
   ```

## Expected Behavior

### Normal Operation
- WebSocket connects to `wss://stream-demo.bybit.com`
- Position sync runs every 5 seconds via REST API
- Reconciliation checks every 2 minutes
- No MEXC-related errors or warnings
- Clean logs showing only Bybit activity

### Error Handling
If Bybit WebSocket disconnects:
- Automatic reconnection with exponential backoff
- Circuit breaker activates after 5 consecutive failures
- Fallback to REST API polling
- Telegram notification sent (if configured)

## Rollback Instructions

If you need to revert to MEXC:

1. **Restore config.py**:
   ```bash
   git checkout app/config.py
   # Or manually change ACTIVE_EXCHANGE back to "mexc"
   ```

2. **Restore sync_agent.py**:
   ```bash
   git checkout app/sync/sync_agent.py
   ```

3. **Restart application**

## Support

For issues related to this migration:
- Check logs: `journalctl -u auto-trade-system -f`
- Review Bybit status: https://status.bybit.com
- Consult Bybit skill documentation in project root

---
**Migration Date**: May 13, 2026  
**Status**: ✅ Complete  
**Next Steps**: Monitor system stability for 24 hours
