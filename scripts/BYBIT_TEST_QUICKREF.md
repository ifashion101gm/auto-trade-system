# Bybit Market Order Test - Quick Reference

## 🚀 Quick Start

### Interactive Test (Recommended for First Time)
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python3 scripts/test_bybit_market_order.py
```

### Automated Test (CI/CD or Repeated Testing)
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python3 scripts/test_bybit_market_order_auto.py
```

---

## ⚙️ Configuration Checklist

Before running tests, verify `.env` has:

```bash
# ✅ Required Settings
BYBIT_DEMO_API_KEY="your_testnet_key"
BYBIT_DEMO_API_SECRET="your_testnet_secret"
BYBIT_USE_DEMO_DOMAIN=false          # false = testnet, true = demo trading
BYBIT_RATE_LIMIT_ENABLED=true
BYBIT_RATE_LIMIT_CALLS_PER_SECOND=10
BYBIT_RECV_WINDOW=5000
```

---

## 📋 What Happens During Test

| Step | Action | Details |
|------|--------|---------|
| 1 | Initialize Client | Connects to testnet.bybit.com |
| 2 | Check Balance | Verifies USDT balance > 0 |
| 3 | Fetch Ticker | Gets XRP/USDT price |
| 4 | Calculate Size | ~$15 USD worth of XRP |
| 5 | Place Order | Market BUY with 1x leverage |
| 6 | Wait 2 Seconds | Allows order to fill |
| 7 | Check Status | Determines if filled or open |
| 8a | If Filled | Closes position automatically |
| 8b | If Open | Cancels order automatically |
| 9 | Summary | Prints test results |

**Total Time:** ~5-10 seconds  
**Cost:** ~$15 USDT (virtual funds on testnet)

---

## 🔍 Common Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 10003 | API key invalid | Check credentials & permissions |
| 10002 | Invalid parameter | Verify symbol format (XRP/USDT:USDT) |
| 10004 | Permissions denied | Enable Order/Position permissions |
| 10016 | Timestamp error | Already handled by client |
| 110026 | Insufficient balance | Add virtual USDT to testnet |
| 130021 | Position limit | Reduce order size |

---

## 🛠️ Troubleshooting One-Liners

```bash
# Check if credentials are set
grep BYBIT_DEMO .env

# Verify testnet balance (manual)
# Visit: https://testnet.bybit.com/en-US/assets

# Test client initialization only
python3 scripts/validate_bybit_config.py

# View recent logs
tail -f logs/trading.log | grep -i bybit
```

---

## 📊 Expected Output (Success)

```
✅ Client initialized
✅ Balance: 10000.00 USDT
✅ Order placed: [order-id]
✅ Status: filled
✅ Position closed
✅ TEST PASSED
```

---

## ❌ Expected Output (Failure)

```
❌ Failed to place order: Bybit authentication failed (10003)
   
   Troubleshooting:
   1. Check API key permissions (Order - Trade)
   2. Verify sufficient USDT balance
   3. Ensure testnet has the trading pair available
   4. Check if minimum order size is met
```

---

## 🔒 Safety Reminders

- ✅ **Testnet Only** - Uses virtual funds
- ✅ **Small Orders** - Only $15 per test
- ✅ **Auto Cleanup** - No orphaned positions
- ✅ **1x Leverage** - No liquidation risk
- ❌ **Never Mainnet** - Don't change `testnet=False`

---

## 📖 Full Documentation

See [BYBIT_ORDER_TEST_README.md](./BYBIT_ORDER_TEST_README.md) for:
- Detailed setup instructions
- Advanced customization options
- CI/CD integration examples
- Complete troubleshooting guide

---

**Quick Help:** If stuck, check error code in table above or run `python3 scripts/validate_bybit_config.py` first.
