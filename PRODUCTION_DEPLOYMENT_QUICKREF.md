# 🚀 Production Deployment Quick Reference

**Purpose**: Step-by-step checklist for deploying Auto Trade System to production  
**Prerequisites**: Execution layer components validated ✅  

---

## 📋 Pre-Deployment Checklist

### Before Starting (Day 0)

- [ ] PostgreSQL running and accessible
- [ ] Redis running (if using)
- [ ] `.env` configured for TestNet (`BINANCE_TESTNET=true`)
- [ ] Telegram bot token and chat ID set
- [ ] Virtual environment activated
- [ ] All dependencies installed

```bash
# Quick system check
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate

# Verify database connection
python -c "from app.storage.db import async_session_maker; import asyncio; asyncio.run(async_session_maker())" && echo "✅ DB OK"

# Verify Telegram
python -c "import asyncio; from app.infra.telegram_notifier import TelegramNotifier; asyncio.run(TelegramNotifier().send_message('System check'))" && echo "✅ Telegram OK"

# Run component validation
python scripts/validate_execution_layer_simple.py
```

---

## Phase 1: TestNet Validation (48+ Hours)

### Step 1: Start System

```bash
# Start application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or use systemd if configured
sudo systemctl start auto-trade
```

**Verify Startup**:
```bash
# Check health endpoint
curl http://localhost:8000/health

# Check metrics
curl http://localhost:8000/metrics | python -m json.tool
```

### Step 2: Execute Test Trades

```bash
# Execute trades via script
python scripts/execute_gold_trade.py

# Or via API
curl -X POST http://localhost:8000/api/v1/trading/execute-cycle \
  -H "Content-Type: application/json" \
  -d '{"symbol": "XAUT/USDT", "mode": "DEMO"}'
```

**Target**: 20+ trades over 48 hours

### Step 3: Set Up Monitoring

```bash
# Make monitoring script executable
chmod +x scripts/monitor_deployment.py

# Add to crontab (run every 5 minutes)
crontab -e
# Add: */5 * * * * cd /home/admin/.openclaw/workspace/auto-trade-system && source .venv/bin/activate && python scripts/monitor_deployment.py >> logs/deployment_monitor.log 2>&1
```

### Step 4: Test Failure Scenarios

#### Network Interruption (Day 1)
```bash
# Block API temporarily
sudo iptables -A OUTPUT -d api.binance.com -j DROP
sleep 10
sudo iptables -D OUTPUT -d api.binance.com -j DROP

# Check circuit breaker in logs
grep "Circuit breaker" logs/app.log | tail -5
```

#### WebSocket Disconnect (Day 2)
```bash
# Monitor reconnection
watch -n 10 'curl -s http://localhost:8000/metrics | jq ".websocket.reconnect_count"'
```

---

## Phase 2: Validation (After 48 Hours)

### Run Comprehensive Validation

```bash
python scripts/validate_production_readiness.py
```

**Expected Output**:
```
✅ Trade Volume: PASS
✅ Performance: PASS
✅ Event Store: PASS
✅ Telegram: PASS
✅ Uptime: PASS

✅ ALL CRITICAL CHECKS PASSED
```

### Review Metrics

```bash
# Check trade statistics
psql -U postgres -d vmassit -c "
SELECT 
    COUNT(*) as total_trades,
    ROUND(AVG(CASE WHEN profit > 0 THEN 1 ELSE 0 END) * 100, 2) as win_rate,
    SUM(profit) as total_pnl
FROM paper_trades 
WHERE status = 'closed';
"

# Check event store
psql -U postgres -d vmassit -c "
SELECT event_type, COUNT(*) 
FROM order_events 
GROUP BY event_type 
ORDER BY COUNT(*) DESC;
"
```

### Verify Thresholds

| Metric | Required | Current | Status |
|--------|----------|---------|--------|
| Trades | ≥ 20 | ___ | [ ] |
| Win Rate | ≥ 55% | ___% | [ ] |
| Profit Factor | ≥ 1.5 | ___ | [ ] |
| Max Drawdown | ≤ 15% | ___% | [ ] |
| Queue Size | < 100 | ___ | [ ] |
| Latency | < 100ms | ___ms | [ ] |
| Uptime | ≥ 48h | ___h | [ ] |

---

## Phase 3: Pre-Launch (Before Go-Live)

### Database Backup

```bash
# Stop system
sudo systemctl stop auto-trade

# Create backup
./scripts/backup_database.sh --retention 90

# Verify backup
ls -lh data/backups/vmassit_db_*.db.gz | tail -1
gzip -t data/backups/vmassit_db_*.db.gz && echo "✅ Backup verified"

# Copy to safe location
cp data/backups/vmassit_db_*.db.gz /path/to/external/storage/
```

### Update Configuration

Edit `.env`:

```diff
- BINANCE_TESTNET=true
+ BINANCE_TESTNET=false

- EXECUTION_MODE=fully-auto
+ EXECUTION_MODE=semi-auto

- AUTO_EXECUTE_THRESHOLD_USD=100.0
+ AUTO_EXECUTE_THRESHOLD_USD=50.0

# Verify MEXC keys are production keys
MEXC_API_KEY=your_REAL_mexc_key
MEXC_API_SECRET=your_REAL_mexc_secret
```

### Final Health Check

```bash
# Restart with new config
sudo systemctl start auto-trade
sleep 120

# Verify
curl http://localhost:8000/health
curl http://localhost:8000/metrics | python -m json.tool

# Test Telegram
python -c "import asyncio; from app.infra.telegram_notifier import TelegramNotifier; asyncio.run(TelegramNotifier().send_message('🚀 System switching to PRODUCTION mode'))"
```

---

## Phase 4: Go-Live (Production)

### First 24 Hours - Intensive Monitoring

```bash
# Check every hour
while true; do
  curl -s http://localhost:8000/metrics | jq '{
    time: now,
    queue_size: .event_bus.queue_size,
    latency: .websocket.avg_latency_ms,
    connected: .websocket.connected
  }'
  sleep 3600
done
```

**Monitor**:
- [ ] Every trade execution
- [ ] Telegram alerts received
- [ ] No unexpected errors in logs
- [ ] P&L within expected range
- [ ] System uptime maintained

### After 24 Hours - Gradual Scaling

If all looks good:
- [ ] Increase position sizes to $50-$100
- [ ] Consider switching to `fully-auto` mode
- [ ] Continue daily reviews for first week

---

## 🚨 Emergency Procedures

### System Crash

```bash
# Check status
systemctl status auto-trade

# View logs
journalctl -u auto-trade -n 100 --no-pager

# Restart
sudo systemctl restart auto-trade

# Check database integrity
psql -U postgres -d vmassit -c "SELECT COUNT(*) FROM paper_trades;"
```

### Unexpected Losses

```bash
# Pause trading immediately
curl -X POST http://localhost:8000/api/v1/trading/pause

# Or stop system
sudo systemctl stop auto-trade

# Review recent trades
psql -U postgres -d vmassit -c "
SELECT id, symbol, side, profit, ts_close 
FROM paper_trades 
ORDER BY ts_close DESC 
LIMIT 10;
"
```

### Database Issues

```bash
# Restore from backup
sudo systemctl stop auto-trade
cp data/backups/vmassit_db_LATEST.db.gz /tmp/
cd /tmp
gunzip vmassit_db_LATEST.db.gz
cp vmassit_db_LATEST.db data/vmassit.db
sudo systemctl start auto-trade
```

---

## 📊 Quick Commands Reference

### System Management
```bash
# Start
sudo systemctl start auto-trade

# Stop
sudo systemctl stop auto-trade

# Restart
sudo systemctl restart auto-trade

# Status
systemctl status auto-trade

# Logs
journalctl -u auto-trade -f
```

### Monitoring
```bash
# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics | python -m json.tool

# Run validation
python scripts/validate_production_readiness.py

# Monitor logs
tail -f logs/app.log
```

### Database
```bash
# Connect to DB
psql -U postgres -d vmassit

# Backup
./scripts/backup_database.sh

# Check trades
psql -U postgres -d vmassit -c "SELECT COUNT(*) FROM paper_trades;"
```

### Testing
```bash
# Component validation
python scripts/validate_execution_layer_simple.py

# Telegram test
python -c "import asyncio; from app.infra.telegram_notifier import TelegramNotifier; asyncio.run(TelegramNotifier().send_message('Test'))"
```

---

## 📞 Support Resources

### Documentation
- **Full Plan**: `PRODUCTION_DEPLOYMENT_PLAN.md`
- **Status Report**: `PRODUCTION_DEPLOYMENT_STATUS.md`
- **Quick Start**: `QUICK_START_EXECUTION_LAYER.md`
- **Live Criteria**: `MEXC_LIVE_TRADING_CRITERIA.md`

### Key Scripts
- **Monitor**: `scripts/monitor_deployment.py`
- **Validate**: `scripts/validate_production_readiness.py`
- **Backup**: `scripts/backup_database.sh`

### External Links
- Binance API: https://binance-docs.github.io/apidocs/
- MEXC API: https://mexcdevelop.github.io/apidocs/

---

## ✅ Final Sign-Off

Before going live, confirm:

- [ ] 48+ hours TestNet runtime completed
- [ ] 20+ trades executed successfully
- [ ] All validation checks passed
- [ ] Database backup performed and verified
- [ ] Configuration updated for mainnet
- [ ] Team briefed on procedures
- [ ] Emergency plan documented
- [ ] Capital allocation decided

**Authorized By**: _________________________  
**Date**: ___________  
**Time**: ___________

---

*Last Updated: May 12, 2026*  
*Version: 1.0*
