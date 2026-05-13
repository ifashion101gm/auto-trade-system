# Infrastructure Connectivity - Quick Reference

## Problem Summary (May 13, 2026)

**Issues Fixed:**
1. ❌ Database connection refused (Errno 111) on both IPv6 and IPv4
2. ❌ WebSocket stuck at 60s reconnect delay indefinitely
3. ❌ SYNC MISMATCH alerts blocking trading during DB outages

**Root Causes:**
- `localhost` resolving to both `::1` and `127.0.0.1` causing connection failures
- No backoff reset mechanism for prolonged WebSocket outages
- PositionSyncService crashing when database unavailable

---

## Quick Diagnostics

### Check Database Health
```bash
.venv/bin/python3 -c "from app.database.connection import check_database_health; import asyncio; result = asyncio.run(check_database_health()); print('✅ HEALTHY' if result['is_healthy'] else '❌ UNHEALTHY')"
```

### Check PostgreSQL Container
```bash
docker ps | grep postgres
# Expected: Up X hours (healthy)
```

### Check Network Ports
```bash
netstat -tuln | grep 5432
# Expected: tcp 0 0 0.0.0.0:5432 LISTEN
```

### Check Application Logs
```bash
journalctl -u auto-trade -f --since "10 minutes ago" | grep -E "ERROR|WARNING|DATABASE|WEBSOCKET"
```

---

## Common Scenarios & Solutions

### Scenario 1: Database Connection Refused

**Symptoms:**
```
Multiple exceptions: [Errno 111] Connect call failed ('::1', 5432), [Errno 111] Connect call failed ('127.0.0.1', 5432)
```

**Solution:**
✅ **Already Fixed** - DATABASE_URL now uses `127.0.0.1` instead of `localhost`

**If issue persists:**
```bash
# 1. Check PostgreSQL is running
docker ps | grep postgres

# 2. Restart PostgreSQL if needed
docker restart trading-postgres

# 3. Wait 30 seconds for initialization
sleep 30

# 4. Verify health
docker exec -it trading-postgres pg_isready -U trading -d vmassit
```

### Scenario 2: WebSocket Stuck at High Delay

**Symptoms:**
```
WEBSOCKET DISCONNECTED
Reconnect attempt #15
Calculated delay: 60.84s (capped at 60s)
```

**Solution:**
✅ **Already Fixed** - Backoff resets after 1 hour of continuous retries

**To manually reset (if needed):**
```bash
# Restart the application
sudo systemctl restart auto-trade
```

### Scenario 3: Position Sync Failing

**Symptoms:**
```
❌ Position sync error: Multiple exceptions...
SYNC MISMATCH DETECTED
```

**Solution:**
✅ **Already Fixed** - System enters degraded mode (30s sync interval) instead of crashing

**Monitor degraded mode:**
```bash
journalctl -u auto-trade -f | grep "degraded mode"
# If seen, database is temporarily unavailable but system is still running
```

---

## Log Patterns Cheat Sheet

### ✅ Healthy Operation
```
✅ Database initialized successfully
✅ MEXC WebSocket connected
🔄 Running position sync cycle...
Exchange positions: X ({symbols})
```

### ⚠️ Acceptable Warnings (Transient Issues)
```
⚠️  Database connection issue during sync (failure 1): ...
⚠️  Connection refused - PostgreSQL may be starting or unreachable
⚠️  WEBSOCKET DISCONNECTED
Reconnect attempt #3
Next retry in: 8.2s
🔧 Entering degraded mode - reducing sync frequency to 30s
```

### 🚨 Critical Alerts (Requires Action)
```
🚨 CIRCUIT BREAKER ACTIVATED!
WebSocket has failed 50 consecutive times.
❌ Database connection failed after 3 attempts
🚨 DATABASE UNAVAILABLE - System may operate in degraded mode
```

---

## Emergency Procedures

### Emergency 1: Complete Database Outage

**Goal:** Keep trading running, minimize data loss

**Steps:**
1. System will automatically enter degraded mode (30s sync interval)
2. Monitor logs: `journalctl -u auto-trade -f | grep degraded`
3. Restore database:
   ```bash
   docker restart trading-postgres
   sleep 30
   docker exec -it trading-postgres pg_isready -U trading -d vmassit
   ```
4. System will automatically resume normal operation
5. Check for SYNC_MISMATCH events and review if any

### Emergency 2: WebSocket Persistent Failure

**Goal:** Maintain market data connectivity

**Steps:**
1. Check circuit breaker status in logs
2. If circuit breaker active, investigate root cause:
   ```bash
   python3 scripts/diagnose_websocket.py
   ```
3. Common fixes:
   - Check API credentials in `.env`
   - Verify network connectivity to MEXC
   - Check if IP is banned
4. Restart application if needed:
   ```bash
   sudo systemctl restart auto-trade
   ```

### Emergency 3: Both Database AND WebSocket Down

**Goal:** Prevent catastrophic failure

**Steps:**
1. System will continue running with degraded functionality
2. Prioritize database restoration first
3. Then address WebSocket issues
4. Manual position sync may be required:
   ```bash
   .venv/bin/python3 -c "
   from app.sync.position_sync import PositionSyncService
   from app.database.connection import get_session
   import asyncio
   
   async def sync():
       service = PositionSyncService(testnet=True)
       async for db_session in get_session():
           await service.sync_once(db_session)
           break
   
   asyncio.run(sync())
   "
   ```

---

## Monitoring Commands

### Real-time Health Dashboard
```bash
# Open multiple terminal tabs

# Tab 1: Database health
watch -n 5 '.venv/bin/python3 -c "from app.database.connection import check_database_health; import asyncio; r=asyncio.run(check_database_health()); print(\"DB:\", \"✅\" if r[\"is_healthy\"] else \"❌\", \"Latency:\", r.get(\"checks\",{}).get(\"connectivity\",{}).get(\"latency_ms\",\"N/A\"), \"ms\")"'

# Tab 2: Application logs
journalctl -u auto-trade -f --since "2 minutes ago"

# Tab 3: Docker containers
watch -n 5 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
```

### Quick Health Check Script
```bash
#!/bin/bash
echo "=== Auto-Trade System Health Check ==="
echo ""

# Database
echo -n "Database: "
.venv/bin/python3 -c "from app.database.connection import check_database_health; import asyncio; r=asyncio.run(check_database_health()); print('✅ HEALTHY' if r['is_healthy'] else '❌ UNHEALTHY')" 2>/dev/null || echo "❌ ERROR"

# PostgreSQL Container
echo -n "PostgreSQL: "
docker ps | grep -q trading-postgres && echo "✅ Running" || echo "❌ Stopped"

# Application
echo -n "Application: "
systemctl is-active auto-trade >/dev/null 2>&1 && echo "✅ Active" || echo "❌ Inactive"

echo ""
echo "Check logs: journalctl -u auto-trade -f --since '5 minutes ago'"
```

---

## Configuration Reference

### Database Settings (`.env`)
```bash
DATABASE_URL=postgresql+asyncpg://trading:trading123@127.0.0.1:5432/vmassit
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
```

### WebSocket Settings (`app/config.py`)
```python
WEBSOCKET_HEARTBEAT_INTERVAL = 30        # Ping every 30s
WEBSOCKET_HEARTBEAT_TIMEOUT = 45         # Timeout after 45s
WEBSOCKET_RECONNECT_DELAY = 2            # Start with 2s delay
WEBSOCKET_MAX_RECONNECT_DELAY = 60       # Cap at 60s
WEBSOCKET_MAX_RECONNECT_ATTEMPTS = 0     # 0 = unlimited retries
WEBSOCKET_STALE_STREAM_THRESHOLD = 120   # Detect stale streams after 120s
WEBSOCKET_JITTER_FACTOR = 0.1            # 10% jitter
```

### Position Sync Settings (`app/sync/position_sync.py`)
```python
self._sync_interval = 5                  # Normal: every 5s
degraded_interval = 30                   # Degraded: every 30s
max_consecutive_failures = 5             # Enter degraded after 5 failures
```

---

## Troubleshooting Flowchart

```
Database Connection Failed?
├─ Yes → Check PostgreSQL container
│        ├─ Running? → Check logs: docker logs trading-postgres
│        └─ Stopped? → Start: docker start trading-postgres
│
└─ No → Check WebSocket
         ├─ Disconnected? → Check API credentials
         │                  → Run: python3 scripts/diagnose_websocket.py
         │
         └─ Connected? → System is healthy ✅
```

---

## Key Contacts & Resources

- **Diagnostic Scripts:** `scripts/diagnose_connectivity.py`, `scripts/diagnose_websocket.py`
- **Full Documentation:** `INFRASTRUCTURE_CONNECTIVITY_FIXES_MAY2026.md`
- **Monitoring Dashboard:** Grafana at http://localhost:3000 (if configured)
- **Logs:** `journalctl -u auto-trade -f`

---

**Last Updated:** May 13, 2026  
**Version:** 1.0  
**Status:** Production Ready
