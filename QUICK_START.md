# 🚀 Quick Start Checklist

Use this checklist to get the Auto Trade System up and running in under 15 minutes.

---

## ⚡ Prerequisites (5 minutes)

### 1. System Requirements
- [ ] Python 3.11+ installed (required)
- [ ] Git installed
- [ ] Text editor (VS Code, nano, vim, etc.)

### 2. Exchange Accounts
- [ ] Bybit account for Demo Trading (https://www.bybit.com/en/trade/demo)
- [ ] API keys generated FROM demo mode interface (required for demo trading)
- [ ] Alternative: Binance testnet (https://testnet.binance.vision/)

### 3. Optional but Recommended
- [ ] Telegram account (for notifications)
- [ ] OpenRouter account (https://openrouter.ai/ for AI enhancement)
- [ ] Redis server installed (for rate limiting)

---

## 📦 Installation (5 minutes)

### Step 1: Clone Repository
```bash
git clone <repository_url>
cd auto-trade-system
```

### Step 2: Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
# Copy example config
cp .env.example .env

# Edit with your credentials
nano .env  # or use your preferred editor
```

**Minimum Required Changes:**
```bash
TRADING_API_SECRET=<generate_with: openssl rand -hex 32>

# Bybit Demo Trading (Primary)
BYBIT_DEMO_API_KEY=your_demo_api_key_here
BYBIT_DEMO_API_SECRET=your_demo_api_secret_here
BYBIT_USE_DEMO_DOMAIN=true  # Use api-demo.bybit.com

# Alternative: Binance Testnet
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=true
```

---

## 🧪 Initial Setup (3 minutes)

### Step 1: Initialize Database
```bash
python -c "from app.storage.db import init_db; import asyncio; asyncio.run(init_db())"
```

Expected output:
```
✅ Database initialized successfully
```

### Step 2: Run Validation Script
```bash
python scripts/validate_complete_system.py
```

Expected output:
```
✅ Configuration: All API keys loaded
✅ Database: SQLite initialized with WAL mode
✅ AI Orchestrator: Parallel agents operational
✅ Exchange Manager: Multi-exchange support
✅ System Status: READY FOR TRADING
```

### Step 3: Start Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

## ✅ Verification (2 minutes)

### Test 1: Check API Docs
Open browser: `http://localhost:8000/docs`

You should see the FastAPI Swagger UI with all endpoints listed.

### Test 2: Generate First Trade Proposal

```bash
curl -X POST http://localhost:8000/trading/paper-trading/run-cycle \
  -H "Content-Type: application/json" \
  -d '{
    "market_data": {
      "symbol": "BTC/USDT",
      "current_price": 45000.0,
      "volatility": 0.45
    }
  }'
```

Expected response:
```json
{
  "status": "success",
  "trade_proposal": {
    "symbol": "BTC/USDT",
    "side": "LONG",
    "entry_price": 45000.0,
    "stop_loss": 44100.0,
    "take_profit": 46800.0
  },
  "cycle_time_ms": 169.35
}
```

### Test 3: Check Database
```bash
python -c "
from app.storage.db import async_session_maker
from app.storage.models import DecisionJournal
import asyncio

async def check():
    async with async_session_maker() as db:
        from sqlalchemy import select
        result = await db.execute(select(DecisionJournal))
        records = result.scalars().all()
        print(f'DecisionJournal records: {len(records)}')

asyncio.run(check())
"
```

Expected output:
```
DecisionJournal records: 1
```

---

## 🎯 First Trading Cycle

### Option A: Paper Trading (Recommended for Beginners)

1. **Keep testnet enabled** (default in `.env`):
   ```bash
   BINANCE_TESTNET=true
   EXECUTION_MODE=proposal
   ```

2. **Generate proposal**:
   ```bash
   curl -X POST http://localhost:8000/trading/paper-trading/run-cycle \
     -H "Content-Type: application/json" \
     -d '{"market_data": {"symbol": "BTC/USDT", "current_price": 45000.0}}'
   ```

3. **Review proposal** in response

4. **Manually execute** on Binance Testnet if desired

5. **Monitor results** via Telegram or API

### Option B: Semi-Auto Trading (Recommended for Production)

1. **Configure semi-auto mode**:
   ```bash
   EXECUTION_MODE=semi-auto
   ```

2. **Restart server**:
   ```bash
   # Stop current server (Ctrl+C)
   uvicorn app.main:app --reload
   ```

3. **Generate proposal** (same as above)

4. **Confirm execution**:
   ```bash
   curl -X POST http://localhost:8000/trading/confirm-trade/{proposal_id}
   ```

5. **Receive Telegram notification** with order details

### Option C: Fully-Auto Trading (Experts Only)

⚠️ **WARNING:** Only use after extensive testing!

1. **Ensure testnet first**:
   ```bash
   BINANCE_TESTNET=true
   EXECUTION_MODE=fully-auto
   ```

2. **Restart server**

3. **Generate proposal** → **Auto-executes immediately**

4. **Monitor closely** via Telegram

5. **After 100+ successful testnet trades**, consider mainnet:
   ```bash
   BINANCE_TESTNET=false  # REAL MONEY NOW!
   ```

---

## 🔧 Common Configurations

### Configuration 1: Conservative (Beginners)
```bash
BINANCE_TESTNET=true
EXECUTION_MODE=proposal
ACTIVE_EXCHANGE=binance
MEXC_DEFAULT_MARKET_TYPE=spot  # Lower risk than futures
```

### Configuration 2: Balanced (Most Users) ⭐
```bash
BINANCE_TESTNET=true
EXECUTION_MODE=semi-auto
ACTIVE_EXCHANGE=binance
MEXC_DEFAULT_MARKET_TYPE=futures
```

### Configuration 3: Aggressive (Experts)
```bash
BINANCE_TESTNET=false  # LIVE MONEY
EXECUTION_MODE=fully-auto
ACTIVE_EXCHANGE=binance
MEXC_DEFAULT_MARKET_TYPE=futures
```

---

## 📊 Monitoring

### Check System Status
```bash
curl http://localhost:8000/ai/status
```

### View Trade History
```bash
curl http://localhost:8000/trading/paper-trading/history
```

### Check Exchange Balance
```bash
curl http://localhost:8000/trading/balance
```

### Pause Trading (Emergency)
```bash
curl -X POST http://localhost:8000/ai/pause \
  -H "Content-Type: application/json" \
  -d '{"reason": "Emergency stop"}'
```

### Resume Trading
```bash
curl -X POST http://localhost:8000/ai/reset-circuit-breaker
```

---

## 🐛 Troubleshooting

### Issue: Module not found errors
**Solution:**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Database locked errors
**Solution:**
```bash
# Remove lock files
rm data/vmassit.db-shm data/vmassit.db-wal

# Restart server
```

### Issue: API key errors
**Solution:**
```bash
# Verify keys are loaded
python -c "from app.config import settings; print(settings.BINANCE_API_KEY)"

# Check .env file format (no quotes around values)
cat .env | grep BINANCE
```

### Issue: Port already in use
**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill <PID>

# Or use different port
uvicorn app.main:app --reload --port 8001
```

### Issue: Telegram notifications not working
**Solution:**
```bash
# Verify bot token and chat ID
python -c "from app.config import settings; print(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)"

# Test manually
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>&text=Test"
```

---

## 📚 Next Steps

After completing this quick start:

1. **Read Documentation:**
   - [EXECUTION_MODES_GUIDE.md](EXECUTION_MODES_GUIDE.md) - Understand trading modes
   - [VALIDATION_REPORT.md](VALIDATION_REPORT.md) - See test results
   - [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Full system overview

2. **Run More Tests:**
   ```bash
   # Complete validation
   python scripts/validate_complete_system.py
   
   # Paper trading specific
   python scripts/validate_paper_trading.py
   ```

3. **Customize Settings:**
   - Adjust risk parameters in orchestrator
   - Configure trading strategies
   - Set up custom indicators

4. **Monitor Performance:**
   - Track P&L daily
   - Review trade decisions
   - Adjust parameters weekly

5. **Scale Up Gradually:**
   - Week 1-2: Paper trading only
   - Week 3-4: Semi-auto on testnet
   - Month 2+: Consider mainnet (if profitable)

---

## ✅ Success Criteria

You've successfully set up the system when:

- [x] Server runs without errors
- [x] API docs accessible at `http://localhost:8000/docs`
- [x] Can generate trade proposals
- [x] Database records created
- [x] Telegram notifications received (if configured)
- [x] Validation script passes all tests

---

## 🆘 Getting Help

If you encounter issues:

1. **Check Logs:**
   ```bash
   # Server logs show detailed errors
   # Look for ERROR or WARNING messages
   ```

2. **Review Documentation:**
   - All common issues documented in guides
   - Search for error message in docs

3. **Validate Configuration:**
   ```bash
   python scripts/validate_complete_system.py
   ```

4. **Reset to Defaults:**
   ```bash
   cp .env.example .env
   # Edit with minimal config
   ```

---

## 🎉 You're Ready!

Congratulations! Your Auto Trade System is now operational.

**Remember:**
- Start conservative (testnet + proposal mode)
- Monitor closely (check Telegram daily)
- Document everything (keep trading journal)
- Scale gradually (increase automation over time)

**Happy Trading! 🚀📈**

---

*Quick Start Guide v1.0 - Last updated: May 10, 2026*
