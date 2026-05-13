# Bybit Demo Trading - Quick Reference Guide

## Quick Start

### Verify Demo API Connection
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
PYTHONPATH=. python scripts/check_bybit_demo_permissions.py
```

### Expected Output
```
✅ Server Connectivity: Working
✅ Authentication: Working (Balance: $49,999.xx)
✅ Write Permissions: Working (can place orders)
```

---

## Configuration Checklist

### 1. Environment Variables (.env)
```bash
BYBIT_DEMO_API_KEY="your_demo_api_key"
BYBIT_DEMO_API_SECRET="your_demo_api_secret"
BYBIT_USE_DEMO_DOMAIN=true
```

### 2. API Key Requirements
- ✅ Generated from **Demo Trading** mode (not live/testnet)
- ✅ URL: https://www.bybit.com/en/trade/demo
- ✅ Permissions: "Contract Trading" enabled
- ✅ Not expired or revoked

### 3. Code Initialization
```python
from app.infra.bybit_client import BybitClient

# For demo trading
client = BybitClient(demo_trading=True)

# Client automatically uses Pybit SDK for demo mode
```

---

## Common Error Codes & Solutions

| Error Code | Meaning | Solution |
|------------|---------|----------|
| **10032** | Demo trading not supported | ✅ FIXED - Now using Pybit SDK |
| **10003** | Invalid API key | Regenerate keys from demo interface |
| **10004** | Permissions denied | Enable "Contract Trading" permission |
| **10001** | Parameter error | Check symbol format (XAUUSDT not XAU/USDT:USDT) |
| **110001** | Order not found | Order already filled/cancelled |

---

## Symbol Format Conversion

The system automatically converts between formats:

| CCXT Format | Pybit Format | Example |
|-------------|--------------|---------|
| `XAU/USDT:USDT` | `XAUUSDT` | Gold futures |
| `BTC/USDT:USDT` | `BTCUSDT` | Bitcoin futures |
| `ETH/USDT:USDT` | `ETHUSDT` | Ethereum futures |

**Conversion Logic:**
```python
bybit_symbol = symbol.replace('/', '').replace(':', '')
if bybit_symbol.endswith('USDTUSDT'):
    bybit_symbol = bybit_symbol[:-4]
```

---

## Architecture Overview

```
┌─────────────────────────────────────┐
│        BybitClient Class            │
├─────────────────────────────────────┤
│                                     │
│  if demo_trading=True:              │
│    → Uses Pybit SDK                 │
│    → api-demo.bybit.com             │
│    → Synchronous calls              │
│    → Full demo support ✅           │
│                                     │
│  if testnet/mainnet:                │
│    → Uses CCXT                      │
│    → api-testnet/api.bybit.com      │
│    → Async/await calls              │
│    → Unified interface              │
│                                     │
└─────────────────────────────────────┘
```

---

## Troubleshooting Flowchart

```
retCode 10032 Error?
    │
    ├─ Yes → Check BYBIT_USE_DEMO_DOMAIN in .env
    │         ├─ false → Set to true
    │         └─ true → Verify using Pybit SDK (not CCXT)
    │                    ├─ No → Update bybit_client.py
    │                    └─ Yes → Regenerate API keys from demo mode
    │
    └─ No → Check other error codes above
```

---

## API Key Generation Steps

1. **Access Demo Trading**
   ```
   Go to: https://www.bybit.com/en/trade/demo
   ```

2. **Navigate to API Management**
   ```
   Profile Icon → API Management (while in demo mode)
   ```

3. **Create New API Key**
   ```
   Click "Create New Key"
   Select: "Unified Trading Account"
   ```

4. **Set Permissions**
   ```
   ✅ Account Read
   ✅ Wallet Read  
   ✅ Order - Trade (Spot & Derivatives)
   ✅ Position - Read & Write
   ```

5. **Copy Credentials**
   ```
   Copy API Key and Secret immediately
   Update .env file:
     BYBIT_DEMO_API_KEY="..."
     BYBIT_DEMO_API_SECRET="..."
   ```

6. **Verify**
   ```bash
   python scripts/check_bybit_demo_permissions.py
   ```

---

## Testing Commands

### Test Balance Retrieval
```python
import asyncio
from app.infra.bybit_client import BybitClient

async def test():
    client = BybitClient(demo_trading=True)
    balance = await client.fetch_balance()
    print(f"Balance: ${balance['total_usdt']:,.2f}")
    await client.close()

asyncio.run(test())
```

### Test Market Order
```python
async def test_order():
    client = BybitClient(demo_trading=True)
    
    order = await client.create_market_order(
        symbol="XAU/USDT:USDT",
        side="buy",
        amount=0.01,
        leverage=1
    )
    print(f"Order ID: {order['order_id']}")
    print(f"Status: {order['status']}")
    
    await client.close()

asyncio.run(test_order())
```

### Test Position Query
```python
async def test_positions():
    client = BybitClient(demo_trading=True)
    positions = await client.fetch_open_positions()
    print(f"Open Positions: {len(positions)}")
    for pos in positions:
        print(f"  {pos['symbol']}: {pos['side']} {pos['size']}")
    await client.close()

asyncio.run(test_positions())
```

---

## Important Notes

### ⚠️ Critical Reminders

1. **Never use CCXT for demo trading** - It doesn't work (GitHub #25545)
2. **Always set `testnet=False`** when using Pybit for demo
3. **API keys are environment-specific**:
   - Demo keys ≠ Testnet keys ≠ Live keys
4. **Symbol format matters** - System handles conversion automatically

### 💡 Best Practices

1. **Rate Limiting**: 10 requests/sec (private), 50 requests/sec (public)
2. **Recv Window**: 5000ms default (prevents timestamp errors)
3. **Error Handling**: Always check retCode in responses
4. **Testing**: Use diagnostic script before production changes

---

## File Locations

| File | Purpose |
|------|---------|
| `app/infra/bybit_client.py` | Main client implementation |
| `.env` | API credentials & configuration |
| `scripts/check_bybit_demo_permissions.py` | Diagnostic tool |
| `BYBIT_DEMO_FIX_RESOLUTION.md` | Detailed fix documentation |

---

## Support Resources

- **Official Pybit Docs**: https://github.com/bybit-exchange/pybit
- **Bybit V5 API Docs**: https://bybit-exchange.github.io/docs/v5
- **Demo Trading Guide**: https://bybit-exchange.github.io/docs/v5/demo
- **Error Code Reference**: https://bybit-exchange.github.io/docs/v5/error

---

## Last Updated
May 13, 2026 - retCode 10032 fix implemented and verified
