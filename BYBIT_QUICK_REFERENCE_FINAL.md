# Bybit API Quick Reference

## Symbol Formats

### Perpetual Swaps (USDT-Margined)
```python
'XAG/USDT:USDT'  # Silver perpetual ✅ CORRECT
'BTC/USDT:USDT'  # Bitcoin perpetual
'ETH/USDT:USDT'  # Ethereum perpetual
```

### Spot Markets
```python
'XAG/USDT'       # Silver spot
'BTC/USDT'       # Bitcoin spot
```

**Rule:** For USDT-margined perpetuals, use `SYMBOL/USDT:USDT` format in CCXT.

---

## Demo Trading vs Testnet

### Bybit Uses Demo Trading (NOT Traditional Testnet)

| Feature | Traditional Testnet | Bybit Demo Trading |
|---------|-------------------|-------------------|
| API Endpoint | Separate testnet URL | Mainnet API |
| Account Mode | Set via code | Set via web interface |
| Funds | Requires faucet | Auto-allocated |
| Verification | API parameter | Web interface only |

### Connection Code
```python
# Bybit Demo Trading uses MAINNET API
client = BybitClient(testnet=False)  # Use mainnet for demo
```

**Important:** Cannot verify demo mode via API. Check at: https://www.bybit.com/en/trade/demo

---

## Quick Validation Commands

### Automated Validation (Recommended)
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python scripts/validate_bybit_automated.py
```

### Interactive Validation
```bash
python scripts/validate_bybit_api.py
```

### View Logs
```bash
cat /tmp/bybit_validation_final.log
```

---

## Common Operations

### Fetch Ticker Price
```python
from app.infra.bybit_client import BybitClient
import asyncio

async def get_price():
    client = BybitClient(testnet=False)
    ticker = await client.fetch_ticker('XAG/USDT:USDT')
    print(f"Silver Price: ${ticker['last_price']:,.2f}")
    await client.close()

asyncio.run(get_price())
```

### Place Market Order
```python
order = await client.create_market_order(
    symbol='XAG/USDT:USDT',
    side='buy',
    amount=1.0,      # 1 oz of silver
    leverage=1        # 1x leverage
)
print(f"Order ID: {order['order_id']}")
```

### Check Order Status
```python
status = await client.fetch_order_status(
    order_id='your-order-id',
    symbol='XAG/USDT:USDT'
)
print(f"Status: {status['status']}")
print(f"Filled: {status['filled']}")
```

### Get Open Positions
```python
positions = await client.fetch_positions()
for pos in positions:
    print(f"{pos['symbol']}: {pos['side']} {pos['size']}")
```

### Fetch OHLCV Data
```python
candles = await client.fetch_ohlcv(
    symbol='XAG/USDT:USDT',
    timeframe='1h',
    limit=10
)
for candle in candles:
    print(f"Time: {candle[0]}, Close: ${candle[4]:,.2f}")
```

---

## Risk Calculations

### Position Sizing
```python
balance = 10000          # Account balance
risk_pct = 0.01          # 1% risk per trade
entry = 84.16            # Entry price
stop_loss = 82.00        # Stop loss price
leverage = 5             # Max leverage

risk_amount = balance * risk_pct
risk_per_unit = abs(entry - stop_loss)
quantity = (risk_amount * leverage) / risk_per_unit
position_value = quantity * entry
margin_required = position_value / leverage

print(f"Quantity: {quantity:.2f} XAG")
print(f"Position Value: ${position_value:,.2f}")
print(f"Margin Required: ${margin_required:,.2f}")
```

---

## Troubleshooting

### Error: "market symbol not found"
```python
# WRONG
await client.fetch_ticker('XAG/USDT')

# CORRECT
await client.fetch_ticker('XAG/USDT:USDT')
```

### Error: "Insufficient balance"
- Verify account has sufficient funds
- For demo: Check demo mode is activated at https://www.bybit.com/en/trade/demo
- For live: Ensure real funds deposited

### Error: "404 Not Found" with duplicate paths
- Don't set custom URLs in exchange config
- Let CCXT handle URL routing automatically
- Only set `exchange_config['options']['test'] = True`

### Balance Shows $0 But Should Have Funds
- API keys may belong to different account
- Demo balance might require special endpoint
- Verify keys match the intended account
- Check sub-account settings if applicable

---

## Safety Checklist

Before placing orders:

- [ ] Verified account is in Demo mode (check web interface)
- [ ] Confirmed correct symbol format (`SYMBOL/USDT:USDT`)
- [ ] Checked current market price
- [ ] Calculated position size within risk limits
- [ ] Set appropriate leverage (start with 1x)
- [ ] Reviewed order parameters before execution
- [ ] Enabled safety checks in code

---

## Key URLs

- **Demo Trading Interface:** https://www.bybit.com/en/trade/demo
- **API Documentation:** https://bybit-exchange.github.io/docs/v5/intro
- **CCXT Bybit Docs:** https://docs.ccxt.com/#/exchanges/bybit

---

## Configuration Files

### Environment Variables (.env)
```bash
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
```

### Client Initialization
```python
from app.infra.bybit_client import BybitClient

# For Demo Trading (uses mainnet API)
client = BybitClient(testnet=False)

# For traditional testnet (if available)
client = BybitClient(testnet=True)
```

---

## Current Market Data (As of May 12, 2026)

| Symbol | Price | 24h Volume | Bid/Ask Spread |
|--------|-------|------------|----------------|
| XAG/USDT:USDT | $84.16 | $44.47M | $84.16 / $84.17 |

---

## Script Locations

- **Automated Validation:** `/scripts/validate_bybit_automated.py`
- **Interactive Validation:** `/scripts/validate_bybit_api.py`
- **Bybit Client:** `/app/infra/bybit_client.py`
- **Configuration:** `/app/config.py`
- **Credentials:** `/.env`

---

## Recent Changes (May 12, 2026)

✅ Fixed symbol format from `XAG/USDT` to `XAG/USDT:USDT`  
✅ Updated both validation scripts  
✅ Removed duplicate URL path configuration  
✅ Added Demo Trading documentation  
✅ Disabled automatic order placement for safety  
✅ All 6 validation tests passing  

---

**Last Updated:** May 12, 2026  
**Status:** Production Ready ✅
