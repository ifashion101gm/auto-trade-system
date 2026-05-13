# Infrastructure Connectivity Fixes - Quick Reference

## Overview

This document provides a quick reference for the infrastructure connectivity fixes implemented on May 13, 2026.

---

## What Was Fixed

### 1. WebSocket Instability ✅
- **Problem**: Persistent disconnections, backoff stuck at max delay
- **Solution**: Extended retry detection, backoff reset after 1 hour, network error handling
- **File**: `app/websocket/manager.py`

### 2. Database Connectivity Failures ✅
- **Problem**: Errno 104 (connection reset) and Errno 111 (connection refused)
- **Solution**: Active health monitoring, auto-reconnection, connection recycling
- **File**: `app/database/connection.py`

### 3. Docker PostgreSQL Configuration ✅
- **Problem**: Not listening on all interfaces, suboptimal settings
- **Solution**: Listen on all interfaces, optimized memory, enhanced health checks
- **File**: `docker-compose.yml`

---

## Quick Commands

### Run Diagnostics
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python scripts/diagnose_connectivity.py
```

### Check Database Health
```bash
# Via Python
python -c "
import asyncio
from app.database.connection import check_database_health
async def check():
    health = await check_database_health()
    print(f'Healthy: {health[\"is_healthy\"]}')
    print(f'Latency: {health[\"checks\"][\"connectivity\"][\"latency_ms\"]}ms')
asyncio.run(check())
"

# Via psql
psql -h localhost -U trading -d vmassit -c "SELECT version();"
```

### Check WebSocket Status
```bash
# Check if MEXC WebSocket is connected
python -c "
from app.websocket.manager import MEXCWebSocketManager
ws = MEXCWebSocketManager()
print(f'URL: {ws.ws_url}')
print(f'Circuit Breaker Threshold: {ws.circuit_breaker_threshold}')
"
```

### Restart Services
```bash
# Restart PostgreSQL only
docker-compose restart postgres

# Restart all services
docker-compose down
docker-compose up -d

# Check service status
docker-compose ps
```

---

## Key Configuration Values

### WebSocket Settings (`.env` or `app/config.py`)
```python
WEBSOCKET_HEARTBEAT_INTERVAL = 30        # seconds
WEBSOCKET_HEARTBEAT_TIMEOUT = 45         # seconds
WEBSOCKET_RECONNECT_DELAY = 2            # initial delay
WEBSOCKET_MAX_RECONNECT_DELAY = 60       # max delay
WEBSOCKET_MAX_RECONNECT_ATTEMPTS = 0     # 0 = unlimited
WEBSOCKET_STALE_STREAM_THRESHOLD = 120   # seconds
WEBSOCKET_JITTER_FACTOR = 0.1            # 10%
```

### Database Settings (`.env`)
```bash
DATABASE_URL=postgresql+asyncpg://trading:trading123@localhost:5432/vmassit
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
```

### Docker PostgreSQL Settings (`docker-compose.yml`)
```yaml
POSTGRES_MAX_CONNECTIONS: "100"
POSTGRES_SHARED_BUFFERS: "256MB"
POSTGRES_EFFECTIVE_CACHE_SIZE: "768MB"
pool_recycle: 300  # in application code
```

---

## Monitoring

### Check Logs

**WebSocket:**
```bash
# Look for these patterns
grep "WebSocket" logs/app.log | tail -20
grep "Circuit breaker" logs/app.log | tail -10
grep "Extended retry" logs/app.log | tail -10
```

**Database:**
```bash
# Look for these patterns
grep "Database connection" logs/app.log | tail -20
grep "pool_recycle" logs/app.log | tail -10
grep "OperationalError" logs/app.log | tail -10
```

### Health Check Endpoints

If you have an API running, you can add these endpoints:

```python
@app.get("/health/database")
async def database_health():
    from app.database.connection import check_database_health
    return await check_database_health()

@app.get("/health/websocket")
async def websocket_health():
    from app.websocket.manager import MEXCWebSocketManager
    ws = MEXCWebSocketManager()
    return ws.get_metrics()
```

---

## Troubleshooting

### WebSocket Keeps Disconnecting

**Symptoms:**
- Frequent "WebSocket disconnected" messages
- Circuit breaker activation alerts

**Check:**
```bash
# Test network connectivity
ping contract.mexc.com

# Check DNS resolution
nslookup contract.mexc.com

# Check firewall
sudo iptables -L | grep -i wss
```

**Fix:**
1. Verify API credentials are valid
2. Check if IP is banned by exchange
3. Increase `WEBSOCKET_HEARTBEAT_INTERVAL` to 60s
4. Review Telegram alerts for circuit breaker activations

### Database Connection Refused (Errno 111)

**Symptoms:**
- "Connection refused" errors
- Cannot connect to PostgreSQL

**Check:**
```bash
# Is PostgreSQL running?
docker-compose ps postgres

# Check logs
docker-compose logs postgres | tail -50

# Test connection
psql -h localhost -U trading -d vmassit -c "SELECT 1"
```

**Fix:**
```bash
# Restart PostgreSQL
docker-compose restart postgres

# If still failing, rebuild
docker-compose down
docker-compose up -d postgres
sleep 30  # Wait for initialization
```

### Connection Reset by Peer (Errno 104)

**Symptoms:**
- "Connection reset by peer" errors
- Intermittent database failures

**Check:**
```bash
# Check idle timeout
docker exec -it trading-postgres psql -U trading -d vmassit \
  -c "SHOW idle_in_transaction_session_timeout;"

# Check pool status
python -c "
from app.database.connection import engine
print(engine.pool.status())
"
```

**Fix:**
The fix already adds `pool_recycle=300` which should resolve this. If persists:
1. Increase `DB_POOL_SIZE` in `.env`
2. Check for long-running transactions
3. Monitor `db_health_status['consecutive_failures']`

---

## Alert Thresholds

Set up monitoring alerts for:

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| WebSocket disconnects | >5/hour | >20/hour | Check network/exchange status |
| Circuit breaker activated | Any | Any | Immediate investigation required |
| Database connection failures | >3/min | >10/min | Check PostgreSQL health |
| Pool utilization | >80% | >95% | Increase pool size |
| Query latency | >100ms | >500ms | Check database load |

---

## Files Modified

1. **`app/websocket/manager.py`**
   - Added OSError handling for errno 104/111
   - Implemented extended retry detection (>1 hour)
   - Added backoff reset mechanism

2. **`app/database/connection.py`**
   - Added `pool_recycle=300` for connection lifecycle
   - Implemented `check_database_health()` function
   - Enhanced `get_session()` with auto-reconnection
   - Added `db_health_status` tracking

3. **`docker-compose.yml`**
   - Added `listen_addresses=*` for PostgreSQL
   - Optimized memory settings
   - Enhanced health check configuration

4. **`scripts/diagnose_connectivity.py`** (NEW)
   - Comprehensive diagnostic script
   - Tests database, WebSocket, and Docker config

5. **`INFRASTRUCTURE_CONNECTIVITY_FIXES.md`** (NEW)
   - Detailed implementation report

---

## Validation Checklist

After deployment, verify:

- [ ] Diagnostic script passes all tests
- [ ] No "Connection reset" errors in logs
- [ ] No "Connection refused" errors in logs
- [ ] WebSocket stays connected >99% of time
- [ ] Database queries complete in <100ms
- [ ] Circuit breaker not activated
- [ ] Pool utilization <80%

Run this command to validate:
```bash
python scripts/diagnose_connectivity.py && echo "✅ All checks passed"
```

---

## Support

For issues or questions:
1. Check `INFRASTRUCTURE_CONNECTIVITY_FIXES.md` for detailed documentation
2. Run `python scripts/diagnose_connectivity.py` for diagnostics
3. Review logs: `docker-compose logs -f`
4. Check Telegram alerts for circuit breaker activations

---

**Last Updated:** May 13, 2026  
**Status:** ✅ Production Ready  
**Version:** 1.0
