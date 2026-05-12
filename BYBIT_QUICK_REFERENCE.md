# Bybit Integration - Quick Reference Guide

## Quick Start

### 1. Verify Configuration
```bash
# Check API credentials are set
grep BYBIT .env
```

Expected output:
```
BYBIT_API_KEY=ShROT8PoWLCdmRaA9W
BYBIT_API_SECRET=1xdtnJEgqmDlMZfz0CkXvjmfODlioiVAmGGD
```

### 2. Run Validation
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate

# Interactive validation (recommended first time)
python scripts/validate_bybit_api.py

# Automated validation (for CI/CD or quick checks)
python scripts/validate_bybit_automated.py
```

### 3. Test Connection in Python
```python
from app.infra.bybit_client import BybitClient

# Testnet (Paper Trading)
client = BybitClient(testnet=True)
balance = await client.fetch_balance()
print(f"Testnet Balance: ${balance['total_usdt']}")

# Mainnet (Live Trading)
client = BybitClient(testnet=False)
balance = await client.fetch_balance()
print(f"Mainnet Balance: ${balance['total_usdt']}")

await client.close()
```

---

## Common Operations

### Fetch Market Data
```python
client = BybitClient(testnet=True)

# Get ticker
ticker = await client.fetch_ticker('BTC/USDT')
print(f"Price: ${ticker['last_price']}")

# Get OHLCV candles
candles = await client.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=100)
```

### Place Orders
```python
# Market Order
order = await client.create_market_order(
    symbol='BTC/USDT',
    side='buy',
    amount=0.001,
    leverage=5
)

# Limit Order
order = await client.create_limit_order(
    symbol='BTC/USDT',
    side='buy',
    amount=0.001,
    price=80000.0,
    leverage=5
)
```

### Check Order Status
```python
status = await client.fetch_order_status(
    order_id='your-order-id',
    symbol='BTC/USDT'
)
print(f"Status: {status['status']}")
```

### Manage Positions
```python
# Get all open positions
positions = await client.fetch_open_positions()

# Close a position
result = await client.close_position('BTC/USDT')
```

---

## Configuration Settings

### Environment Variables (.env)
```bash
# Required
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret

# Optional (defaults shown)
ACTIVE_EXCHANGE=bybit          # Switch from binance to bybit
EXECUTION_MODE=semi-auto       # proposal | semi-auto | fully-auto
GOLD_MAX_LEVERAGE=5            # Maximum leverage allowed
GOLD_RISK_PER_TRADE=0.01       # 1% risk per trade
LIVE_TRADING_MIN_BALANCE=100   # Minimum balance for live trading
```

### WebSocket Settings (app/config.py)
```python
WEBSOCKET_HEARTBEAT_INTERVAL = 30        # seconds
WEBSOCKET_HEARTBEAT_TIMEOUT = 45         # seconds
WEBSOCKET_RECONNECT_DELAY = 2            # initial delay
WEBSOCKET_MAX_RECONNECT_DELAY = 60       # max delay
WEBSOCKET_STALE_STREAM_THRESHOLD = 120   # force reconnect after
```

---

## Troubleshooting

### Issue: "InsufficientFunds" Error
**Cause:** Account balance is $0  
**Solution:** Fund your account
- Testnet: Use faucet at https://testnet.bybit.com/
- Mainnet: Transfer real funds

### Issue: "Invalid API Key" Error
**Cause:** Wrong credentials or permissions  
**Solution:**
1. Verify keys in `.env` file
2. Check API key has "Futures Trading" permission
3. Ensure IP whitelist includes your server

### Issue: Connection Timeout
**Cause:** Network issues or API rate limits  
**Solution:**
1. Check internet connectivity
2. Verify API rate limits not exceeded
3. Enable retry logic in code

### Issue: Testnet Not Working
**Cause:** Missing testnet URL configuration  
**Solution:** Already fixed in `bybit_client.py` v1.1
- Ensure you're using updated code
- Testnet URLs: `https://api-testnet.bybit.com/v5/*`

---

## Supported Symbols

### Popular Perpetual Swaps
- BTC/USDT (Bitcoin)
- ETH/USDT (Ethereum)
- XRP/USDT (Ripple)
- SOL/USDT (Solana)
- DOGE/USDT (Dogecoin)

### Gold Trading
- Note: Bybit doesn't have direct gold futures
- Alternative: Use PAXG/USDT (Paxos Gold token)
- Or stick with MEXC/Binance for GOLD(XAUT)/USDT

---

## Fee Structure

### Perpetual Swaps
- **Maker Fee:** 0.02%
- **Taker Fee:** 0.055%
- **Default Used:** 0.06% (conservative estimate)

### Calculation Example
```python
client = BybitClient()
fee_rate = client.get_trading_fee_rate()  # 0.0006

# For $1000 position
cost = client.calculate_total_cost(
    price=50000,
    amount=0.02,
    leverage=5,
    include_fee=True
)
# Base: $200, Fee: $0.12, Total: $200.12
```

---

## Safety Checklist

Before Live Trading:
- [ ] API keys configured and tested
- [ ] Testnet validation completed successfully
- [ ] Mainnet connection verified
- [ ] Account funded with minimum balance ($100+)
- [ ] Risk parameters reviewed and approved
- [ ] Execution mode set to 'proposal' or 'semi-auto'
- [ ] Stop-loss mechanisms understood
- [ ] Position monitoring in place
- [ ] Emergency close procedures documented

---

## Code Examples

### Complete Trading Cycle
```python
from app.infra.bybit_client import BybitClient
from app.config import settings

async def execute_trade():
    # Initialize client
    client = BybitClient(testnet=False)  # Mainnet
    
    try:
        # 1. Check balance
        balance = await client.fetch_balance()
        if balance['total_usdt'] < settings.LIVE_TRADING_MIN_BALANCE_USD:
            raise Exception("Insufficient balance")
        
        # 2. Get market data
        ticker = await client.fetch_ticker('BTC/USDT')
        current_price = ticker['last_price']
        
        # 3. Calculate position size
        risk_amount = balance['total_usdt'] * settings.GOLD_RISK_PER_TRADE
        entry_price = current_price
        stop_loss = entry_price * 0.98  # 2% below
        leverage = min(5, settings.GOLD_MAX_LEVERAGE)
        
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit
        
        # 4. Place order
        order = await client.create_market_order(
            symbol='BTC/USDT',
            side='buy',
            amount=quantity,
            leverage=leverage
        )
        
        print(f"Order placed: {order['order_id']}")
        return order
        
    finally:
        await client.close()
```

### Position Monitoring
```python
async def monitor_positions():
    client = BybitClient(testnet=False)
    
    try:
        positions = await client.fetch_open_positions()
        
        for pos in positions:
            pnl = pos['unrealized_pnl']
            print(f"{pos['symbol']}: PnL = ${pnl:.2f}")
            
            # Add your monitoring logic here
            # e.g., auto-close if loss exceeds threshold
            
    finally:
        await client.close()
```

---

## API Rate Limits

### Bybit V5 API Limits
- **Spot REST:** 120 requests per 5 seconds
- **Derivatives REST:** 120 requests per 5 seconds
- **WebSocket:** 500 requests per 5 minutes

### Best Practices
- ✅ Use WebSocket for real-time data
- ✅ Implement request caching
- ✅ Batch operations when possible
- ✅ Monitor rate limit headers
- ✅ Add exponential backoff on errors

---

## Support & Resources

### Documentation
- Official API Docs: https://bybit-exchange.github.io/docs/v5/intro
- CCXT Manual: https://docs.ccxt.com/en/latest/manual.html
- Testnet Guide: https://www.bybit.com/en-US/help-center/bybitHC_Article?id=000001923

### Community
- Discord: https://discord.gg/bybit
- Telegram: https://t.me/BybitEnglish
- GitHub Issues: Report bugs in project repo

### Emergency Contacts
- API Issues: api-support@bybit.com
- Trading Issues: support@bybit.com

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2026-05-12 | Fixed testnet URL configuration |
| 1.0 | 2026-05-10 | Initial Bybit client implementation |

---

**Last Updated:** May 12, 2026  
**Maintained By:** Auto Trade System Team
