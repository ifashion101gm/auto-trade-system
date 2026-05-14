# XAUUSDT-Only Trading - Quick Reference Card

## ✅ Configuration Complete

Your trading system is now **EXCLUSIVELY configured for XAUUSDT (Gold) day trading**.

---

## Key Settings

```python
# app/config.py
PRIMARY_TRADING_SYMBOL = "XAUUSDT"
ENABLED_TRADING_SYMBOLS = ["XAUUSDT"]
```

**All other symbols are REJECTED.**

---

## Validation Layers

### Layer 1: API (ExecutionService)
```python
# Rejects invalid symbols at entry point
if symbol not in ["XAUUSDT"]:
    return ExecutionResult(
        success=False,
        error="Symbol NOT ALLOWED. Trading is EXCLUSIVELY restricted to XAUUSDT"
    )
```

### Layer 2: Risk (RiskManager)
```python
# Check 0: Symbol Validation
symbol_check = self._check_symbol_allowed(symbol)
if not symbol_check['passed']:
    return RiskValidationResult(passed=False, violations=[...])
```

### Layer 3: Execution (TradingService)
```python
# Defaults to XAUUSDT if None provided
if symbol is None:
    symbol = settings.PRIMARY_TRADING_SYMBOL  # XAUUSDT

# Validates before any market data fetch
if not self._validate_symbol_allowed(symbol):
    return {'status': 'symbol_rejected', 'error': ...}
```

---

## Symbol Normalization

All formats accepted for XAUUSDT:
- ✅ `XAUUSDT`
- ✅ `XAU/USDT`
- ✅ `XAU:USDT`
- ✅ `xauusdt`

Rejected symbols:
- ❌ `BTC/USDT`
- ❌ `ETHUSDT`
- ❌ Any non-XAU symbol

---

## Testing

### Test Valid Symbol
```bash
python -c "
import asyncio
from app.execution.trading_service import TradingService

async def test():
    service = TradingService()
    result = await service.execute_trading_cycle(symbol='XAUUSDT')
    print(f'Status: {result[\"status\"]}')
    print(f'Symbol: {result.get(\"symbol\", \"N/A\")}')

asyncio.run(test())
"
```

### Test Invalid Symbol
```bash
python -c "
import asyncio
from app.execution.trading_service import TradingService

async def test():
    service = TradingService()
    result = await service.execute_trading_cycle(symbol='BTC/USDT')
    print(f'Status: {result[\"status\"]}')
    print(f'Error: {result.get(\"error\", \"N/A\")}')

asyncio.run(test())
"
# Expected: status='symbol_rejected', error mentions XAUUSDT
```

---

## Monitoring

### Log Messages

**Success:**
```
🎯 Using default symbol: XAUUSDT (Gold)
✅ Symbol validated: XAUUSDT (XAUUSDT Gold)
```

**Rejection:**
```
❌ Symbol 'BTC/USDT' REJECTED. Trading is EXCLUSIVELY restricted to XAUUSDT
```

### Watch For
```bash
# Monitor symbol rejections
tail -f logs/all_*.log | grep -i "symbol.*rejected"

# Monitor successful validations
tail -f logs/all_*.log | grep -i "symbol validated"
```

---

## Troubleshooting

### Issue: "Symbol rejected" error
**Cause:** Attempting to trade non-XAUUSDT symbol  
**Solution:** Only use XAUUSDT (or variants: XAU/USDT, XAU:USDT)

### Issue: "No symbol provided" warning
**Cause:** Symbol parameter is None  
**Solution:** System will default to XAUUSDT automatically

### Issue: Symbol validation fails unexpectedly
**Cause:** Symbol format issue  
**Solution:** Use one of the accepted formats listed above

---

## Files Modified

| File | Changes |
|------|---------|
| `app/config.py` | Added PRIMARY_TRADING_SYMBOL, ENABLED_TRADING_SYMBOLS |
| `app/risk/risk_manager.py` | Added Check 0: Symbol Validation |
| `app/execution/trading_service.py` | Updated execute_trading_cycle with symbol enforcement |
| `app/execution/execution_service.py` | Added symbol validation in _validate_request |

---

## Quick Commands

### Start Trading (Defaults to XAUUSDT)
```bash
python -m app.main
```

### Run Specific Symbol
```bash
python scripts/execute_gold_trade.py --symbol XAUUSDT
```

### Check Configuration
```bash
python -c "
from app.config import settings
print(f'Primary Symbol: {settings.PRIMARY_TRADING_SYMBOL}')
print(f'Enabled Symbols: {settings.ENABLED_TRADING_SYMBOLS}')
"
```

---

## Support

For issues or questions:
1. Check logs: `logs/all_*.log`
2. Review configuration: `app/config.py`
3. See full documentation: `XAUUSDT_ONLY_CONFIGURATION.md`

---

**System Status:** ✅ Ready for XAUUSDT-only Gold day trading
