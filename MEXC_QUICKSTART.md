# MEXC Demo Futures - Quick Start Guide

## 🚀 Quick Start

### 1. Verify Configuration
```bash
# Check current settings
python -c "from app.config import settings; print(f'Active Exchange: {settings.ACTIVE_EXCHANGE}'); print(f'Gold Symbol: {settings.GOLD_SYMBOL_MEXC}')"
```

**Expected Output:**
```
Active Exchange: mexc
Gold Symbol: XAUT/USDT
```

### 2. Run Validation
```bash
python scripts/validate_mexc_demo_futures.py
```

This will test:
- ✅ MEXC API connectivity
- ✅ Market data fetching (XAUT/USDT)
- ✅ AI strategy selection
- ✅ Order execution (demo)
- ✅ Position tracking

### 3. Execute First Trade
```python
from app.services.live_trading_service import LiveTradingService
import asyncio

async def trade():
    service = LiveTradingService(exchange_name='mexc')
    result = await service.execute_trading_cycle(
        symbol='XAUT/USDT',
        user_id='test_user'
    )
    print(result)
    await service.close()

asyncio.run(trade())
```

---

## 📊 Key Changes Summary

| Component | Before | After |
|-----------|--------|-------|
| **Primary Exchange** | Binance Testnet | MEXC Demo Futures |
| **Gold Symbol** | PAXG/USDT | XAUT/USDT |
| **Execution Mode** | Paper Trading | Demo Futures |
| **API Keys** | BINANCE_PAPER_* | MEXC_API_* |
| **Database Label** | `execution_type: 'paper'` | `execution_type: 'demo_futures'` |

---

## 🔧 Configuration Checklist

### Environment Variables (.env)
```bash
# MEXC Credentials (Required)
MEXC_API_KEY=your_mexc_api_key_here
MEXC_API_SECRET=your_mexc_api_secret_here
MEXC_DEFAULT_MARKET_TYPE=futures

# Active Exchange
ACTIVE_EXCHANGE=mexc

# Gold Trading Parameters
GOLD_SYMBOL_MEXC=XAUT/USDT
GOLD_MAX_LEVERAGE=5
GOLD_RISK_PER_TRADE=0.01
GOLD_MIN_CONFIDENCE=0.65

# Binance (Optional - for comparison)
BINANCE_PAPER_API_KEY=your_binance_paper_key
BINANCE_PAPER_API_SECRET=your_binance_paper_secret
BINANCE_TESTNET=true
BINANCE_DEMO_MODE=futures_demo
```

### Verify .env Setup
```bash
# Test configuration loading
python test_config.py
```

---

## 🎯 Common Operations

### Check MEXC Balance
```python
from app.infra.mexc_client import MEXCClient
import asyncio

async def check_balance():
    mexc = MEXCClient(market_type='futures')
    balance = await mexc.fetch_balance()
    print(f"Total USDT: ${balance['total_usdt']:,.2f}")
    print(f"Available: ${balance['free_usdt']:,.2f}")
    await mexc.close()

asyncio.run(check_balance())
```

### Fetch XAUT/USDT Price
```python
from app.infra.mexc_client import MEXCClient
import asyncio

async def get_price():
    mexc = MEXCClient(market_type='futures')
    ticker = await mexc.fetch_ticker('XAUT/USDT')
    print(f"XAUT/USDT: ${ticker['last_price']:,.2f}")
    await mexc.close()

asyncio.run(get_price())
```

### Execute Dual Trade (MEXC + Binance)
```python
from app.services.live_trading_service import LiveTradingService
import asyncio

async def dual_trade():
    service = LiveTradingService(exchange_name='mexc')
    
    # This will execute on BOTH exchanges
    result = await service.execute_dual_gold_trade(
        proposal={
            'side': 'BUY',
            'entry_price': 4700.0,
            'quantity': 0.02,
            'leverage': 3,
            'confidence': 0.75,
            'strategy_name': 'momentum',
            'regime': 'Normal'
        },
        user_id='test_user'
    )
    
    print(f"MEXC Status: {result['mexc']['status']}")
    print(f"Binance Status: {result['binance']['status']}")
    await service.close()

asyncio.run(dual_trade())
```

---

## 🐛 Troubleshooting

### Issue: "MEXC API credentials not configured"
**Solution:** Ensure `MEXC_API_KEY` and `MEXC_API_SECRET` are set in `.env`

### Issue: "Insufficient balance"
**Solution:** MEXC demo accounts start with ~$100 USDT. Reduce position size or request demo top-up.

### Issue: "Symbol not found: XAUT/USDT"
**Solution:** Verify MEXC client is initialized with `market_type='futures'`

### Issue: Orders executing on Binance instead of MEXC
**Solution:** Check `ACTIVE_EXCHANGE` in `app/config.py` is set to `"mexc"`

### Issue: Database shows wrong execution_type
**Solution:** Ensure you're using the updated `live_trading_service.py` with `'demo_futures'` label

---

## 📈 Monitoring

### View Recent Trades
```sql
SELECT 
    id,
    exchange,
    symbol,
    side,
    entry_price,
    execution_mode,
    ts_open
FROM paper_trades
WHERE symbol LIKE '%XAUT%' OR symbol LIKE '%PAXG%'
ORDER BY ts_open DESC
LIMIT 10;
```

### Check Paired Trades
```sql
SELECT 
    mt.id as mexc_trade_id,
    bt.id as binance_trade_id,
    mt.entry_price as mexc_entry,
    bt.entry_price as binance_entry,
    mt.ts_open
FROM paper_trades mt
JOIN paper_trades bt ON mt.notes->>'paired_with' = bt.id::text
WHERE mt.exchange = 'mexc'
ORDER BY mt.ts_open DESC
LIMIT 5;
```

---

## 🔄 Switching Back to Binance (Rollback)

If needed, revert to Binance Testnet:

1. **Update Config**:
   ```python
   # app/config.py
   ACTIVE_EXCHANGE = "binance"
   ```

2. **Restart Service**:
   ```bash
   python app/main.py
   ```

3. **Validate**:
   ```bash
   python scripts/validate_complete_cycle.py
   ```

---

## 📚 Additional Resources

- **Full Refactoring Details**: See `MEXC_DEMO_FUTURES_REFACTORING.md`
- **Validation Script**: `scripts/validate_mexc_demo_futures.py`
- **Hybrid Manager Docs**: `app/infra/hybrid_exchange_manager.py`
- **MEXC Client**: `app/infra/mexc_client.py`

---

## ✅ Success Criteria

Your MEXC Demo Futures integration is successful when:

- [ ] Validation script passes all 5 tests
- [ ] First trade executes on MEXC with `execution_type: 'demo_futures'`
- [ ] Telegram notification shows "MEXC (Primary/Demo)" label
- [ ] Database contains paired trades (MEXC + Binance)
- [ ] Balance decreases after order execution
- [ ] Position appears in `fetch_open_positions()`

---

**Need Help?** Check the logs in `data/vmassit.db` or review the validation script output for detailed error messages.
