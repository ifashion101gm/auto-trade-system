# Production Monitoring Quick Reference

## 🚀 Start Services

```bash
# Start system
sudo systemctl start auto-trade

# Check status
systemctl status auto-trade

# View logs
journalctl -u auto-trade -f
```

---

## 📊 Monitor Events

### Event Types to Watch

| Event | When It Fires | Action Required |
|-------|---------------|-----------------|
| `ORDER_STATE_CHANGED` | Order transitions states | Monitor critical transitions |
| `RISK_VIOLATION_DETECTED` | Risk limits breached | **Immediate review** |
| `RECOVERY_ACTION_TAKEN` | Auto-repair performed | Verify correctness |

### Quick Event Query

```python
from app.events.event_store import event_store
from app.database.connection import get_session

async for db_session in get_session():
    events = await event_store.get_recent_events(
        db_session, 
        event_type='ORDER_STATE_CHANGED', 
        limit=10
    )
```

---

## 🔍 Query Tables

### Risk Violations (Last 24h)

```python
from app.database.repositories import RiskEventRepository

async for db_session in get_session():
    risk_repo = RiskEventRepository()
    violations = await risk_repo.get_recent_violations(db_session, hours=24)
```

**SQL Equivalent:**
```sql
SELECT * FROM risk_events 
WHERE risk_level IN ('HIGH', 'CRITICAL') 
  AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

### Pending Manual Reviews

```python
from app.database.repositories import RecoveryEventRepository

async for db_session in get_session():
    recovery_repo = RecoveryEventRepository()
    reviews = await recovery_repo.get_pending_reviews(db_session)
```

**SQL Equivalent:**
```sql
SELECT * FROM recovery_events 
WHERE requires_manual_review = 1 
ORDER BY timestamp DESC;
```

### Execution Logs for Trade

```python
from app.database.repositories import ExecutionLogRepository

async for db_session in get_session():
    exec_log_repo = ExecutionLogRepository()
    logs = await exec_log_repo.get_logs_by_trade(trade_id, db_session)
```

**SQL Equivalent:**
```sql
SELECT * FROM execution_logs 
WHERE trade_id = 'your-trade-id' 
ORDER BY timestamp;
```

### Run All Queries

```bash
python scripts/production_monitoring_queries.py
```

---

## 📱 Telegram Notifications

### New Alert Methods

#### 1. Order State Alerts
```python
await notifier.send_order_state_alert(
    order_id="ORD123",
    symbol="XAUT/USDT",
    from_state="PENDING",
    to_state="FILLED"
)
```

#### 2. Reconciliation Alerts
```python
await notifier.send_reconciliation_alert(
    action="closed_ghost_position",
    symbol="XAUT/USDT",
    exchange="MEXC",
    mismatch_type="GHOST_POSITION",
    requires_review=False
)
```

#### 3. Risk Violation Alerts
```python
await notifier.send_risk_violation_alert(
    violation_type="MAX_POSITION_EXCEEDED",
    symbol="XAUT/USDT",
    risk_level="CRITICAL",
    description="Exposure exceeds limit",
    metrics={"current": 5500, "max": 5000}
)
```

---

## 🎯 Critical Commands

### Emergency Stop
```bash
sudo systemctl stop auto-trade
```

### Check Open Positions
```bash
python scripts/check_open_trades.py
```

### Manual Position Sync
```bash
python -c "
import asyncio
from app.sync.position_sync import PositionSyncService
from app.database.connection import get_session

async def sync():
    service = PositionSyncService(testnet=True)
    async for db_session in get_session():
        await service.sync_once(db_session)
        break

asyncio.run(sync())
"
```

### Database Health Check
```bash
psql -U postgres -d vmassit -c "
SELECT 
    (SELECT COUNT(*) FROM trades WHERE status = 'OPEN') as open_trades,
    (SELECT COUNT(*) FROM risk_events WHERE timestamp > NOW() - INTERVAL '24 hours') as recent_violations,
    (SELECT COUNT(*) FROM recovery_events WHERE requires_manual_review = 1) as pending_reviews;
"
```

---

## ⚠️ Alert Severity Guide

| Level | Emoji | Response Time | Examples |
|-------|-------|---------------|----------|
| LOW | ⚠️ | Next business day | Minor warnings |
| MEDIUM | 🟡 | Within 4 hours | Moderate concerns |
| HIGH | 🔴 | Within 1 hour | Serious issues |
| CRITICAL | 🚨 | **Immediate** | System-threatening |

---

## 📈 Key Metrics

### Prometheus Endpoints
- Health: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`

### Important Metrics
- `trading_cycle_duration_seconds` - Should be < 60s
- `order_execution_latency_ms` - Should be < 5000ms
- `risk_violations_total` - Monitor trends
- `reconciliation_mismatches_total` - Should be near 0
- `websocket_connection_uptime` - Should be > 95%

---

## 🔧 Troubleshooting

### No Telegram Alerts?
```bash
# Check config
grep TELEGRAM .env

# Test notification
python -c "
import asyncio
from app.notifications.notifier import TelegramNotifier
async def test():
    n = TelegramNotifier()
    print(await n.send_system_alert('Test', 'OK'))
asyncio.run(test())
"
```

### High Mismatch Rate?
```bash
# Check WebSocket stability
journalctl -u auto-trade | grep websocket | tail -20

# Increase sync frequency (edit app/config.py)
POSITION_SYNC_INTERVAL = 3  # Reduce from 5
```

### System Crash Recovery
```bash
# Restart (auto-recovers on startup)
sudo systemctl restart auto-trade

# Verify recovery
journalctl -u auto-trade -f | grep recovery
```

---

## 📅 Maintenance Schedule

### Daily
- [ ] Review Telegram alerts
- [ ] Check risk violations
- [ ] Verify no pending reviews
- [ ] Monitor system health

### Weekly
- [ ] Analyze violation trends
- [ ] Review mismatch frequency
- [ ] Check latency trends
- [ ] Backup database

### Monthly
- [ ] Performance analysis
- [ ] Optimize risk parameters
- [ ] Capacity planning
- [ ] Security audit

---

## 🆘 Quick Help

| Problem | Solution |
|---------|----------|
| System not starting | `journalctl -u auto-trade -n 50` |
| Too many alerts | Adjust thresholds in `.env` |
| Missing positions | Run manual sync script |
| Database errors | `psql -U postgres -d vmassit -c "\dt"` |
| High latency | Check network and API rate limits |

---

**For detailed documentation:** See `PRODUCTION_ENHANCED_MONITORING.md`  
**Last Updated:** May 12, 2026
