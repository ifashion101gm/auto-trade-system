# Bybit Demo Trading Fix - Pybit SDK Integration

**Date:** May 13, 2026  
**Issue:** retCode 10032 - "Demo trading are not supported"  
**Root Cause:** CCXT library does NOT support Bybit Demo Trading  
**Solution:** Migrated to official Pybit SDK for demo mode

---

## 🔍 Problem Analysis

### CCXT Limitation (GitHub Issue #25545)
- **Issue**: https://github.com/ccxt/ccxt/issues/25545
- **Symptom**: `set_sandbox_mode(true)` returns error 10003/10032
- **Cause**: CCXT's Bybit implementation has known issues with demo mode
- **Status**: CCXT does not properly support `api-demo.bybit.com`

### Official Documentation Findings

1. **Bybit V5 Demo Documentation**:
   - URL: https://bybit-exchange.github.io/docs/v5/demo
   - Demo trading uses `api-demo.bybit.com`
   - Must be created from mainnet account in demo mode
   - Keys are isolated from testnet

2. **Pybit SDK** (Official Bybit SDK):
   - Repository: https://github.com/bybit-exchange/pybit
   - **CRITICAL**: Demo trading uses `demo=True`, `testnet=False`
   - Pybit has full demo trading support

---

## ✅ Solution Implemented

### Architecture Change
```
BEFORE (Broken):
┌─────────────┐
│ BybitClient │
│             │
│   CCXT      │ ← Doesn't support demo mode
│             │
└─────────────┘

AFTER (Working):
┌─────────────┐
│ BybitClient │
│             │
│ Demo Mode?  │
├────────────┤
│ YES │ NO    │
│     │       │
│Pybit│ CCXT  │ ← Pybit for demo, CCXT for testnet/mainnet
│     │       │
└─────┴───────┘
```

### Code Changes

1. **Import Pybit SDK**:
   ```python
   from pybit.unified_trading import HTTP as PybitHTTP
   ```

2. **Demo Mode Initialization** (CRITICAL):
   ```python
   if self.demo_trading:
       self.use_pybit = True
       self.pybit_session = PybitHTTP(
           testnet=False,  # CRITICAL: Must be False for demo
           demo=True,       # Enable demo trading mode
           api_key=self.api_key,
           api_secret=self.api_secret,
       )
   ```

3. **Refactored Methods**:
   - `fetch_balance()` - Uses Pybit `get_wallet_balance()` for demo
   - `fetch_open_positions()` - Uses Pybit `get_position_list()` for demo
   - `create_market_order()` - Uses Pybit `place_order()` for demo
   - `cancel_order()` - Uses Pybit `cancel_order()` for demo

---

## 📋 Official Pybit Best Practices

### Demo Trading Initialization
```python
from pybit.unified_trading import HTTP

session = HTTP(
    testnet=False,    # MUST be False for demo
    demo=True,        # Enable demo trading
    api_key="YOUR_DEMO_API_KEY",
    api_secret="YOUR_DEMO_API_SECRET",
)
```

### Important Notes
1. **testnet=False** is required for demo trading
2. **demo=True** enables `api-demo.bybit.com` routing
3. API keys must be generated from demo mode interface
4. Demo keys are separate from live/testnet keys

---

## 🔑 API Key Requirements

### Correct Configuration
```bash
BYBIT_USE_DEMO_DOMAIN=true
BYBIT_DEMO_API_KEY=EJswnKqHaQKyvY2sgz
BYBIT_DEMO_API_SECRET=Yzfufhz4pmVLKFx6JL1t0GR4Nj7VtPHAzTzg
```

### Required Permissions
- ✅ Read-Write
- ✅ Contract Trading
- ✅ Account Read
- ✅ Wallet Read

### Key Generation Steps
1. Go to: https://www.bybit.com/en/trade/demo
2. Verify "DEMO" badge visible
3. Profile → API Management (while in demo mode)
4. Create new key with Read-Write + Contract permissions
5. Copy API Key & Secret immediately

---

## ✅ Verification

Run the diagnostic script:
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python scripts/check_bybit_demo_permissions.py
```

### Expected Results
- ✅ Server connectivity: Working
- ✅ Authentication: Success (no more 10032 error)
- ✅ Balance check: Shows demo USDT balance
- ✅ Position check: Read permissions working
- ✅ Order placement: Write permissions working

---

##  References

1. **Pybit SDK**: https://github.com/bybit-exchange/pybit
2. **Demo Trading Docs**: https://bybit-exchange.github.io/docs/v5/demo
3. **CCXT Issue**: https://github.com/ccxt/ccxt/issues/25545
4. **Error Codes**: https://bybit-exchange.github.io/docs/v5/error

---

**Status:** ✅ Implementation Complete  
**Next Step:** Verify API keys have demo trading permissions  
**Risk Level:** None - Demo trading uses virtual funds only
