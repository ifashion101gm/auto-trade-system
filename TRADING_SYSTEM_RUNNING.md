# 🚀 Trading System - Running Status

## ✅ System Status: OPERATIONAL

**Started**: May 11, 2026  
**Server**: FastAPI on http://0.0.0.0:8000  
**Mode**: Semi-Auto (Safe)  
**Exchange**: Binance Testnet  

---

## 📊 Current Configuration

```bash
Exchange:        BINANCE
Testnet Mode:    TRUE (Safe - No real money)
Execution Mode:  semi-auto (Requires confirmation)
Active Symbol:   BTC/USDT
AI Provider:     OpenRouter (3-tier routing)
Telegram:        Enabled
Database:        SQLite (WAL mode)
```

---

## 🎯 Quick Actions

### 1. Access API Documentation
Open in browser: **http://localhost:8000/docs**

This shows all available endpoints with interactive testing.

### 2. Check System Health
```bash
curl http://localhost:8000/health
```

### 3. Generate Trade Proposal
```bash
curl -X POST http://localhost:8000/api/v1/trading/paper-trading/run-cycle \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "user_id": "test_user"
  }'
```

### 4. View Trade History
```bash
curl http://localhost:8000/api/v1/trading/paper-trading/history
```

### 5. Check AI Status
```bash
curl http://localhost:8000/api/v1/ai/status
```

### 6. Get Exchange Balance
```bash
curl http://localhost:8000/api/v1/trading/balance
```

---

## 🔄 Running a Complete Trading Cycle

The system is currently configured for **semi-auto** mode, which means:

1. **AI analyzes market** and generates trade proposal
2. **You review** the proposal (via Telegram or API)
3. **You confirm** execution (or reject)
4. **System executes** on Binance Testnet
5. **Telegram notification** sent with results

### Example Workflow:

```bash
# Step 1: Generate proposal
curl -X POST http://localhost:8000/api/v1/trading/paper-trading/run-cycle \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC/USDT", "user_id": "user1"}'

# Response will include proposal_id

# Step 2: Review proposal (check Telegram or API response)

# Step 3: Confirm execution
curl -X POST http://localhost:8000/api/v1/trading/confirm-trade/{proposal_id}

# Step 4: Receive Telegram notification with order details
```

---

## 📱 Telegram Notifications

You will receive notifications for:
- ✅ Trade proposals generated
- ✅ Orders executed (with filled price, fees, slippage)
- ✅ Trade exits (with P&L calculations)
- ⚠️ System alerts and errors

**Bot**: Already configured in `.env`  
**Chat ID**: -1003893860648

---

## 🔧 Change Execution Mode

### Switch to Proposal Mode (Manual Review Only)
Edit `.env`:
```bash
EXECUTION_MODE=proposal
```
Then restart server:
```bash
# Stop current server (Ctrl+C in terminal 1)
# Then restart:
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Switch to Fully-Auto (Experts Only)
⚠️ **WARNING**: Only after extensive testing!

```bash
EXECUTION_MODE=fully-auto
```
Restart server as above.

---

## 🛑 Emergency Stop

If you need to pause trading immediately:

```bash
curl -X POST http://localhost:8000/api/v1/ai/pause \
  -H "Content-Type: application/json" \
  -d '{"reason": "Emergency stop"}'
```

To resume:
```bash
curl -X POST http://localhost:8000/api/v1/ai/reset-circuit-breaker
```

---

## 📈 Monitoring Commands

### Check Server Logs
The server is running in terminal 1. View logs there.

### View Recent Trades
```bash
curl http://localhost:8000/api/v1/trading/paper-trading/history?limit=10
```

### Check Database Records
```bash
source .venv/bin/activate
python -c "
from app.storage.db import async_session_maker
from app.storage.models import DecisionJournal, PaperTrades
import asyncio
from sqlalchemy import select

async def check():
    async with async_session_maker() as db:
        decisions = await db.execute(select(DecisionJournal))
        trades = await db.execute(select(PaperTrades))
        print(f'DecisionJournal records: {len(decisions.scalars().all())}')
        print(f'PaperTrades records: {len(trades.scalars().all())}')

asyncio.run(check())
"
```

---

## 🔍 Validation Scripts

Run comprehensive tests anytime:

```bash
# Full system validation
source .venv/bin/activate
python scripts/validate_complete_system.py

# E2E trading cycle test
python scripts/validate_e2e_cycle.py

# Integration test
python scripts/test_complete_integration.py
```

---

## 📝 Important Notes

### Safety Features Active
- ✅ **Testnet Mode**: Using Binance Testnet (no real money)
- ✅ **Semi-Auto**: Requires your confirmation before execution
- ✅ **Circuit Breaker**: Auto-pauses on excessive losses
- ✅ **Risk Management**: Position sizing and stop-loss enforced

### Current Market Data
The system fetches real-time data from Binance:
- Price: ~$81,308 (BTC/USDT)
- Indicators: RSI, MA-20, MA-50, MACD, Volatility
- Updates: Every trading cycle

### AI Analysis
- **Regime Detection**: Identifies market conditions
- **Strategy Selection**: Chooses best strategy for regime
- **Risk Assessment**: Calculates position size and risk level
- **Cost Optimized**: 86% reduction via 3-tier routing

---

## 🚀 Next Steps

1. **Monitor First Trades**: Watch Telegram for notifications
2. **Review Proposals**: Check if AI recommendations make sense
3. **Adjust Parameters**: Modify risk settings if needed
4. **Track Performance**: Monitor P&L over time
5. **Scale Gradually**: Increase automation only after success

---

## 🆘 Troubleshooting

### Server Not Responding?
```bash
# Check if server is running
ps aux | grep uvicorn

# Restart if needed
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Database Locked?
```bash
# Remove lock files
rm data/vmassit.db-shm data/vmassit.db-wal

# Restart server
```

### Want to See Real-Time Logs?
Check terminal 1 where the server is running.

---

## 📞 Support

- **Documentation**: See README.md and guides in repo
- **API Docs**: http://localhost:8000/docs
- **Logs**: Terminal 1 (server output)
- **Validation**: Run scripts in `scripts/` directory

---

**System is LIVE and ready for trading!** 🎉

Start by generating your first trade proposal and monitor the Telegram notifications.
