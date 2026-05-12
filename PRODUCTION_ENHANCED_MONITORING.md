# Production Deployment Guide - Enhanced Monitoring & Notifications

## Overview

This guide covers the enhanced production features for real-time monitoring, risk management, and automated notifications. These enhancements provide enterprise-grade observability and alerting for your trading system.

---

## 1. Start Services

The enhanced services automatically use the new logic when started:

### Service Configuration

```bash
# PositionSyncService runs every 5 seconds with risk integration
# ReconciliationService runs every 2 minutes with deep validation
```

### Starting the System

```bash
# Option 1: Using systemd (recommended for production)
sudo systemctl start auto-trade
sudo systemctl enable auto-trade  # Auto-start on boot

# Option 2: Manual start
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python app/main.py

# Option 3: Using start script
./start_services.sh
```

### Verify Services Are Running

```bash
# Check service status
systemctl status auto-trade

# View live logs
journalctl -u auto-trade -f

# Check health endpoint
curl http://localhost:8000/health

# Check metrics endpoint
curl http://localhost:8000/metrics | python -m json.tool
```

### Expected Service Behavior

- **PositionSyncService**: Runs every 5 seconds, syncs exchange positions with database
- **ReconciliationService**: Runs every 2 minutes, detects and repairs mismatches
- **Event Bus**: Publishes events for all critical operations
- **Telegram Notifier**: Sends alerts based on configured thresholds

---

## 2. Monitor Events

Subscribe to new event types for real-time monitoring:

### New Event Types

| Event Type | Description | Priority | Use Case |
|------------|-------------|----------|----------|
| `ORDER_STATE_CHANGED` | Track order lifecycle transitions | High | Monitor order execution flow |
| `RISK_VIOLATION_DETECTED` | Alert on risk breaches | Critical | Immediate risk intervention |
| `RECOVERY_ACTION_TAKEN` | Monitor reconciliation actions | Medium | Track auto-repairs |

### Event Subscription Example

```python
from app.events.event_bus import event_bus
from app.events.event_types import (
    ORDER_STATE_CHANGED,
    RISK_VIOLATION_DETECTED,
    RECOVERY_ACTION_TAKEN
)

# Subscribe to order state changes
async def on_order_state_changed(event):
    payload = event['payload']
    print(f"Order {payload['order_id']} changed from {payload['from_state']} to {payload['to_state']}")
    
event_bus.subscribe(ORDER_STATE_CHANGED, on_order_state_changed)

# Subscribe to risk violations
async def on_risk_violation(event):
    payload = event['payload']
    print(f"Risk violation detected: {payload['violation_type']}")
    
event_bus.subscribe(RISK_VIOLATION_DETECTED, on_risk_violation)

# Subscribe to recovery actions
async def on_recovery_action(event):
    payload = event['payload']
    print(f"Recovery action taken: {payload['action']}")
    
event_bus.subscribe(RECOVERY_ACTION_TAKEN, on_recovery_action)
```

### Real-Time Event Monitoring

Use the event store to query recent events:

```python
from app.events.event_store import event_store
from app.database.connection import get_session

async for db_session in get_session():
    # Get recent order state changes
    events = await event_store.get_recent_events(
        db_session,
        event_type='ORDER_STATE_CHANGED',
        limit=20
    )
    
    for event in events:
        print(f"[{event['created_at']}] {event['event_type']}")
```

### Telegram Integration

Events automatically trigger Telegram notifications when configured:

```bash
# Configure in .env file
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Critical events that trigger Telegram alerts:**
- Order rejections or cancellations
- Risk limit breaches (HIGH/CRITICAL level)
- Reconciliation actions requiring manual review
- System errors and failures

---

## 3. Query New Tables

Use the new repositories for advanced queries:

### Repository Access Pattern

```python
from app.database.repositories import (
    RiskEventRepository,
    RecoveryEventRepository,
    ExecutionLogRepository
)
from app.database.connection import get_session

async for db_session in get_session():
    risk_repo = RiskEventRepository()
    recovery_repo = RecoveryEventRepository()
    exec_log_repo = ExecutionLogRepository()
    
    # Perform queries...
```

### Query Examples

#### Get Recent Risk Violations

```python
# Get violations from last 24 hours
violations = await risk_repo.get_recent_violations(db_session, hours=24)

for violation in violations:
    print(f"[{violation.risk_level}] {violation.event_type}")
    print(f"Description: {violation.description}")
    print(f"Action Taken: {violation.action_taken}")
```

#### Get Pending Manual Reviews

```python
# Get recovery events requiring manual review
reviews = await recovery_repo.get_pending_reviews(db_session)

for review in reviews:
    print(f"[{review.recovery_type}] {review.symbol}")
    print(f"Exchange: {review.exchange}")
    print(f"Requires Review: {review.requires_manual_review}")
```

#### Get Execution Logs for a Trade

```python
# Get all execution logs for a specific trade
logs = await exec_log_repo.get_logs_by_trade(trade_id, db_session)

for log in logs:
    print(f"[{log.status}] {log.action}")
    print(f"Latency: {log.latency_ms}ms")
    print(f"Retries: {log.retry_count}")
```

### Run Pre-Built Monitoring Queries

A comprehensive monitoring script is provided:

```bash
# Run all production monitoring queries
python scripts/production_monitoring_queries.py
```

This script queries:
- Recent risk violations (last 24 hours)
- Pending manual reviews
- Recent order state changes
- Risk violation summary (last 7 days)
- Execution logs for specific trades

### Direct Database Queries (PostgreSQL)

```sql
-- Connect to PostgreSQL
psql -U postgres -d vmassit

-- View recent critical risk events
SELECT 
    id,
    trade_id,
    event_type,
    risk_level,
    description,
    action_taken,
    timestamp
FROM risk_events
WHERE risk_level IN ('HIGH', 'CRITICAL')
ORDER BY timestamp DESC
LIMIT 20;

-- Count risk violations by type (last 48 hours)
SELECT 
    event_type,
    COUNT(*) as count
FROM risk_events
WHERE timestamp > NOW() - INTERVAL '48 hours'
GROUP BY event_type
ORDER BY count DESC;

-- Get pending manual reviews
SELECT 
    id,
    recovery_type,
    symbol,
    exchange,
    description,
    requires_manual_review,
    timestamp
FROM recovery_events
WHERE requires_manual_review = 1
ORDER BY timestamp DESC;

-- Get execution logs for a specific trade
SELECT 
    id,
    action,
    status,
    latency_ms,
    retry_count,
    error_message,
    timestamp
FROM execution_logs
WHERE trade_id = 'your-trade-id-here'
ORDER BY timestamp;

-- Analyze order state transitions
SELECT 
    payload->>'from_state' as from_state,
    payload->>'to_state' as to_state,
    COUNT(*) as transition_count
FROM order_events
WHERE event_type = 'ORDER_STATE_CHANGED'
GROUP BY from_state, to_state
ORDER BY transition_count DESC;
```

---

## 4. Telegram Notifications (Enhanced)

Three new notification methods have been added to `app/notifications/notifier.py`:

### send_order_state_alert()

Sends alerts for critical order state changes.

**Usage:**
```python
from app.notifications.notifier import TelegramNotifier

notifier = TelegramNotifier()

await notifier.send_order_state_alert(
    order_id="ORD123456",
    symbol="XAUT/USDT",
    from_state="PENDING",
    to_state="FILLED",
    trade_id="trade-uuid-here",
    details={
        "filled_price": 3350.00,
        "quantity": 0.5
    }
)
```

**Triggers Automatically For:**
- Order rejections
- Order cancellations
- Order expirations
- Recovery required states

### send_reconciliation_alert()

Sends alerts for position mismatches detected during reconciliation.

**Usage:**
```python
await notifier.send_reconciliation_alert(
    action="closed_ghost_position",
    symbol="XAUT/USDT",
    exchange="MEXC",
    mismatch_type="GHOST_POSITION",
    old_state={"size": 0.5, "status": "open"},
    new_state={"size": 0, "status": "closed"},
    requires_review=False
)
```

**Triggers Automatically For:**
- Ghost positions detected
- Orphaned orders found
- Position mismatches requiring repair
- States requiring manual review

### send_risk_violation_alert()

Sends alerts for risk limit breaches.

**Usage:**
```python
await notifier.send_risk_violation_alert(
    violation_type="MAX_POSITION_EXCEEDED",
    symbol="XAUT/USDT",
    risk_level="CRITICAL",
    description="Total exposure exceeds maximum allowed limit",
    metrics={
        "current_exposure": 5500.00,
        "max_allowed": 5000.00,
        "excess_amount": 500.00
    },
    action_taken="Trade rejected",
    trade_id="trade-uuid-here"
)
```

**Triggers Automatically For:**
- Maximum position size exceeded
- Daily loss limit reached
- Consecutive losses threshold hit
- Correlation limits breached
- Leverage limits exceeded

### Notification Severity Levels

| Level | Emoji | Use Case |
|-------|-------|----------|
| LOW | ⚠️ | Minor warnings, informational |
| MEDIUM | 🟡 | Moderate concerns, attention needed |
| HIGH | 🔴 | Serious issues, immediate action |
| CRITICAL | 🚨 | System-threatening, emergency response |

---

## 5. Monitoring Dashboard Setup

### Prometheus Metrics

The system exposes metrics at `/metrics` endpoint:

```bash
# View metrics
curl http://localhost:8000/metrics

# Key metrics to monitor:
# - trading_cycle_duration_seconds
# - order_execution_latency_ms
# - risk_violations_total
# - reconciliation_mismatches_total
# - websocket_connection_uptime
```

### Grafana Dashboards

Pre-configured dashboards are available in `monitoring/grafana/`:

1. **Trading Performance Dashboard**
   - Trade P&L over time
   - Win rate and Sharpe ratio
   - Drawdown tracking

2. **System Health Dashboard**
   - API latency and error rates
   - WebSocket connection status
   - Database connection pool usage

3. **Risk Management Dashboard**
   - Risk violations by type
   - Position exposure over time
   - Leverage utilization

### Alert Rules

Configure alerts in `monitoring/prometheus-alerts.yml`:

```yaml
groups:
  - name: trading_alerts
    rules:
      - alert: HighRiskViolationRate
        expr: rate(risk_violations_total[1h]) > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High rate of risk violations detected"
          
      - alert: ReconciliationMismatchDetected
        expr: reconciliation_mismatches_total > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Position mismatch detected during reconciliation"
          
      - alert: OrderExecutionLatencyHigh
        expr: histogram_quantile(0.95, order_execution_latency_ms) > 5000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Order execution latency is high"
```

---

## 6. Emergency Procedures

### If Critical Risk Violation Detected

1. **Immediate Response**
   ```bash
   # Stop trading immediately
   sudo systemctl stop auto-trade
   
   # Check current positions
   python scripts/check_open_trades.py
   
   # Review risk violations
   python scripts/production_monitoring_queries.py
   ```

2. **Assess Impact**
   - Review Telegram alerts for details
   - Check risk_events table for violation history
   - Determine if positions need manual closure

3. **Resolution**
   - Adjust risk parameters in `.env` if needed
   - Restart system after fixing root cause
   - Monitor closely for first hour after restart

### If Reconciliation Mismatch Detected

1. **Investigate**
   ```bash
   # Check pending reviews
   psql -U postgres -d vmassit -c \
     "SELECT * FROM recovery_events WHERE requires_manual_review = 1 ORDER BY timestamp DESC LIMIT 10;"
   ```

2. **Manual Review**
   - Compare database state with exchange state
   - Determine if auto-repair was appropriate
   - Manually correct if necessary

3. **Prevention**
   - Review WebSocket connection logs
   - Check for API rate limiting issues
   - Increase sync frequency if needed

### If System Crash During Trading

1. **Recovery**
   ```bash
   # Check last known state
   journalctl -u auto-trade -n 100 --no-pager
   
   # Restart system (will run recovery on startup)
   sudo systemctl restart auto-trade
   
   # Verify recovery completed
   journalctl -u auto-trade -f | grep "recovery"
   ```

2. **State Verification**
   ```bash
   # Run position sync manually
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

---

## 7. Best Practices

### Daily Monitoring Checklist

- [ ] Review Telegram alerts from previous 24 hours
- [ ] Check risk violation summary
- [ ] Verify no pending manual reviews
- [ ] Monitor system health metrics
- [ ] Review open positions vs database state

### Weekly Maintenance

- [ ] Analyze risk violation trends
- [ ] Review reconciliation mismatch frequency
- [ ] Check order execution latency trends
- [ ] Update risk parameters if needed
- [ ] Backup database

### Monthly Review

- [ ] Comprehensive performance analysis
- [ ] Risk parameter optimization
- [ ] System capacity planning
- [ ] Security audit of API keys
- [ ] Review and update alert thresholds

---

## 8. Troubleshooting

### Common Issues

**Issue: Not receiving Telegram notifications**
```bash
# Check configuration
grep TELEGRAM .env

# Test notification
python -c "
import asyncio
from app.notifications.notifier import TelegramNotifier

async def test():
    notifier = TelegramNotifier()
    result = await notifier.send_system_alert('Test', 'Testing notifications')
    print(f'Sent: {result}')

asyncio.run(test())
"
```

**Issue: High number of reconciliation mismatches**
```bash
# Check WebSocket connection stability
journalctl -u auto-trade | grep "websocket" | tail -20

# Increase sync frequency if needed
# Edit app/config.py: POSITION_SYNC_INTERVAL = 3  # Reduce from 5 to 3 seconds
```

**Issue: Risk violations not being recorded**
```bash
# Check database connectivity
psql -U postgres -d vmassit -c "SELECT COUNT(*) FROM risk_events;"

# Verify event bus is working
journalctl -u auto-trade | grep "RISK_VIOLATION_DETECTED"
```

---

## 9. Next Steps

After deploying these enhancements:

1. **Monitor for 48 hours** - Watch for false positives in alerts
2. **Tune thresholds** - Adjust risk limits based on observed behavior
3. **Document incidents** - Keep log of all alerts and resolutions
4. **Train team** - Ensure all operators understand new alerts
5. **Review weekly** - Analyze patterns and optimize parameters

---

## Support

For issues or questions:
- Check logs: `journalctl -u auto-trade -f`
- Review documentation in repository root
- Consult monitoring dashboards in Grafana
- Contact system administrator for critical issues

---

**Last Updated:** May 12, 2026  
**Version:** 2.0 - Enhanced Production Monitoring
