# Bybit Testnet Market Order Testing

This directory contains scripts for testing market order placement on Bybit Testnet.

## 📋 Available Scripts

### 1. Interactive Test Script
**File:** `test_bybit_market_order.py`

A comprehensive test script with user confirmation and detailed output.

**Features:**
- ✅ User confirmation before placing orders
- ✅ Detailed step-by-step progress reporting
- ✅ Automatic order size calculation ($15 USD target)
- ✅ Smart symbol selection (XRP first, BTC fallback)
- ✅ Automatic cleanup (cancel open orders or close positions)
- ✅ Comprehensive error handling with troubleshooting tips
- ✅ Final test summary

**Usage:**
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python3 scripts/test_bybit_market_order.py
```

**Example Output:**
```
================================================================================
  Bybit Testnet Market Order Test
================================================================================

Timestamp: 2026-05-13 00:45:00

[Step 1] Initializing BybitClient...
   Testnet: True
   Demo Trading: False
   API Key: AEYrjMN6...Ga3y
   Rate Limit: 10 req/sec
   Recv Window: 5000ms
   ✅ Client initialized successfully

[Step 2] Checking account balance...
   USDT Balance: 10000.00 USDT

[Step 3] Fetching ticker data for order sizing...
   Symbol: XRP/USDT:USDT
   Current Price: $2.1234
   Target Order Value: $15.00 USD
   Calculated Amount: 7.06 XRP
   Estimated Cost: $14.99 USD

[Step 4] Placing market BUY order...
   Symbol: XRP/USDT:USDT
   Side: buy
   Amount: 7.06
   Type: MARKET

   ✅ Order placed successfully!
   Order ID: 12345678-abcd-efgh-ijkl-123456789012
   Status: filled
   Filled Price: $2.1234
   Amount: 7.06
   Filled: 7.06
   Remaining: 0
   Cost: $14.99
   Timestamp: 1715558700000

[Step 5] Checking order status and performing cleanup...
   Current Status: filled
   ✅ Order was filled successfully

[Step 6] Closing position...
   ✅ Position closed
   Close Order ID: 87654321-dcba-hgfe-lkji-210987654321
   Close Status: filled
   Close Price: $2.1240

================================================================================
  TEST SUMMARY
================================================================================
  ✅ Client Initialization: SUCCESS
  ✅ Balance Check: SUCCESS
  ✅ Ticker Fetch: SUCCESS
  ✅ Order Placement: SUCCESS
  ✅ Cleanup: COMPLETED
================================================================================

  🎉 Test completed successfully!
  Check your Bybit Testnet account for order history.
================================================================================
```

---

### 2. Automated Test Script
**File:** `test_bybit_market_order_auto.py`

A non-interactive version suitable for CI/CD pipelines or automated testing.

**Features:**
- ✅ No user confirmation required
- ✅ Concise output format
- ✅ Same safety checks and cleanup
- ✅ Exit codes for automation (0 = success, 1 = failure)

**Usage:**
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python3 scripts/test_bybit_market_order_auto.py
```

**Example Output:**
```
================================================================================
Bybit Testnet Market Order Test (Automated)
================================================================================
Timestamp: 2026-05-13 00:45:00

[1/6] Initializing BybitClient...
      ✅ Client initialized

[2/6] Checking account balance...
      USDT Balance: 10000.00 USDT

[3/6] Fetching ticker data...
      Symbol: XRP/USDT:USDT
      Price: $2.1234
      Order Amount: 7.06 XRP ($15.00)

[4/6] Placing market BUY order...
      ✅ Order placed: 12345678-abcd-efgh-ijkl-123456789012
      Status: filled
      Filled: 7.06

[5/6] Checking order status...
      Status: filled

[6/6] Performing cleanup...
      Order filled - closing position...
      ✅ Position closed: 87654321-dcba-hgfe-lkji-210987654321

================================================================================
✅ TEST PASSED - All steps completed successfully
================================================================================
```

---

## 🔧 Prerequisites

### 1. Configure Bybit Testnet Credentials

Ensure your `.env` file has the correct testnet credentials:

```bash
# Bybit Testnet API Keys
BYBIT_DEMO_API_KEY="your_testnet_api_key_here"
BYBIT_DEMO_API_SECRET="your_testnet_api_secret_here"

# Use Testnet (not Demo Trading)
BYBIT_USE_DEMO_DOMAIN=false

# Rate limiting and configuration
BYBIT_RATE_LIMIT_ENABLED=true
BYBIT_RATE_LIMIT_CALLS_PER_SECOND=10
BYBIT_RECV_WINDOW=5000
```

### 2. Get Testnet Credentials

1. Visit [Bybit Testnet](https://testnet.bybit.com/)
2. Sign up or log in
3. Go to **API Management**
4. Create new API key with permissions:
   - ✅ Order - Trade
   - ✅ Position - Read & Write
   - ✅ Account - Read
   - ✅ Wallet - Read
5. Copy API Key and Secret to `.env` file

### 3. Fund Your Testnet Account

Testnet provides virtual funds, but ensure you have sufficient USDT balance:
- Minimum recommended: 50 USDT
- Script uses: ~15 USDT per test

---

## 🎯 What the Scripts Do

### Step-by-Step Process:

1. **Initialize Client** - Creates `BybitClient` with testnet=True
2. **Check Balance** - Verifies sufficient USDT balance
3. **Fetch Ticker** - Gets current price for safe order sizing
4. **Calculate Size** - Determines amount for $15 USD order
5. **Place Order** - Executes market BUY order with 1x leverage
6. **Check Status** - Waits 2 seconds, then checks if filled
7. **Cleanup** - Either:
   - If filled → Closes the position
   - If open → Cancels the order
8. **Summary** - Prints test results

### Safety Features:

- ✅ Small order size ($15 USD) to minimize risk
- ✅ 1x leverage (no borrowed funds)
- ✅ Automatic cleanup to avoid orphaned positions
- ✅ Comprehensive error handling
- ✅ Detailed logging for debugging
- ✅ Client connection always closed properly

---

## 🐛 Troubleshooting

### Error: "API key is invalid (10003)"

**Causes:**
1. Wrong API key/secret
2. Key lacks required permissions
3. IP restriction blocking server

**Solution:**
```bash
# Verify credentials in .env
grep BYBIT_DEMO .env

# Check API key permissions on testnet.bybit.com
# Ensure these are enabled:
# - Order - Trade
# - Position - Read & Write
# - Account - Read
# - Wallet - Read
```

### Error: "Insufficient balance (110026)"

**Cause:** Not enough USDT in testnet account

**Solution:**
1. Log into [Bybit Testnet](https://testnet.bybit.com/)
2. Go to **Assets** → **Derivatives**
3. Click **Deposit** to add virtual USDT
4. Ensure balance > 50 USDT

### Error: "Timestamp error (10016)"

**Cause:** Server clock not synchronized

**Solution:** Already handled by `adjustForTimeDifference=True` in client initialization.

If persists, increase recvWindow:
```bash
# In .env
BYBIT_RECV_WINDOW=10000  # Increase to 10 seconds
```

### Error: "Rate limit exceeded"

**Cause:** Too many requests too quickly

**Solution:**
```bash
# In .env, reduce rate limit
BYBIT_RATE_LIMIT_CALLS_PER_SECOND=5  # Reduce to 5 req/sec
```

### Error: "Symbol not found" or "Trading pair unavailable"

**Cause:** Testnet doesn't support the selected symbol

**Solution:** Script automatically tries XRP first, then BTC. If both fail:
1. Check available pairs on testnet
2. Modify `test_symbol` in the script

---

## 📊 Expected Behavior

### Successful Test:
```
✅ Order placed → Status: filled → Position closed
```

### Order Still Open:
```
✅ Order placed → Status: open → Order cancelled
```

### Failed Order:
```
❌ Order placement failed → Troubleshooting tips displayed
```

---

## 🔒 Security Notes

### ⚠️ IMPORTANT SAFETY WARNINGS:

1. **TESTNET ONLY** - These scripts use testnet credentials (`testnet=True`)
2. **Virtual Funds** - No real money is at risk
3. **Small Orders** - Only ~$15 USD per test
4. **Automatic Cleanup** - Positions/orders are closed immediately
5. **Never Run on Mainnet** - Do NOT change `testnet=False` without thorough review

### Best Practices:

- ✅ Always verify `testnet=True` before running
- ✅ Check API key permissions (read-only where possible)
- ✅ Monitor testnet balance regularly
- ✅ Review logs for unexpected behavior
- ✅ Never commit `.env` file to version control

---

## 📝 Customization

### Change Order Size

Edit the `target_usd_value` variable:

```python
# In test_bybit_market_order.py or test_bybit_market_order_auto.py
target_usd_value = 20.0  # Change from 15.0 to 20.0
```

### Change Trading Symbol

Modify the symbol selection logic:

```python
# Try different symbols
test_symbol = "ETH/USDT:USDT"  # Ethereum
test_symbol = "SOL/USDT:USDT"  # Solana
test_symbol = "DOGE/USDT:USDT"  # Dogecoin
```

### Add Leverage

Change leverage parameter (use caution):

```python
order_result = await client.create_market_order(
    symbol=test_symbol,
    side='buy',
    amount=order_amount,
    leverage=3  # 3x leverage (riskier!)
)
```

**⚠️ Warning:** Higher leverage increases liquidation risk. Stick to 1x for testing.

---

## 🔄 Integration with CI/CD

To integrate the automated test into your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
name: Bybit Integration Test

on:
  push:
    branches: [ main ]

jobs:
  test-bybit:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run Bybit test
        env:
          BYBIT_DEMO_API_KEY: ${{ secrets.BYBIT_TESTNET_API_KEY }}
          BYBIT_DEMO_API_SECRET: ${{ secrets.BYBIT_TESTNET_API_SECRET }}
          BYBIT_USE_DEMO_DOMAIN: false
        run: |
          python3 scripts/test_bybit_market_order_auto.py
```

---

## 📚 Related Documentation

- [BybitClient Implementation](../app/infra/bybit_client.py)
- [Configuration Settings](../app/config.py)
- [Bybit Enhancement Summary](../BYBIT_ENHANCEMENT_SUMMARY.md)
- [Pybit SDK Comparison](../BYBIT_PYBIT_SDK_COMPARISON.md)
- [Official Bybit API Docs](https://bybit-exchange.github.io/docs/v5/intro)

---

## 💡 Tips

1. **Run During Low Volatility** - Avoid testing during major market moves
2. **Monitor Logs** - Watch for rate limit warnings
3. **Check Testnet UI** - Verify orders in Bybit Testnet web interface
4. **Test Multiple Symbols** - Ensure different pairs work correctly
5. **Document Issues** - Log any errors for future reference

---

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review error logs for specific error codes
3. Verify API key permissions on testnet.bybit.com
4. Consult [Bybit API Documentation](https://bybit-exchange.github.io/docs/v5/error)
5. Check project issues or contact maintainers

---

**Last Updated:** May 13, 2026  
**Status:** ✅ Production Ready for Testnet Testing
