# 🚀 Quick Start: Testing the Execution Layer Upgrade

This guide helps you quickly validate the new execution layer components.

---

## 1️⃣ Run Validation Tests (2 minutes)

Test all core components without starting the full application:

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
python scripts/validate_execution_layer_simple.py
```

**Expected Output:**
```
✅ Circuit Breaker: PASSED
✅ Rate Limiter: PASSED
✅ State Machine: PASSED
✅ Event Priority Queue: PASSED

✅ ALL TESTS PASSED!
```

---

## 2️⃣ Start the Application (1 minute)

Launch FastAPI with all background services:

```bash
# From project root
python -m uvicorn app.main:app --reload --port 8000
```

**Watch for these startup logs:**
```
✅ PostgreSQL database initialized
✅ EventBus started with priority processing
✅ EventStore subscribed to critical events
✅ Agents initialized
✅ Sync agent with WebSocket started
✅ Reconciliation loop started
```

If you see errors, check:
- Database connection (PostgreSQL running?)
- Environment variables (.env file configured?)
- Dependencies installed (`pip install -r requirements.txt`)

---

## 3️⃣ Verify System Health (30 seconds)

Check if all components are running:

```bash
# Health check
curl http://localhost:8000/health

# Component metrics
curl http://localhost:8000/metrics | python -m json.tool
```

**Expected Metrics Response:**
```json
{
  "event_bus": {
    "queue_size": 0,
    "dead_letter_count": 0,
    "processed_count": 5
  },
  "websocket": {
    "connected": true,
    "uptime_seconds": 45,
    "reconnect_count": 0,
    "avg_latency_ms": 42.5
  },
  "timestamp": "2026-05-12T10:30:00"
}
```

**Key Indicators:**
- ✅ `queue_size` < 100 (normal operation)
- ✅ `dead_letter_count` = 0 (no failed handlers)
- ✅ `websocket.connected` = true
- ✅ `avg_latency_ms` < 100 (good connection)

---

## 4️⃣ Execute Test Trade (Optional - 5 minutes)

If you want to test the state machine in action:

### Option A: Use API Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/trading/execute-cycle \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "XAUT/USDT",
    "mode": "DEMO"
  }'
```

### Option B: Use Python Script

```bash
python scripts/execute_gold_trade.py
```

**Monitor State Transitions in Logs:**
```
State: IDLE → FETCHING_DATA
State: FETCHING_DATA → ANALYZING
State: ANALYZING → PROPOSING
State: PROPOSING → VALIDATING
State: VALIDATING → EXECUTING
State: EXECUTING → MONITORING
State: MONITORING → IDLE
```

Each transition should log:
```
🔄 State changed: IDLE -> FETCHING_DATA
```

---

## 5️⃣ Monitor Real-Time Events

Watch the event stream as trades execute:

### Check EventStore Database

```sql
-- Connect to PostgreSQL
psql -U postgres -d vmassit

-- View recent critical events
SELECT 
    id,
    trade_id,
    event_type,
    created_at,
    payload->>'order_id' as order_id
FROM order_events
ORDER BY created_at DESC
LIMIT 10;
```

**Expected Events:**
- `STATE_CHANGED` - State machine transitions
- `ORDER_SUBMITTED` - Order sent to exchange
- `ORDER_FILLED` - Order executed
- `POSITION_UPDATED` - Position synced from WebSocket

---

## 6️⃣ Test Failure Scenarios (Advanced)

### Simulate Network Issues

1. **Block MEXC API temporarily:**
   ```bash
   # Add firewall rule (Linux)
   sudo iptables -A OUTPUT -d api.mexc.com -j DROP
   
   # Wait 10 seconds, then remove
   sudo iptables -D OUTPUT -d api.mexc.com -j DROP
   ```

2. **Observe circuit breaker behavior:**
   ```bash
   grep "CircuitBreakerError" logs/app.log
   grep "Circuit breaker OPEN" logs/app.log
   ```

3. **Verify auto-recovery:**
   ```bash
   # After 60s, circuit should close
   grep "Circuit breaker CLOSED" logs/app.log
   ```

### Simulate Orphaned Orders

1. **Manually cancel an order on MEXC website**
2. **Wait for reconciliation (2 minutes)**
3. **Check logs:**
   ```bash
   grep "Orphaned trade detected" logs/app.log
   ```

---

## 🔍 Troubleshooting

### Issue: EventBus not starting

**Symptoms:**
```
❌ EventBus failed to start
```

**Fix:**
```bash
# Check Python version (need 3.7+)
python --version

# Install dependencies
pip install -r requirements.txt

# Check for import errors
python -c "from app.events.event_bus import event_bus; print('OK')"
```

### Issue: WebSocket keeps reconnecting

**Symptoms:**
```
⚠️ WebSocket disconnected, reconnecting...
⚠️ WebSocket disconnected, reconnecting...
```

**Fix:**
```bash
# Check MEXC API status
curl https://api.mexc.com/api/v3/ping

# Verify API keys in .env
grep MEXC_API_KEY .env
grep MEXC_API_SECRET .env

# Check network connectivity
ping api.mexc.com
```

### Issue: State transitions not logging

**Symptoms:**
No `State changed:` messages in logs

**Fix:**
```bash
# Verify imports in live_trading_service.py
grep "from app.services.execution_states import" app/services/live_trading_service.py

# Check log level
grep "LOG_LEVEL" .env
# Should be: LOG_LEVEL=INFO or DEBUG
```

### Issue: High message latency (>500ms)

**Symptoms:**
```json
{
  "websocket": {
    "avg_latency_ms": 850.5
  }
}
```

**Fix:**
```bash
# Check server load
top -bn1 | head -20

# Check network latency
ping -c 10 api.mexc.com

# Consider moving to closer region if consistently high
```

---

## 📊 What to Monitor

### Daily Checks

1. **EventBus Queue Size**
   ```bash
   curl -s http://localhost:8000/metrics | jq '.event_bus.queue_size'
   ```
   - Normal: 0-50
   - Warning: 50-500 (backlog building)
   - Critical: >500 (processing too slow)

2. **Dead Letter Count**
   ```bash
   curl -s http://localhost:8000/metrics | jq '.event_bus.dead_letter_count'
   ```
   - Normal: 0
   - Warning: 1-10 (investigate failed handlers)
   - Critical: >10 (systematic issue)

3. **WebSocket Uptime**
   ```bash
   curl -s http://localhost:8000/metrics | jq '.websocket.uptime_seconds'
   ```
   - Should increase steadily
   - Resets indicate reconnections

4. **Circuit Breaker State**
   ```bash
   grep "Circuit breaker" logs/app.log | tail -5
   ```
   - Should remain CLOSED
   - OPEN indicates exchange issues

### Weekly Reviews

1. **EventStore Analysis**
   ```sql
   -- Count events by type (last 7 days)
   SELECT 
       event_type,
       COUNT(*) as count
   FROM order_events
   WHERE created_at > NOW() - INTERVAL '7 days'
   GROUP BY event_type
   ORDER BY count DESC;
   ```

2. **Orphaned Order Frequency**
   ```bash
   grep "Orphaned trade" logs/app.log | wc -l
   ```
   - Normal: 0-2 per week
   - High: >10 per week (sync issues)

3. **State Transition Patterns**
   ```bash
   grep "State changed" logs/app.log | awk '{print $4}' | sort | uniq -c
   ```
   - Should show balanced distribution
   - Excessive ERROR states indicate problems

---

## 🎯 Success Criteria

Your execution layer upgrade is working correctly if:

- ✅ All validation tests pass
- ✅ Application starts without errors
- ✅ `/metrics` endpoint returns valid data
- ✅ WebSocket stays connected (uptime > 95%)
- ✅ State transitions follow expected pattern
- ✅ No dead letter queue buildup
- ✅ Circuit breaker remains CLOSED during normal operation
- ✅ Orphaned orders detected and flagged (<5 per day)
- ✅ Message latency < 100ms average
- ✅ EventStore captures all critical events

---

## 📞 Need Help?

### Quick Diagnostics

Run this one-liner to check system health:

```bash
echo "=== Health ===" && \
curl -s http://localhost:8000/health && \
echo -e "\n\n=== Metrics ===" && \
curl -s http://localhost:8000/metrics | python -m json.tool && \
echo -e "\n\n=== Recent Errors ===" && \
tail -50 logs/app.log | grep -i error | tail -5
```

### Log Locations

- **Application Logs:** `logs/app.log`
- **EventStore:** PostgreSQL table `order_events`
- **Trade History:** PostgreSQL table `paper_trades` or `live_trades`

### Documentation

- **Full Report:** `EXECUTION_LAYER_COMPLETION_REPORT.md`
- **Architecture Details:** `EXECUTION_LAYER_UPGRADE_SUMMARY.md`
- **Quick Reference:** `QUICK_REFERENCE_EXECUTION_LAYER.md`

---

## 🚦 Ready for Production?

Before going live:

1. ✅ Run on TestNet for at least 48 hours
2. ✅ Execute 20+ test trades successfully
3. ✅ Verify all failure scenarios handled gracefully
4. ✅ Monitor metrics for stability
5. ✅ Review EventStore for anomalies
6. ✅ Set up Telegram alerts for critical events
7. ✅ Document runbook for common issues
8. ✅ Backup database before switching to mainnet

**Then:** Update `.env` to use production exchange credentials and monitor closely for first 24 hours.

---

**Happy Trading! 🎉**
