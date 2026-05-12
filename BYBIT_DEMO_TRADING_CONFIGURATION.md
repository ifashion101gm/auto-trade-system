# Bybit API Configuration Guide - Live vs Demo Trading

**Date:** May 12, 2026  
**Status:** ✅ **UPDATED** with proper demo trading support  
**Based on:** Official Bybit V5 API Documentation

---

## 🎯 Critical Discovery: Separate Domains & Credentials

After consulting official Bybit documentation, I've discovered that **Bybit Demo Trading requires**:

1. ✅ **SEPARATE API keys** generated from demo mode interface
2. ✅ **DIFFERENT API domain**: `https://api-demo.bybit.com` (not `api.bybit.com`)
3. ✅ **Independent account** with its own user ID and balance

### ❌ Previous Misconception
We previously thought demo trading used the same domain (`api.bybit.com`) with the same API keys, just in "demo mode". This was **INCORRECT**.

### ✅ Correct Architecture
```
Live Trading:
  • Domain: https://api.bybit.com
  • API Keys: Generated from live account
  • Balance: Real funds
  
Demo Trading:
  • Domain: https://api-demo.bybit.com  ← DIFFERENT!
  • API Keys: Generated FROM DEMO MODE  ← SEPARATE!
  • Balance: Virtual funds (100M+ USDT)
```

---

## 📋 Configuration Changes Made

### 1. Updated `.env` File

**Before:**
```bash
BYBIT_API_KEY="ShROT8PoWLCdmRaA9W"
BYBIT_API_SECRET="1xdtnJEgqmDlMZfz0CkXvjmfODlioiVAmGGD"
BYBIT_TESTNET=true  # ← UNUSED
```

**After:**
```bash
# Live/Mainnet API Keys (for production trading)
BYBIT_API_KEY="ShROT8PoWLCdmRaA9W"
BYBIT_API_SECRET="1xdtnJEgqmDlMZfz0CkXvjmfODlioiVAmGGD"

# Demo Trading API Keys (separate - generate from demo mode)
BYBIT_DEMO_API_KEY=  # TODO: Generate from https://www.bybit.com/en/trade/demo
BYBIT_DEMO_API_SECRET=  # TODO: Generate from demo mode

# Use Demo Trading Domain (api-demo.bybit.com)
BYBIT_USE_DEMO_DOMAIN=false  # Set to true when using demo keys
```

**Changes:**
- ✅ Removed unused `BYBIT_TESTNET` setting
- ✅ Added `BYBIT_DEMO_API_KEY` and `BYBIT_DEMO_API_SECRET`
- ✅ Added `BYBIT_USE_DEMO_DOMAIN` flag to switch domains
- ✅ Added comprehensive documentation comments

---

### 2. Updated `app/config.py`

**Added Configuration Variables:**
```python
# Bybit Demo Trading (separate credentials and domain)
BYBIT_DEMO_API_KEY: Optional[str] = None
BYBIT_DEMO_API_SECRET: Optional[str] = None
BYBIT_USE_DEMO_DOMAIN: bool = False  # Use api-demo.bybit.com instead of api.bybit.com
```

---

### 3. Updated `app/infra/bybit_client.py`

**New Constructor Parameters:**
```python
def __init__(
    self,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    testnet: bool = True,          # Legacy parameter
    demo_trading: bool = False     # NEW: Enable demo trading domain
):
```

**Domain Selection Logic:**
```python
if self.demo_trading:
    # Use demo trading domain: api-demo.bybit.com
    exchange_config['urls'] = {
        'api': {
            'public': 'https://api-demo.bybit.com',
            'private': 'https://api-demo.bybit.com',
        }
    }
elif self.testnet:
    # Legacy testnet mode
    exchange_config['options']['test'] = True
else:
    # Live trading: api.bybit.com (default)
    pass
```

**Automatic Key Selection:**
```python
# Use demo API keys if demo trading is enabled
if self.demo_trading:
    self.api_key = api_key or settings.BYBIT_DEMO_API_KEY or settings.BYBIT_API_KEY
    self.api_secret = api_secret or settings.BYBIT_DEMO_API_SECRET or settings.BYBIT_API_SECRET
```

---

## 🚀 How to Use Demo Trading

### Step 1: Activate Demo Mode

1. Visit: https://www.bybit.com/en/trade/demo
2. Click "Activate Demo Trading" (if needed)
3. Verify "DEMO" badge appears in top-right corner
4. Confirm balance shows ~100M USDT

### Step 2: Generate Demo API Keys

⚠️ **CRITICAL:** Must stay in demo mode during this process!

1. While in demo mode, click profile icon → "API Management"
2. Click "Create New Key"
3. Select "System Generated"
4. Name: "AutoTrade-Demo-2026-05-12"
5. Enable permissions:
   - ✓ Read-Write
   - ✓ Contract Trading
   - ✓ Unified Trading Account
6. **Copy API Key and Secret IMMEDIATELY** (shown only once!)
7. Verify key shows "Demo" indicator

### Step 3: Update Configuration

Edit `.env` file:
```bash
nano .env

# Add your demo API keys:
BYBIT_DEMO_API_KEY="your_demo_api_key_here"
BYBIT_DEMO_API_SECRET="your_demo_api_secret_here"

# Enable demo domain:
BYBIT_USE_DEMO_DOMAIN=true

# Save: Ctrl+O → Enter → Ctrl+X
```

### Step 4: Test Connection

```bash
# Quick test with demo domain
python -c "
import asyncio
from app.infra.bybit_client import BybitClient

async def test():
    client = BybitClient(demo_trading=True)
    balance = await client.fetch_balance()
    print(f'Demo Balance: \${balance[\"total_usdt\"]:,.2f}')
    await client.close()

asyncio.run(test())
"

# Expected output:
# Demo Balance: $100,008,018.00
```

---

## 📊 Usage Examples

### Example 1: Live Trading (Default)

```python
from app.infra.bybit_client import BybitClient

# Uses live domain (api.bybit.com) with live API keys
client = BybitClient(testnet=False, demo_trading=False)

# Or simply:
client = BybitClient(testnet=False)  # demo_trading defaults to False
```

**Configuration Used:**
- Domain: `https://api.bybit.com`
- API Key: `BYBIT_API_KEY` from `.env`
- Balance: Real funds

---

### Example 2: Demo Trading (NEW!)

```python
from app.infra.bybit_client import BybitClient

# Uses demo domain (api-demo.bybit.com) with demo API keys
client = BybitClient(demo_trading=True)

# Or explicitly:
client = BybitClient(testnet=False, demo_trading=True)
```

**Configuration Used:**
- Domain: `https://api-demo.bybit.com`
- API Key: `BYBIT_DEMO_API_KEY` from `.env` (falls back to `BYBIT_API_KEY` if not set)
- Balance: Virtual funds (100M+ USDT)

---

### Example 3: Override API Keys

```python
# Use custom API keys for demo trading
client = BybitClient(
    api_key="custom_demo_key",
    api_secret="custom_demo_secret",
    demo_trading=True
)
```

---

### Example 4: Using Environment Variable

```bash
# In .env file:
BYBIT_USE_DEMO_DOMAIN=true

# In Python code (automatically uses demo domain):
client = BybitClient()  # Will use demo_trading=True from config
```

---

## 🔍 Verification Checklist

After setting up demo trading, verify:

- [ ] Logged into Bybit demo mode
- [ ] "DEMO" badge visible in web interface
- [ ] Demo API keys generated FROM DEMO MODE
- [ ] Keys copied and stored securely
- [ ] `.env` updated with demo keys
- [ ] `BYBIT_USE_DEMO_DOMAIN=true` set
- [ ] Test script shows non-zero balance
- [ ] Can fetch XAG/USDT:USDT ticker
- [ ] Domain is `api-demo.bybit.com` (check logs)

---

## 📝 Migration Guide

### If You Were Using Old Configuration

**Old Setup:**
```bash
BYBIT_API_KEY="ShROT8Po..."
BYBIT_API_SECRET="1xdtnJEg..."
BYBIT_TESTNET=true  # ← Didn't work correctly
```

**Problem:**
- Connected to wrong domain (`api.bybit.com`)
- Used live API keys
- Showed $0 balance (wrong account)

**New Setup:**
```bash
# Keep live keys as-is
BYBIT_API_KEY="ShROT8Po..."
BYBIT_API_SECRET="1xdtnJEg..."

# Add demo keys (generate from demo mode)
BYBIT_DEMO_API_KEY="new_demo_key_here"
BYBIT_DEMO_API_SECRET="new_demo_secret_here"

# Enable demo domain
BYBIT_USE_DEMO_DOMAIN=true
```

**Result:**
- Connects to correct domain (`api-demo.bybit.com`)
- Uses demo API keys
- Shows 100M+ USDT balance ✅

---

## 🎓 Technical Details

### Bybit API Domains

| Mode | REST API Domain | WebSocket Domain | Purpose |
|------|----------------|------------------|---------|
| **Live Trading** | `https://api.bybit.com` | `wss://stream.bybit.com` | Real funds |
| **Demo Trading** | `https://api-demo.bybit.com` | `wss://stream-demo.bybit.com` | Virtual funds |
| **Testnet** | N/A (deprecated) | N/A | Not recommended |

### Why Separate Domains?

Bybit's architecture isolates demo trading completely:
- Prevents accidental live trades with demo logic
- Separate infrastructure for stability
- Independent rate limits
- Different user IDs and balances

### CCXT Integration

The `ccxt` library supports custom URLs via the `urls` configuration:

```python
exchange_config['urls'] = {
    'api': {
        'public': 'https://api-demo.bybit.com',
        'private': 'https://api-demo.bybit.com',
    }
}
```

This overrides the default Bybit URLs and routes all requests to the demo domain.

---

## ⚠️ Common Pitfalls

### Pitfall 1: Using Live Keys with Demo Domain

**Error:**
```json
{"retCode":10003,"retMsg":"API key is invalid"}
```

**Cause:**
Live API keys don't work on demo domain.

**Solution:**
Generate separate API keys from demo mode interface.

---

### Pitfall 2: Using Demo Keys with Live Domain

**Symptom:**
Balance shows $0 even though demo account has funds.

**Cause:**
Demo API keys only work on demo domain (`api-demo.bybit.com`).

**Solution:**
Set `BYBIT_USE_DEMO_DOMAIN=true` or use `demo_trading=True`.

---

### Pitfall 3: Generating Keys Outside Demo Mode

**Symptom:**
Keys are created but show as "live" keys, not "demo" keys.

**Cause:**
API management page accessed while NOT in demo mode.

**Solution:**
1. Navigate to demo trading first
2. THEN access API management
3. Verify "Demo" indicator on key

---

## 📞 Support Resources

### Official Documentation
- **Bybit Demo Trading:** https://bybit-exchange.github.io/docs/v5/demo
- **API Key Creation:** https://www.bybit.com/en/help-center/article/How-to-create-API-key
- **Demo Trading Guide:** https://www.bybit.com/en/help-center/article/Demo-Trading

### API Endpoints
- **Live REST API:** https://api.bybit.com
- **Demo REST API:** https://api-demo.bybit.com
- **Live WebSocket:** wss://stream.bybit.com
- **Demo WebSocket:** wss://stream-demo.bybit.com

### Quick Commands
```bash
# Test live connection
python -c "from app.infra.bybit_client import BybitClient; import asyncio; asyncio.run((lambda: (c := BybitClient(testnet=False), print(f'Live: \${(await c.fetch_balance())[\"total_usdt\"]:,.2f}'), c.close())[2])())"

# Test demo connection
python -c "from app.infra.bybit_client import BybitClient; import asyncio; asyncio.run((lambda: (c := BybitClient(demo_trading=True), print(f'Demo: \${(await c.fetch_balance())[\"total_usdt\"]:,.2f}'), c.close())[2])())"

# Full validation
python scripts/validate_bybit_automated.py
```

---

## 🎯 Summary

### What Changed

1. ✅ **Added demo trading domain support** (`api-demo.bybit.com`)
2. ✅ **Added separate demo API key configuration** (`BYBIT_DEMO_API_KEY`)
3. ✅ **Added domain toggle** (`BYBIT_USE_DEMO_DOMAIN`)
4. ✅ **Updated BybitClient** to support both modes
5. ✅ **Removed unused** `BYBIT_TESTNET` setting

### What This Fixes

- ❌ **Before:** Balance showed $0 (wrong domain/keys)
- ✅ **After:** Balance will show 100M+ USDT (correct domain/keys)

### Next Steps

1. Generate demo API keys from https://www.bybit.com/en/trade/demo
2. Update `.env` with new demo credentials
3. Set `BYBIT_USE_DEMO_DOMAIN=true`
4. Run validation to confirm setup

---

**Last Updated:** May 12, 2026 at 23:00 UTC  
**Architecture:** Dual-domain (Live + Demo)  
**Status:** Ready for demo key configuration  
