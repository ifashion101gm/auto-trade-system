# 🚀 Production Deployment Plan - Auto Trade System v2026

**Updated**: May 17, 2026  
**System**: Auto Trade System - Execution Layer Upgrade  
**Status**: ⚠️ **PAPER TRADING VALIDATION IN PROGRESS**  
**Production Ready**: ❌ **No** (requires additional validation)  
**Estimated Time to Production**: 3-5 days  

---

## 📋 Executive Summary

This document provides an **updated and accurate** production deployment plan based on the **current system state** (May 17, 2026). The previous documentation was outdated and showed 0 trades when the system has actually completed **5 paper trades**.

### Current Reality vs. Old Documentation

| Metric | Old Docs Claimed | Actual Current State | Gap |
|--------|------------------|---------------------|-----|
| Paper Trades | 0 | **5 completed** | +5 ✅ |
| Closed Trades | 0 | **5 closed** | +5 ✅ |
| System Mode | Not running | **Paper mode active** | Running ✅ |
| TestNet Runtime | 0 hours | Unknown | Needs verification |
| Database | Empty | **vmassit.db (258KB)** | Has data ✅ |
| BINANCE_TESTNET | true | **false** | Using paper mode |
| EXECUTION_MODE | proposal | **paper** | Safe mode ✅ |

**Key Insight**: The system is further along than documented but still requires validation before handling real capital.

---

## 🎯 Pre-Live Criteria Checklist (Updated)

### 1. Trading Validation Status

**Requirement**: Execute minimum 20 trades with acceptable performance metrics.

**Current Status**: ⚠️ **PARTIALLY COMPLETE** (5/20 trades)

**Trade Statistics** (from database):
- Total Paper Trades: **5**
- Closed Trades: **5**
- Open Trades: **0**
- Completion Rate: **100%** (all trades closed properly)

**Validation Steps Remaining**:
- [ ] Execute 15 more trades to reach 20+ minimum
- [ ] Calculate win rate from 5 completed trades
- [ ] Calculate profit factor
- [ ] Measure maximum drawdown
- [ ] Verify trade execution quality (slippage, fill rates)

**Performance Metrics** (need to calculate from existing 5 trades):
```sql
-- Connect to database and analyze
python3 -c "
import sqlite3
conn = sqlite3.connect('data/vmassit.db')
cursor = conn.cursor()

# Get all closed trades
cursor.execute('''
    SELECT id, symbol, side, entry_price, exit_price, profit, status, ts_open, ts_close
    FROM paper_trades 
    WHERE status = 'closed'
    ORDER BY ts_open DESC
''')
trades = cursor.fetchall()

print(f'Total closed trades: {len(trades)}')
if trades:
    wins = sum(1 for t in trades if t[5] > 0)  # profit column
    losses = sum(1 for t in trades if t[5] <= 0)
    total_profit = sum(t[5] for t in trades)
    gross_profit = sum(t[5] for t in trades if t[5] > 0)
    gross_loss = abs(sum(t[5] for t in trades if t[5] < 0))
    
    win_rate = (wins / len(trades)) * 100 if trades else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    print(f'Wins: {wins}, Losses: {losses}')
    print(f'Win Rate: {win_rate:.2f}%')
    print(f'Total P&L: ${total_profit:.2f}')
    print(f'Profit Factor: {profit_factor:.2f}')
    
    print('\\nRecent Trades:')
    for t in trades[:5]:
        print(f'  Trade #{t[0]}: {t[1]} {t[2]} | Entry: {t[3]} | Exit: {t[4]} | P&L: ${t[5]:.2f}')

conn.close()
"
```

**Target Metrics**:
- Win Rate: ≥ 55% (target 60%+)
- Profit Factor: ≥ 1.5 (target 2.0+)
- Maximum Drawdown: ≤ 15% (target ≤ 10%)
- Risk-Reward Ratio: ≥ 1.5:1 (target 2:1+)

**Status**: [ ] PASS (≥20 trades with good metrics) | [ ] IN PROGRESS (5/20) | [ ] FAIL

---

### 2. System Runtime Validation

**Requirement**: Run continuously for 48+ hours without crashes.

**Current Status**: ❓ **UNKNOWN** (needs verification)

**Verification Steps**:
```bash
# Check systemd service status
systemctl status auto-trade

# Check recent logs for uptime indicators
journalctl -u auto-trade --since "2 days ago" --no-pager | grep -i "started\|uptime"

# Or check application logs
find logs/ -name "*.log" -mtime -2 -exec grep -l "startup\|initialized" {} \;
```

**What to Look For**:
- [ ] No critical errors or crashes in logs
- [ ] Service restarts logged (indicates instability)
- [ ] Continuous operation timestamps
- [ ] WebSocket connection stability

**Action Required**:
1. If system hasn't run 48 hours continuously: Start it now
2. Monitor for next 48 hours
3. Document any downtime incidents

**Start Date**: ___________  
**End Date**: ___________  
**Total Runtime**: _____ hours  
**Downtime Incidents**: _____  
**Status**: [ ] PASS | [ ] FAIL | [ ] NOT STARTED

---

### 3. Failure Handling Verification

**Requirement**: All failure scenarios handled gracefully via circuit breaker and retry mechanisms.

**Current Status**: ⚠️ **COMPONENTS VALIDATED, INTEGRATION TESTING NEEDED**

**Components Already Validated** (via `validate_execution_layer_simple.py`):
- ✅ Circuit Breaker Pattern
- ✅ Rate Limiter (Token Bucket)
- ✅ State Machine Transitions
- ✅ Event Priority Queue

**Integration Tests Required**:
- [ ] Simulate network drop during trade execution
- [ ] Test API rate limit handling
- [ ] Verify order status sync after connection loss
- [ ] Test circuit breaker OPEN/HALF_OPEN/CLOSED transitions
- [ ] Validate automatic reconnection logic
- [ ] Confirm orphaned order detection and repair

**Test Scenarios to Execute**:

#### Scenario 1: Network Interruption
```bash
# Block exchange API temporarily (adjust domain based on active exchange)
sudo iptables -A OUTPUT -d api.bybit.com -j DROP
sleep 10
sudo iptables -D OUTPUT -d api.bybit.com -j DROP

# Observe logs for circuit breaker activation
grep -i "circuit.*breaker\|connection.*fail" logs/*.log | tail -20
```

**Expected Behavior**:
- Circuit breaker opens after consecutive failures
- System pauses trading automatically
- Reconnects after timeout period
- Resumes normal operation

**Result**: [ ] PASS | [ ] FAIL | [ ] NOT TESTED

#### Scenario 2: API Rate Limiting
```bash
# Trigger rapid API calls to test rate limiter
python scripts/test_rate_limiting.py  # Create this script if needed
```

**Expected Behavior**:
- Rate limiter prevents excessive API calls
- Graceful error messages logged
- No system crashes
- Retry mechanism activates

**Result**: [ ] PASS | [ ] FAIL | [ ] NOT TESTED

#### Scenario 3: WebSocket Disconnection
```bash
# Monitor WebSocket stability
curl http://localhost:8000/metrics 2>/dev/null | python -m json.tool | grep -A5 websocket
```

**Expected Behavior**:
- Automatic reconnection within 30 seconds
- Position state preserved
- No data loss during disconnect

**Result**: [ ] PASS | [ ] FAIL | [ ] NOT TESTED

**Overall Status**: [ ] ALL SCENARIOS PASS | [ ] SOME FAILED | [ ] NOT TESTED

---

### 4. Metrics Monitoring & Stability

**Requirement**: Confirm system stability by ensuring EventBus queue size < 100 and average latency < 100ms.

**Current Status**: ⚠️ **NEEDS MONITORING SETUP**

**Monitoring Setup**:
```bash
# Check if metrics endpoint is available
curl http://localhost:8000/metrics 2>/dev/null || echo "Metrics endpoint not available (system may not be running)"

# If system is running, check key metrics
curl -s http://localhost:8000/metrics 2>/dev/null | python3 -m json.tool 2>/dev/null | grep -E "queue_size|latency|dead_letter"
```

**Key Metrics to Track**:

| Metric | Threshold | Current | Status |
|--------|-----------|---------|--------|
| EventBus Queue Size | < 100 | Unknown | ⏸️ |
| Dead Letter Count | = 0 | Unknown | ⏸️ |
| WebSocket Latency | < 100ms | Unknown | ⏸️ |
| WebSocket Uptime | > 95% | Unknown | ⏸️ |
| Circuit Breaker State | CLOSED | Unknown | ⏸️ |
| Reconnection Count | < 5/day | Unknown | ⏸️ |

**Monitoring Script Setup**:
```bash
# Create monitoring cron job (runs every 5 minutes)
chmod +x scripts/monitor_deployment.py
crontab -e

# Add this line:
*/5 * * * * cd /home/admin/.openclaw/workspace/auto-trade-system && source .venv/bin/activate && python scripts/monitor_deployment.py >> logs/deployment_monitor.log 2>&1
```

**Stability Criteria** (must maintain for 48 hours):
- [ ] Queue size remains < 100
- [ ] Average latency stays < 100ms
- [ ] No dead letter buildup (count = 0)
- [ ] WebSocket uptime > 95%
- [ ] No unexpected circuit breaker activations

**Status**: [ ] PASS | [ ] FAIL | [ ] MONITORING IN PROGRESS

---

### 5. EventStore Audit

**Requirement**: Review event logs for anomalies or unexpected state transitions.

**Current Status**: ⚠️ **NEEDS AUDIT** (database has trades but events not reviewed)

**Audit Queries**:
```bash
# Connect to PostgreSQL (or SQLite if using)
python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('data/vmassit.db')
cursor = conn.cursor()

# Check if order_events table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_events'")
if cursor.fetchone():
    print("✅ order_events table exists")
    
    # View recent critical events
    cursor.execute("""
        SELECT id, trade_id, event_type, created_at
        FROM order_events
        ORDER BY created_at DESC
        LIMIT 20
    """)
    events = cursor.fetchall()
    print(f"\nRecent Events ({len(events)} shown):")
    for e in events:
        print(f"  {e[2]} | Trade: {e[1]} | {e[3]}")
    
    # Count events by type
    cursor.execute("""
        SELECT event_type, COUNT(*) as count
        FROM order_events
        GROUP BY event_type
        ORDER BY count DESC
    """)
    print("\nEvent Distribution:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    # Check for SYNC_MISMATCH events
    cursor.execute("""
        SELECT COUNT(*) FROM order_events WHERE event_type = 'SYNC_MISMATCH'
    """)
    mismatch_count = cursor.fetchone()[0]
    print(f"\n⚠️ SYNC_MISMATCH events: {mismatch_count}")
else:
    print("ℹ️ order_events table does not exist (using simplified logging)")

conn.close()
EOF
```

**Anomalies to Watch For**:
- [ ] Excessive `SYNC_MISMATCH` events (>5 per day)
- [ ] Orphaned orders (submitted without fill/cancel)
- [ ] Invalid state transitions
- [ ] Duplicate events for same trade
- [ ] Missing critical events in trade lifecycle

**Audit Results**:
- Total Events Reviewed: _____
- Anomalies Found: _____
- Critical Issues: _____
- Resolution Actions: ________________

**Status**: [ ] CLEAN (no anomalies) | [ ] ISSUES FOUND | [ ] NOT AUDITED

---

### 6. Telegram Alerts Configuration

**Requirement**: Ensure Telegram alerts are active and correctly notifying for critical events.

**Current Status**: ✅ **CONFIGURED** (bot token and chat ID set in .env)

**Configuration** (from `.env`):
```bash
TELEGRAM_BOT_TOKEN=8481072337:AAHvyrOAsQv5XuYY6Ap2NF3h7BQIBnoseTk
TELEGRAM_CHAT_ID=-1003893860648
```

**Alert Testing**:
```bash
# Test basic message delivery
python3 << 'EOF'
import asyncio
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

try:
    from app.infra.telegram_notifier import TelegramNotifier
    
    async def test():
        notifier = TelegramNotifier()
        success = await notifier.send_message(
            '🧪 Production Deployment Test\n\nSystem validation in progress.\nTimestamp: ' + 
            __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        if success:
            print('✅ Telegram Notifications: WORKING')
        else:
            print('❌ Telegram Notifications: FAILED')
        return success
    
    result = asyncio.run(test())
except Exception as e:
    print(f'❌ Error testing Telegram: {e}')
EOF
```

**Alert Types to Verify**:
- [ ] Trade entry notifications (with order details)
- [ ] Trade exit notifications (with P&L summary)
- [ ] System error alerts
- [ ] Daily summary reports
- [ ] Circuit breaker activation warnings
- [ ] Sync mismatch alerts

**Test Results**:
| Alert Type | Sent | Received | Formatted Correctly | Timestamp |
|------------|------|----------|---------------------|-----------|
| Basic Message | [ ] | [ ] | [ ] | |
| Trade Entry | [ ] | [ ] | [ ] | |
| Trade Exit | [ ] | [ ] | [ ] | |
| Error Alert | [ ] | [ ] | [ ] | |

**Status**: [ ] ALL ALERTS WORKING | [ ] SOME FAILED | [ ] NOT TESTED

---

### 7. Database Backup

**Requirement**: Perform a full database backup before switching to live trading.

**Current Status**: ⚠️ **BACKUP NOT PERFORMED FOR PRODUCTION TRANSITION**

**Current Database**:
- File: `data/vmassit.db`
- Size: 258 KB
- Last Modified: May 12, 2026
- Contains: 5 paper trades

**Pre-Mainnet Backup Procedure**:
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system

# Option 1: Use backup script (if PostgreSQL)
./scripts/backup_database.sh --retention 90

# Option 2: Manual backup (for SQLite)
cp data/vmassit.db data/vmassit.db.backup.$(date +%Y%m%d_%H%M%S)
gzip data/vmassit.db.backup.*

# Verify backup
ls -lh data/vmassit.db.backup.*.gz
gunzip -t data/vmassit.db.backup.*.gz && echo "✅ Backup integrity verified"

# Copy to safe location
cp data/vmassit.db.backup.*.gz /path/to/external/storage/ 2>/dev/null || echo "⚠️ External storage not configured"
```

**Backup Verification**:
- [ ] Backup file created successfully
- [ ] File integrity verified (gunzip -t passes)
- [ ] Backup size reasonable (>1KB indicates data present)
- [ ] Backup stored in secure location
- [ ] Restore procedure tested (optional but recommended)

**Backup Details**:
- Backup File: `vmassit.db.backup.YYYYMMDD_HHMMSS.gz`
- Backup Size: _____ KB
- Backup Location: `data/`
- Backup Date: ___________
- Verified By: ___________

**Status**: [ ] BACKUP COMPLETE | [ ] PENDING | [ ] FAILED

---

## 📊 Performance Analysis of Existing 5 Trades

**Action Required**: Analyze the 5 completed paper trades to establish baseline performance.

```bash
python3 << 'EOF'
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/vmassit.db')
cursor = conn.cursor()

# Get detailed trade statistics
cursor.execute("""
    SELECT 
        COUNT(*) as total_trades,
        COUNT(CASE WHEN profit > 0 THEN 1 END) as winning_trades,
        COUNT(CASE WHEN profit <= 0 THEN 1 END) as losing_trades,
        ROUND(AVG(profit), 2) as avg_profit,
        SUM(profit) as total_pnl,
        MAX(profit) as best_trade,
        MIN(profit) as worst_trade,
        ROUND(AVG(CASE WHEN profit > 0 THEN profit END), 2) as avg_win,
        ROUND(AVG(CASE WHEN profit < 0 THEN ABS(profit) END), 2) as avg_loss
    FROM paper_trades 
    WHERE status = 'closed'
""")

stats = cursor.fetchone()
total, wins, losses, avg_profit, total_pnl, best, worst, avg_win, avg_loss = stats

print("="*60)
print("TRADE PERFORMANCE ANALYSIS (5 Completed Trades)")
print("="*60)
print(f"Total Trades: {total}")
print(f"Winning Trades: {wins}")
print(f"Losing Trades: {losses}")
print(f"Win Rate: {(wins/total*100) if total > 0 else 0:.2f}%")
print(f"\nProfitability:")
print(f"  Total P&L: ${total_pnl:.2f}")
print(f"  Average Profit/Trade: ${avg_profit:.2f}")
print(f"  Best Trade: ${best:.2f}")
print(f"  Worst Trade: ${worst:.2f}")
print(f"\nRisk Metrics:")
if avg_loss and avg_loss > 0:
    risk_reward = avg_win / avg_loss if avg_win else 0
    print(f"  Average Win: ${avg_win:.2f}")
    print(f"  Average Loss: ${avg_loss:.2f}")
    print(f"  Risk-Reward Ratio: {risk_reward:.2f}:1")
else:
    print(f"  No losing trades yet (excellent!)")

# Calculate profit factor
cursor.execute("""
    SELECT 
        SUM(CASE WHEN profit > 0 THEN profit ELSE 0 END) as gross_profit,
        SUM(CASE WHEN profit < 0 THEN ABS(profit) ELSE 0 END) as gross_loss
    FROM paper_trades 
    WHERE status = 'closed'
""")
gross_profit, gross_loss = cursor.fetchone()
profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
print(f"  Profit Factor: {profit_factor:.2f}")

print("\n" + "="*60)
print("GO/NO-GO CRITERIA CHECK")
print("="*60)

checks = []
win_rate = (wins/total*100) if total > 0 else 0
checks.append(("Win Rate ≥ 55%", win_rate >= 55, f"{win_rate:.2f}%"))
checks.append(("Profit Factor ≥ 1.5", profit_factor >= 1.5, f"{profit_factor:.2f}"))
checks.append(("Total Trades ≥ 20", total >= 20, f"{total}/20"))

for criterion, passed, value in checks:
    status = "✅ PASS" if passed else "❌ FAIL" if total >= 20 else "⏸️ NEED MORE TRADES"
    print(f"{status} | {criterion}: {value}")

conn.close()
EOF
```

---

## 🚦 GO/NO-GO Decision Matrix (Updated)

### Mandatory Criteria (ALL Must Pass)

| # | Criterion | Required | Current | Status |
|---|-----------|----------|---------|--------|
| 1 | **Execution Layer Components** | Validated | ✅ Validated | ✅ PASS |
| 2 | **Paper Trades Executed** | ≥ 20 trades | 5 trades | ⏸️ 5/20 |
| 3 | **Win Rate** | ≥ 55% | Need calc | ⏸️ Pending |
| 4 | **Profit Factor** | ≥ 1.5 | Need calc | ⏸️ Pending |
| 5 | **System Runtime** | ≥ 48 hours | Unknown | ❓ Verify |
| 6 | **Failure Scenarios Tested** | All pass | Not tested | ❌ Pending |
| 7 | **Metrics Within Thresholds** | Stable | Not monitored | ❌ Pending |
| 8 | **Telegram Alerts** | Working | Configured | ⚠️ Test |
| 9 | **Database Backup** | Complete | Not done | ❌ Pending |

### Decision Rule

**GO Decision**: ALL criteria must PASS ✅  
**NO-GO Decision**: ANY criterion FAILS ❌

**Current Decision**: ⏸️ **IN PROGRESS** - 5/20 trades completed, need 15 more + validation

---

## 📅 Updated Deployment Timeline

### Phase 1: Complete Paper Trading Validation (Days 1-3)
**Duration**: 48-72 hours  
**Goal**: Execute 15 more trades and reach 20+ total

- [ ] **Day 1**: Start/restart system, execute 5-7 trades
- [ ] **Day 2**: Execute 5-7 more trades, test failure scenarios
- [ ] **Day 3**: Execute remaining trades, monitor metrics
- [ ] **Throughout**: Set up continuous monitoring

**Commands**:
```bash
# Start system (if not running)
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Execute trades (repeat until 20+ total)
python scripts/execute_gold_trade.py

# Monitor progress
watch -n 60 'python3 -c "import sqlite3; conn=sqlite3.connect(\"data/vmassit.db\"); c=conn.cursor(); c.execute(\"SELECT COUNT(*) FROM paper_trades WHERE status=\\\"closed\\\"\"); print(f\"Closed trades: {c.fetchone()[0]}\"); conn.close()"'
```

### Phase 2: Performance Analysis & Failure Testing (Day 4)
**Duration**: 4-6 hours  
**Goal**: Validate performance and resilience

- [ ] Run comprehensive performance analysis
- [ ] Execute all 3 failure scenarios
- [ ] Audit EventStore/logs for anomalies
- [ ] Verify Telegram alerts working
- [ ] Check metrics stability

**Commands**:
```bash
# Run validation script
python scripts/validate_production_readiness.py

# Test failure scenarios (see Section 3 above)
# ... execute each scenario ...

# Analyze performance (see Section 8 above)
python3 analyze_performance.py  # Create this script
```

### Phase 3: Pre-Launch Preparation (Day 5)
**Duration**: 1-2 hours  
**Goal**: Prepare for mainnet transition

- [ ] Perform final database backup
- [ ] Update configuration for live trading
- [ ] Switch API keys to production credentials
- [ ] Final health check
- [ ] Team briefing

**Commands**:
```bash
# Stop system
sudo systemctl stop auto-trade 2>/dev/null || pkill -f "uvicorn app.main"

# Backup database
cp data/vmassit.db data/vmassit.db.pre-live.$(date +%Y%m%d_%H%M%S).backup
gzip data/vmassit.db.pre-live.*.backup

# Update .env for live trading (carefully!)
# Change: EXECUTION_MODE=paper → EXECUTION_MODE=semi-auto
# Verify: API keys are correct for live trading
# Set: AUTO_EXECUTE_THRESHOLD_USD=50.0 (conservative start)

# Restart system
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Phase 4: Go-Live with Live Capital (Days 6-7)
**Duration**: First 48 hours critical  
**Goal**: Deploy with minimal risk

- [ ] **Hour 0-24**: Start with small positions ($10-$20/trade)
- [ ] **Hour 24-48**: Monitor closely, verify everything works
- [ ] **Day 3-7**: Gradually increase position sizes if performing well
- [ ] **Week 2+**: Consider switching to fully-auto mode

**Monitoring**:
```bash
# Check every hour for first 24 hours
while true; do
  curl -s http://localhost:8000/metrics 2>/dev/null | python3 -m json.tool 2>/dev/null | grep -E "queue_size|latency"
  sleep 3600
done
```

**Estimated Total Time**: 5-7 days from today

---

## 🔍 Monitoring Dashboard Setup

### Real-Time Metrics Endpoint

```bash
# Health check
curl http://localhost:8000/health

# Detailed metrics
curl http://localhost:8000/metrics | python3 -m json.tool
```

### Automated Monitoring Script

Create or update `scripts/monitor_deployment.py`:

```python
#!/usr/bin/env python3
"""Monitor deployment metrics and alert on threshold violations."""
import asyncio
import httpx
import sqlite3
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

METRICS_URL = "http://localhost:8000/metrics"
DB_PATH = "data/vmassit.db"
THRESHOLDS = {
    'queue_size': 100,
    'avg_latency_ms': 100,
    'dead_letter_count': 0
}

async def check_metrics():
    """Check system metrics via API endpoint."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(METRICS_URL, timeout=5.0)
            if response.status_code != 200:
                print(f"[{datetime.now()}] ❌ Metrics endpoint unavailable: {response.status_code}")
                return False
            
            metrics = response.json()
            
            # Check EventBus
            event_bus = metrics.get('event_bus', {})
            queue_size = event_bus.get('queue_size', 0)
            dead_letters = event_bus.get('dead_letter_count', 0)
            
            # Check WebSocket
            websocket = metrics.get('websocket', {})
            latency = websocket.get('avg_latency_ms', 0)
            
            # Validate thresholds
            alerts = []
            if queue_size >= THRESHOLDS['queue_size']:
                alerts.append(f"⚠️ Queue size high: {queue_size}")
            if dead_letters > THRESHOLDS['dead_letter_count']:
                alerts.append(f"🚨 Dead letters detected: {dead_letters}")
            if latency >= THRESHOLDS['avg_latency_ms']:
                alerts.append(f"⚠️ High latency: {latency:.0f}ms")
            
            # Print status
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] Queue: {queue_size} | Latency: {latency:.0f}ms | Dead: {dead_letters}")
            
            if alerts:
                for alert in alerts:
                    print(f"  {alert}")
                return False
            
            return True
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error checking metrics: {e}")
        return False

def check_trade_progress():
    """Check paper trade progress."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status='closed'")
        closed_trades = cursor.fetchone()[0]
        conn.close()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] 📊 Closed trades: {closed_trades}/20")
        
        return closed_trades >= 20
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error checking trades: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(check_metrics())
    check_trade_progress()
```

Run every 5 minutes:
```bash
chmod +x scripts/monitor_deployment.py
crontab -e
# Add: */5 * * * * cd /home/admin/.openclaw/workspace/auto-trade-system && source .venv/bin/activate && python scripts/monitor_deployment.py >> logs/deployment_monitor.log 2>&1
```

---

## 📝 Immediate Action Items

### Today (Day 0) - Start Validation

1. **Verify System State**
   ```bash
   # Check if system is running
   ps aux | grep uvicorn
   
   # Check database
   python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM paper_trades'); print(f'Trades: {c.fetchone()[0]}'); conn.close()"
   
   # Check logs
   ls -lth logs/*.log | head -5
   ```

2. **Start/Restart System** (if not running)
   ```bash
   cd /home/admin/.openclaw/workspace/auto-trade-system
   source .venv/bin/activate
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Execute First Batch of Trades**
   ```bash
   # Execute 5 trades today
   for i in {1..5}; do
     echo "Executing trade $i..."
     python scripts/execute_gold_trade.py
     sleep 300  # Wait 5 minutes between trades
   done
   ```

4. **Set Up Monitoring**
   ```bash
   chmod +x scripts/monitor_deployment.py
   crontab -e
   # Add monitoring cron job (see above)
   ```

### Tomorrow (Day 1) - Continue Validation

- [ ] Execute 5 more trades
- [ ] Test network failure scenario
- [ ] Verify Telegram alerts received
- [ ] Check metrics throughout day
- [ ] Review logs for errors

### Day 2-3 - Complete Trade Volume

- [ ] Execute remaining 10 trades to reach 20+
- [ ] Test API rate limiting scenario
- [ ] Test WebSocket disconnection scenario
- [ ] Collect performance data
- [ ] Monitor metrics continuously

### Day 4 - Validation & Analysis

- [ ] Run comprehensive validation script
- [ ] Analyze performance metrics
- [ ] Audit logs/EventStore
- [ ] Verify all alerts functioning
- [ ] Assess system stability

### Day 5 - Pre-Launch Prep

- [ ] Perform database backup
- [ ] Update configuration for live trading
- [ ] Final health check
- [ ] Team briefing

### Day 6-7 - Go-Live

- [ ] Deploy with small capital
- [ ] Monitor intensively for 48 hours
- [ ] Gradually scale if successful

---

## 🚨 Emergency Procedures

### System Crash
```bash
# Check status
systemctl status auto-trade 2>/dev/null || ps aux | grep uvicorn

# View recent logs
journalctl -u auto-trade -n 100 --no-pager 2>/dev/null || tail -100 logs/*.log

# Restart
sudo systemctl restart auto-trade 2>/dev/null || python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

### Unexpected Losses (Once Live)
```bash
# Pause trading immediately
curl -X POST http://localhost:8000/api/v1/trading/pause

# Or stop system completely
pkill -f "uvicorn app.main"

# Review recent trades
python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT id, symbol, profit FROM paper_trades ORDER BY ts_close DESC LIMIT 10'); [print(row) for row in c.fetchall()]; conn.close()"
```

### Database Issues
```bash
# Restore from backup
cp data/vmassit.db.backup.*.gz /tmp/
cd /tmp && gunzip vmassit.db.backup.*.gz
cp vmassit.db.backup.* data/vmassit.db
```

---

## 📞 Support Resources

### Documentation
- **This Plan**: `PRODUCTION_DEPLOYMENT_PLAN_v2026.md` (this file)
- **Quick Reference**: `PRODUCTION_DEPLOYMENT_QUICKREF_v2026.md` (create next)
- **Status Report**: `PRODUCTION_DEPLOYMENT_STATUS_v2026.md` (create next)
- **Original Quick Start**: `QUICK_START_EXECUTION_LAYER.md`

### Scripts
- **Monitor**: `scripts/monitor_deployment.py`
- **Validate**: `scripts/validate_production_readiness.py`
- **Execute Trades**: `scripts/execute_gold_trade.py`
- **Backup**: `scripts/backup_database.sh`

### External Links
- Bybit API: https://bybit-exchange.github.io/docs/
- Binance API: https://binance-docs.github.io/apidocs/
- MEXC API: https://mexcdevelop.github.io/apidocs/
- PostgreSQL: https://www.postgresql.org/docs/

---

## ✅ Final Checklist Before Going Live

- [ ] Read all documentation thoroughly
- [ ] Completed 20+ paper trades
- [ ] Win rate ≥ 55%
- [ ] Profit factor ≥ 1.5
- [ ] All failure scenarios tested
- [ ] Metrics within thresholds for 48+ hours
- [ ] EventStore/log audit complete
- [ ] Telegram alerts verified
- [ ] Database backup performed
- [ ] Configuration updated for live trading
- [ ] Team briefed on procedures
- [ ] Emergency plan documented
- [ ] Capital allocation decided

**Authorized By**: _________________________  
**Date**: ___________  
**Time**: ___________

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | May 12, 2026 | Initial deployment documentation (outdated) |
| 2.0 | May 17, 2026 | Updated with actual system state (5 trades completed) |

---

*Last Updated: May 17, 2026*  
*Maintained By: Auto Trade System Team*  
*Next Review: After reaching 20 trades*
