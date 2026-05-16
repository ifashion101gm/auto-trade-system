# Telegram Notification Monitoring Guide
## Bybit Demo Paper Trading Validation Cycle

---

## ✅ Current Status

**Telegram Configuration:** ACTIVE
- Bot Token: Configured
- Chat ID: -1003893860648
- Notifications: ENABLED

**Last Test:** May 16, 2026 05:14 UTC - ✅ Sent successfully

---

## 📱 What to Monitor in Telegram

### 1. Trade Rejection Reports

You will receive notifications when trades are rejected:

**Quality Filter Rejections:**
```
⚠️ Trade Rejected by Quality Filter

Symbol: XAUUSDT
Reason: Low confidence score
Quality Score: 45/100
Cycle Time: 8500ms
```

**Risk Engine Rejections:**
```
❌ Trade Rejected by Risk Engine

Symbol: XAUUSDT
Reason: Position size too large
Position Value: $1,400.00
Max Allowed: $1.50 (1.5% of balance)
Balance: $100.00
```

### 2. Successful Trade Executions

When trades pass all validations and execute:

**Entry Notification:**
```
✅ New Trade Executed

Regime: Normal
Strategy: momentum
Confidence: 70.00%

Side: BUY
Entry Price: $4,543.33
Stop Loss: $4,452.46
Take Profit: $4,725.06
Leverage: 2x

Trade ID: #123
Order ID: xxx-xxx-xxx
Status: EXECUTED ✅

Cycle Time: 12000ms
```

**Exit Notification:**
```
✅ Trade Closed

Trade ID: #123
Symbol: XAUUSDT
Side: LONG
Leverage: 2x

Entry Price: $4,543.33
Exit Price: $4,600.00
Quantity: 0.001100

P&L: $+0.62 (+1.25%)
Status: Profit

Duration: 2h 15m
```

### 3. System Alerts & Warnings

**WebSocket Connection Issues:**
```
⚠️ WebSocket Disconnected

Exchange: Bybit Demo
Reconnecting... (attempt 1/5)
```

**Circuit Breaker Activation:**
```
🚨 Circuit Breaker ACTIVATED

Reason: Consecutive losses exceeded threshold
Trading: DISABLED
Recovery Timeout: 60s
```

**Reconciliation Warnings:**
```
⚠️ Position Reconciliation Alert

Database Positions: 1
Exchange Positions: 0
Action: Ghost position detected
```

**Daily Health Reports:**
```
📊 Daily Health Check - Bybit Demo

Balance: $100.00
Open Positions: 0
Total Trades Today: 5
Win Rate: 60%
P&L: $+2.50
```

---

## 🔍 How to Interpret Notifications

### Normal Operation
- ✅ Green checkmarks = Successful operations
- Trade entries and exits with P&L
- Periodic health reports

### Warnings (Yellow/Orange)
- ⚠️ Trade rejections by quality filter (normal protection)
- WebSocket reconnections (auto-recovering)
- Session boundaries (outside trading hours)

### Critical Alerts (Red)
- ❌ Risk engine rejections (position sizing issues)
- 🚨 Circuit breaker activations (stop trading)
- Failed API connections (persistent errors)

---

## 📊 Monitoring Commands

### Quick Status Check
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
python scripts/monitor_telegram_notifications.py
```

### View Recent Logs
```bash
# Last 20 trade cycle attempts
tail -20 logs/trades_*.log | grep "STEP 5: Sending"

# Recent rejections
grep "Trade rejected" logs/trades_*.log | tail -10

# System errors
grep "ERROR\|CRITICAL" logs/*.log | tail -20
```

### Database Status
```bash
python -c "
import asyncio
from app.database.connection import async_session_maker
from sqlalchemy import select, func
from app.database.models import PaperTrades

async def check():
    async with async_session_maker() as db:
        result = await db.execute(
            select(func.count(PaperTrades.id)).where(
                PaperTrades.user_id == 'default_user',
                PaperTrades.exchange == 'bybit'
            )
        )
        print(f'Total Bybit Demo Trades: {result.scalar() or 0}')

asyncio.run(check())
"
```

---

## ⏰ Trading Sessions

The system only trades during these windows (UTC):

- **London Session:** 07:50 - 10:30 UTC
- **New York Session:** 13:20 - 16:30 UTC

Outside these hours, you'll see:
- "Outside trading session" messages in logs
- No new trade proposals
- System in monitoring mode only

---

## 🚨 Common Issues & Solutions

### Issue 1: All Trades Rejected (Position Size)

**Symptom:** Multiple rejection notifications with "Position size too large"

**Cause:** AI orchestrator uses hardcoded max_position_size=1000

**Solution:** 
```python
# Fix in app/ai_agents/orchestrator.py line 207
# Change from:
"max_position_size": 1000,
# To:
"max_position_size": 5.0,  # $100 × 0.5% risk × 10x leverage
```

### Issue 2: No Notifications Received

**Check:**
1. Telegram bot is running
2. Chat ID is correct in .env
3. Internet connectivity
4. Bot token hasn't expired

**Test:**
```bash
python -c "
import asyncio
from app.notifications.notifier import TelegramNotifier

async def test():
    notifier = TelegramNotifier()
    success = await notifier.send_message('🧪 Test message')
    print('✅ Success' if success else '❌ Failed')

asyncio.run(test())
"
```

### Issue 3: Too Many Rejection Notifications

**Solution:** Enable deduplication (already implemented)
- Same rejection type suppressed for 1 hour
- Prevents notification spam

---

## 📈 Expected Notification Frequency

**During Trading Sessions:**
- Every 30-60 minutes: Trade cycle attempt
- If rejected: Immediate rejection report
- If executed: Entry + later exit notification

**Outside Trading Sessions:**
- Minimal activity
- Occasional system health checks
- No trade proposals

**Daily Summary:**
- 1 daily health report (if configured)
- Summary of day's performance

---

## 🔔 Setting Up Alerts

### Cron Job for Regular Monitoring
```bash
# Add to crontab
crontab -e

# Check status every hour
0 * * * * cd /home/admin/.openclaw/workspace/auto-trade-system && python scripts/monitor_telegram_notifications.py >> logs/cron/telegram_monitor.log 2>&1

# Send daily summary at 6 PM UTC
0 18 * * * cd /home/admin/.openclaw/workspace/auto-trade-system && python scripts/bybit_demo_validation_report.py >> logs/cron/daily_report.log 2>&1
```

---

## 📞 Support & Troubleshooting

If Telegram notifications stop working:

1. **Check Configuration:**
   ```bash
   grep TELEGRAM .env
   ```

2. **Test Connection:**
   ```bash
   python scripts/test_notifier_singleton.py
   ```

3. **View Recent Errors:**
   ```bash
   grep -i "telegram\|bot" logs/*.log | grep ERROR | tail -10
   ```

4. **Restart Services:**
   ```bash
   pkill -f "worker_gold_bot"
   pkill -f "uvicorn"
   # Wait 5 seconds, then restart
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
   python -m app.worker_gold_bot &
   ```

---

## 📝 Notes

- All notifications are logged to `logs/trades_*.log`
- Deduplication prevents spam (1-hour cooldown per rejection type)
- WebSocket disconnections auto-reconnect (up to 5 attempts)
- Circuit breaker protects against consecutive losses
- Reconciliation runs every 2 minutes to detect discrepancies

---

**Last Updated:** May 16, 2026
**Status:** ✅ Monitoring Active
