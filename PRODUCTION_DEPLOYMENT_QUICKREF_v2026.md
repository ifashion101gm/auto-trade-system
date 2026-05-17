# 🚀 Production Deployment Quick Reference v2026

**Purpose**: Step-by-step checklist for deploying Auto Trade System to production  
**Updated**: May 17, 2026  
**Current State**: 5 paper trades completed, need 15 more  

---

## 📊 Current Status Snapshot

```bash
# Quick system check (run this first)
cd /home/admin/.openclaw/workspace/auto-trade-system

echo "=== SYSTEM STATUS ==="
ps aux | grep -c "[u]vicorn" && echo "✅ System running" || echo "❌ System not running"

python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM paper_trades WHERE status=\"closed\"'); print(f'Closed trades: {c.fetchone()[0]}/20'); conn.close()"

grep "^EXECUTION_MODE=" .env
grep "^BINANCE_TESTNET=" .env

ls -lh data/vmassit.db
```

---

## 📋 Pre-Deployment Checklist

### Before Starting (Day 0)

- [ ] PostgreSQL/SQLite database accessible
- [ ] `.env` configured correctly (paper mode)
- [ ] Telegram bot token and chat ID set
- [ ] Virtual environment activated
- [ ] All dependencies installed
- [ ] System has 5 completed trades ✅

```bash
# Quick system check
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate

# Verify database connection
python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); print('✅ DB OK'); conn.close()"

# Verify Telegram
python3 << 'EOF'
import asyncio, sys
sys.path.insert(0, '.')
try:
    from app.infra.telegram_notifier import TelegramNotifier
    success = asyncio.run(TelegramNotifier().send_message('System check'))
    print('✅ Telegram OK' if success else '❌ Telegram FAILED')
except Exception as e:
    print(f'❌ Error: {e}')
EOF

# Run component validation
python scripts/validate_execution_layer_simple.py
```

---

## Phase 1: Complete Paper Trading (Days 1-3)

### Goal: Execute 15 More Trades (Reach 20+ Total)

#### Step 1: Start System (If Not Running)

```bash
# Start application
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or use systemd if configured
sudo systemctl start auto-trade 2>/dev/null
```

**Verify Startup**:
```bash
# Check health endpoint
curl http://localhost:8000/health

# Check metrics
curl http://localhost:8000/metrics | python3 -m json.tool
```

#### Step 2: Execute Trades (15 More Needed)

```bash
# Execute trades via script (repeat until 20+ total)
for i in {1..15}; do
  echo "Executing trade $((i+5))..."  # Starting from trade #6
  python scripts/execute_gold_trade.py
  
  # Wait 2-3 hours between trades for realistic testing
  sleep 7200 &
  echo "Next trade in 2 hours... (PID: $!)"
done

# Monitor progress
watch -n 60 'python3 -c "import sqlite3; conn=sqlite3.connect(\"data/vmassit.db\"); c=conn.cursor(); c.execute(\"SELECT COUNT(*) FROM paper_trades WHERE status=\\\"closed\\\"\"); print(f\"Closed trades: {c.fetchone()[0]}/20\"); conn.close()"'
```

**Alternative: Manual Execution**
```bash
# Execute one trade at a time
python scripts/execute_gold_trade.py

# Check result
python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT id, symbol, profit FROM paper_trades ORDER BY id DESC LIMIT 1'); print(f'Latest trade: {c.fetchone()}'); conn.close()"
```

**Target**: 20+ trades over 48-72 hours

#### Step 3: Set Up Monitoring

```bash
# Make monitoring script executable
chmod +x scripts/monitor_deployment.py

# Add to crontab (run every 5 minutes)
crontab -e
# Add: */5 * * * * cd /home/admin/.openclaw/workspace/auto-trade-system && source .venv/bin/activate && python scripts/monitor_deployment.py >> logs/deployment_monitor.log 2>&1

# Test monitoring
python scripts/monitor_deployment.py
```

#### Step 4: Test Failure Scenarios

##### Network Interruption (Day 2)
```bash
# Block API temporarily (adjust domain based on active exchange)
sudo iptables -A OUTPUT -d api.bybit.com -j DROP
sleep 10
sudo iptables -D OUTPUT -d api.bybit.com -j DROP

# Check circuit breaker in logs
grep -i "circuit.*breaker\|connection.*fail" logs/*.log | tail -10
```

##### WebSocket Disconnect (Day 2)
```bash
# Monitor reconnection
watch -n 10 'curl -s http://localhost:8000/metrics 2>/dev/null | python3 -m json.tool 2>/dev/null | grep -A3 websocket'
```

##### API Rate Limiting (Day 3)
```bash
# Rapid API calls to test rate limiter
for i in {1..20}; do
  curl -s http://localhost:8000/health > /dev/null &
done
wait

# Check logs for rate limiting
grep -i "rate.*limit" logs/*.log | tail -5
```

---

## Phase 2: Validation (After 20+ Trades)

### Run Comprehensive Validation

```bash
python scripts/validate_production_readiness.py
```

**Expected Output**:
```
✅ Trade Volume: PASS (20+ trades)
✅ Performance: PASS (win rate ≥ 55%)
✅ Event Store: PASS
✅ Telegram: PASS
✅ Uptime: PASS

✅ ALL CRITICAL CHECKS PASSED
```

### Review Performance Metrics

```bash
python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('data/vmassit.db')
cursor = conn.cursor()

# Get detailed statistics
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN profit > 0 THEN 1 END) as wins,
        ROUND(AVG(CASE WHEN profit > 0 THEN 1 ELSE 0 END) * 100, 2) as win_rate,
        SUM(profit) as total_pnl,
        ROUND(AVG(profit), 2) as avg_profit
    FROM paper_trades 
    WHERE status = 'closed'
""")

total, wins, win_rate, total_pnl, avg_profit = cursor.fetchone()

print("="*60)
print("PERFORMANCE SUMMARY")
print("="*60)
print(f"Total Trades: {total}")
print(f"Wins: {wins}")
print(f"Win Rate: {win_rate}%")
print(f"Total P&L: ${total_pnl:.2f}")
print(f"Avg Profit/Trade: ${avg_profit:.2f}")

# Profit factor
cursor.execute("""
    SELECT 
        SUM(CASE WHEN profit > 0 THEN profit ELSE 0 END),
        SUM(CASE WHEN profit < 0 THEN ABS(profit) ELSE 0 END)
    FROM paper_trades WHERE status = 'closed'
""")
gross_profit, gross_loss = cursor.fetchone()
pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
print(f"Profit Factor: {pf:.2f}")

print("\nGO/NO-GO:")
print(f"  {'✅' if total >= 20 else '❌'} Trades ≥ 20: {total}")
print(f"  {'✅' if win_rate >= 55 else '❌'} Win Rate ≥ 55%: {win_rate}%")
print(f"  {'✅' if pf >= 1.5 else '❌'} Profit Factor ≥ 1.5: {pf:.2f}")

conn.close()
EOF
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
sudo systemctl stop auto-trade 2>/dev/null || pkill -f "uvicorn app.main"

# Create backup
cp data/vmassit.db data/vmassit.db.pre-live.$(date +%Y%m%d_%H%M%S).backup
gzip data/vmassit.db.pre-live.*.backup

# Verify backup
ls -lh data/vmassit.db.pre-live.*.gz
gunzip -t data/vmassit.db.pre-live.*.gz && echo "✅ Backup verified"

# Copy to safe location (optional)
cp data/vmassit.db.pre-live.*.gz /path/to/external/storage/ 2>/dev/null || echo "⚠️ External storage not available"
```

### Update Configuration

Edit `.env`:

```diff
# Change execution mode from paper to semi-auto
- EXECUTION_MODE=paper
+ EXECUTION_MODE=semi-auto

# Set conservative auto-execute threshold
- AUTO_EXECUTE_THRESHOLD_USD=100.0
+ AUTO_EXECUTE_THRESHOLD_USD=50.0

# Verify API keys are correct for live trading
# IMPORTANT: Double-check these before proceeding!
BYBIT_API_KEY=your_LIVE_bybit_key
BYBIT_API_SECRET=your_LIVE_bybit_secret

# If using Binance/MEXC, update their keys too
```

**⚠️ CRITICAL**: Triple-check API keys before restarting!

### Final Health Check

```bash
# Restart with new config
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait 2 minutes for startup
sleep 120

# Verify
curl http://localhost:8000/health
curl http://localhost:8000/metrics | python3 -m json.tool

# Test Telegram
python3 << 'EOF'
import asyncio, sys
sys.path.insert(0, '.')
from app.infra.telegram_notifier import TelegramNotifier
success = asyncio.run(TelegramNotifier().send_message('🚀 System switching to LIVE mode'))
print('✅ Alert sent' if success else '❌ Alert failed')
EOF
```

---

## Phase 4: Go-Live (Production)

### First 24 Hours - Intensive Monitoring

```bash
# Check every hour
while true; do
  echo "=== $(date) ==="
  curl -s http://localhost:8000/metrics 2>/dev/null | python3 -m json.tool 2>/dev/null | grep -E "queue_size|latency|connected"
  
  # Check recent trades
  python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM paper_trades WHERE ts_close > datetime(\"now\", \"-1 hour\")'); print(f'Trades last hour: {c.fetchone()[0]}'); conn.close()"
  
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
systemctl status auto-trade 2>/dev/null || ps aux | grep uvicorn

# View logs
journalctl -u auto-trade -n 100 --no-pager 2>/dev/null || tail -100 logs/*.log

# Restart
sudo systemctl restart auto-trade 2>/dev/null || python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Check database integrity
python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM paper_trades'); print(f'Trades intact: {c.fetchone()[0]}'); conn.close()"
```

### Unexpected Losses

```bash
# Pause trading immediately
curl -X POST http://localhost:8000/api/v1/trading/pause

# Or stop system
pkill -f "uvicorn app.main"

# Review recent trades
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('data/vmassit.db')
c = conn.cursor()
c.execute('SELECT id, symbol, side, profit, ts_close FROM paper_trades ORDER BY ts_close DESC LIMIT 10')
print("Recent trades:")
for row in c.fetchall():
    print(f"  #{row[0]} {row[1]} {row[2]}: ${row[3]:.2f} at {row[4]}")
conn.close()
EOF
```

### Database Issues

```bash
# Restore from backup
sudo systemctl stop auto-trade 2>/dev/null || pkill -f "uvicorn app.main"

# Find latest backup
LATEST_BACKUP=$(ls -t data/vmassit.db.pre-live.*.gz | head -1)
echo "Restoring from: $LATEST_BACKUP"

# Restore
cp "$LATEST_BACKUP" /tmp/
cd /tmp
gunzip vmassit.db.pre-live.*.gz
cp vmassit.db.pre-live.* /home/admin/.openclaw/workspace/auto-trade-system/data/vmassit.db

# Restart
cd /home/admin/.openclaw/workspace/auto-trade-system
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

---

## 📊 Quick Commands Reference

### System Management
```bash
# Start
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Stop
pkill -f "uvicorn app.main"

# Restart
pkill -f "uvicorn app.main" && sleep 2 && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Status
ps aux | grep uvicorn

# Logs
tail -f logs/*.log
```

### Monitoring
```bash
# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics | python3 -m json.tool

# Run validation
python scripts/validate_production_readiness.py

# Monitor logs
tail -f logs/app.log
```

### Database
```bash
# Connect to DB
python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); print('Connected'); conn.close()"

# Check trades
python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM paper_trades'); print(f'Trades: {c.fetchone()[0]}'); conn.close()"

# Backup
cp data/vmassit.db data/vmassit.db.backup.$(date +%Y%m%d_%H%M%S)
```

### Testing
```bash
# Component validation
python scripts/validate_execution_layer_simple.py

# Telegram test
python3 -c "import asyncio, sys; sys.path.insert(0, '.'); from app.infra.telegram_notifier import TelegramNotifier; print('✅ OK' if asyncio.run(TelegramNotifier().send_message('Test')) else '❌ FAIL')"

# Execute single trade
python scripts/execute_gold_trade.py
```

---

## 📞 Support Resources

### Documentation
- **Full Plan**: `PRODUCTION_DEPLOYMENT_PLAN_v2026.md`
- **Status Report**: `PRODUCTION_DEPLOYMENT_STATUS_v2026.md`
- **Quick Start**: `QUICK_START_EXECUTION_LAYER.md`
- **Live Criteria**: `MEXC_LIVE_TRADING_CRITERIA.md`

### Key Scripts
- **Monitor**: `scripts/monitor_deployment.py`
- **Validate**: `scripts/validate_production_readiness.py`
- **Execute Trades**: `scripts/execute_gold_trade.py`
- **Backup**: `scripts/backup_database.sh`

### External Links
- Bybit API: https://bybit-exchange.github.io/docs/
- Binance API: https://binance-docs.github.io/apidocs/
- MEXC API: https://mexcdevelop.github.io/apidocs/

---

## ✅ Final Sign-Off

Before going live, confirm:

- [ ] 20+ paper trades completed
- [ ] Win rate ≥ 55%
- [ ] Profit factor ≥ 1.5
- [ ] All validation checks passed
- [ ] Database backup performed and verified
- [ ] Configuration updated for live trading
- [ ] Team briefed on procedures
- [ ] Emergency plan documented
- [ ] Capital allocation decided

**Authorized By**: _________________________  
**Date**: ___________  
**Time**: ___________

---

*Last Updated: May 17, 2026*  
*Version: 2.0*  
*Previous Version: 1.0 (May 12, 2026 - outdated)*
