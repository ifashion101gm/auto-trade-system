# Gold Futures Hybrid Trading - Quick Start Guide

## 🚀 Quick Start (3 Steps)

### Step 1: Verify MEXC Gold Symbol
The current configuration uses `XAUT/USDT` for MEXC, but this symbol may not be available. Check available symbols:

```bash
# Option A: Check MEXC website
# Visit: https://www.mexc.com/futures

# Option B: Use Python to list available futures
python -c "
import ccxt.async_support as ccxt
import asyncio

async def check():
    mexc = ccxt.mexc({'options': {'defaultType': 'future'}})
    markets = await mexc.load_markets()
    gold_symbols = [s for s in markets.keys() if 'GOLD' in s or 'XAU' in s or 'XAUT' in s]
    print('Available Gold symbols:', gold_symbols)
    await mexc.close()

asyncio.run(check())
"
```

Update `.env` with the correct symbol if needed:
```bash
GOLD_SYMBOL_MEXC=<correct_symbol>  # e.g., XAU/USDT
```

### Step 2: Start the Server
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Execute Dual Trade
```bash
curl -X POST http://localhost:8000/gold-futures/dual-execute \
  -H "Authorization: Bearer change_this_to_a_secure_random_string_12345" \
  -H "Content-Type: application/json"
```

---

## 📊 Expected Response

```json
{
  "status": "success",
  "message": "Gold dual trade executed successfully",
  "binance_paper": {
    "exchange": "Binance Testnet",
    "symbol": "PAXG/USDT",
    "result": { ... },
    "trade_id": 123
  },
  "mexc_live": {
    "exchange": "MEXC Live",
    "symbol": "XAUT/USDT",
    "result": { ... },
    "trade_id": 124
  },
  "comparison": {
    "position_value_usd": 100.0,
    "binance_price": 4699.58,
    "mexc_price": 4700.12,
    "price_difference": 0.54,
    "strategy": "mean_reversion",
    "regime": "Low-vol",
    "confidence": 0.85
  }
}
```

---

## 🔍 Monitoring

### Check Database
```sql
-- View recent Gold trades
SELECT 
    id,
    exchange,
    symbol,
    side,
    entry_price,
    status,
    execution_mode,
    ts_open
FROM paper_trades
WHERE symbol IN ('PAXG/USDT', 'XAUT/USDT')
ORDER BY ts_open DESC
LIMIT 10;

-- Compare paper vs live performance
SELECT 
    exchange,
    COUNT(*) as trade_count,
    AVG(profit) as avg_profit,
    SUM(profit) as total_profit
FROM paper_trades
WHERE symbol IN ('PAXG/USDT', 'XAUT/USDT')
AND status = 'closed'
GROUP BY exchange;
```

### Telegram Notifications
You'll receive alerts like:
```
🥇 GOLD DUAL TRADE EXECUTED

Strategy: mean_reversion
Regime: Low-vol
Confidence: 85.0%

Binance Testnet (Paper): ✅ SUCCESS
• Symbol: PAXG/USDT
• Price: $4,699.58

MEXC Live (Real): ✅ SUCCESS
• Symbol: XAUT/USDT
• Price: $4,700.12

Comparison:
• Position Value: $100.00
• Price Difference: $0.54

Paper vs Live execution comparison for Gold futures
```

---

## ⚙️ Configuration Tuning

### Adjust Risk Parameters
Edit `.env`:
```bash
# More conservative
GOLD_MAX_LEVERAGE=3
GOLD_RISK_PER_TRADE=0.005      # 0.5% risk
GOLD_MIN_CONFIDENCE=0.75       # 75% confidence

# More aggressive
GOLD_MAX_LEVERAGE=10
GOLD_RISK_PER_TRADE=0.02       # 2% risk
GOLD_MIN_CONFIDENCE=0.60       # 60% confidence
```

Restart server after changes.

### Change Execution Mode
```bash
# Proposal only (no execution)
EXECUTION_MODE=proposal

# Semi-auto with threshold
EXECUTION_MODE=semi-auto
AUTO_EXECUTE_THRESHOLD_USD=100.0

# Fully automatic
EXECUTION_MODE=fully-auto
```

---

## 🧪 Testing Commands

### Run Full Validation
```bash
PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system \
python scripts/validate_gold_hybrid.py
```

### Test Individual Components
```bash
# Test connectivity only
python -c "
import asyncio
from app.infra.hybrid_exchange_manager import HybridExchangeManager

async def test():
    mgr = HybridExchangeManager()
    info = mgr.info
    print('Binance:', info['binance_available'])
    print('MEXC:', info['mexc_available'])
    await mgr.close()

asyncio.run(test())
"

# Test market data
python -c "
import asyncio
from app.config import settings
from app.infra.binance_client import BinanceClient

async def test():
    client = BinanceClient(
        api_key=settings.BINANCE_PAPER_API_KEY,
        api_secret=settings.BINANCE_PAPER_API_SECRET,
        testnet=True,
        demo_mode='futures_demo'
    )
    ticker = await client.fetch_ticker(settings.GOLD_SYMBOL_BINANCE)
    print(f'Price: \${ticker[\"last_price\"]:,.2f}')
    await client.close()

asyncio.run(test())
"
```

---

## 🐛 Troubleshooting

### Issue: MEXC Symbol Not Found
**Error**: `mexc does not have market symbol XAUT/USDT`

**Solution**:
1. Check available symbols (see Step 1 above)
2. Update `GOLD_SYMBOL_MEXC` in `.env`
3. Restart server

### Issue: Binance Balance Fetch Failed
**Error**: `binance does not have a testnet/sandbox URL for sapi endpoints`

**Impact**: Minor - trading still works
**Note**: This is a known ccxt limitation with demo endpoints

### Issue: No Trade Proposal Generated
**Cause**: Confidence below minimum threshold

**Solution**:
- Lower `GOLD_MIN_CONFIDENCE` in `.env` (e.g., 0.60)
- Or wait for better market conditions

### Issue: Order Execution Failed
**Check**:
1. API key permissions (enable futures trading)
2. Sufficient balance
3. Symbol availability
4. Network connectivity

---

## 📈 Performance Analysis

### Key Metrics to Track

1. **Execution Quality**
   - Slippage: Difference between expected and filled price
   - Fill rate: Percentage of orders successfully executed

2. **Paper vs Live Comparison**
   - Price differences between exchanges
   - Strategy performance in paper vs live
   - Win rate comparison

3. **Risk Management**
   - Maximum drawdown
   - Average position size
   - Leverage utilization

### Query Examples
```sql
-- Average slippage by exchange
SELECT 
    exchange,
    AVG(ABS(entry_price - (SELECT last_price FROM market_data LIMIT 1))) as avg_slippage
FROM paper_trades
WHERE symbol IN ('PAXG/USDT', 'XAUT/USDT')
GROUP BY exchange;

-- Win rate by strategy
SELECT 
    json_extract(notes, '$.strategy') as strategy,
    COUNT(*) as total_trades,
    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as winning_trades,
    ROUND(100.0 * SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate
FROM paper_trades
WHERE status = 'closed'
AND symbol IN ('PAXG/USDT', 'XAUT/USDT')
GROUP BY strategy;
```

---

## 🔐 Security Checklist

- [ ] API keys stored in `.env` (not committed to git)
- [ ] MEXC API key has trading permissions only (NO withdrawals)
- [ ] `TRADING_API_SECRET` is strong and unique
- [ ] Server not exposed to public internet without authentication
- [ ] Regular backup of database (`data/vmassit.db`)
- [ ] Monitor Telegram for unexpected trades

---

## 📞 Support & Resources

### Documentation
- Full implementation: `GOLD_HYBRID_IMPLEMENTATION_SUMMARY.md`
- Plan details: `.lingma/plans/Gold_Futures_Hybrid_Trading_Setup_*.md`

### Key Files
- Hybrid Manager: `app/infra/hybrid_exchange_manager.py`
- Trading Service: `app/services/live_trading_service.py`
- API Endpoint: `app/api/trading.py`
- Validation: `scripts/validate_gold_hybrid.py`

### External Resources
- Binance Testnet: https://testnet.binance.vision/
- MEXC API Docs: https://mxcdevelop.github.io/apidocs/
- PAXG Info: https://www.paxos.com/paxgold/
- XAUT Info: https://tether.to/xaut/

---

## ✅ Pre-Flight Checklist

Before going live with real money:

- [ ] Validated MEXC Gold symbol is correct
- [ ] Tested Binance paper trading successfully
- [ ] Confirmed API key permissions are correct
- [ ] Set conservative risk parameters initially
- [ ] Enabled Telegram notifications
- [ ] Backed up database
- [ ] Reviewed all safety warnings
- [ ] Started with minimum position sizes
- [ ] Monitored first 10+ trades carefully
- [ ] Verified stop-loss and take-profit working

---

**Ready to trade? Start with Step 1 above!** 🚀
