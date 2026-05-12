# Bybit Demo Account Setup - Action Required

**Date:** May 12, 2026  
**Status:** ⚠️ **ACTION REQUIRED**  
**Issue:** API keys show $0 balance but screenshot shows 100M+ USDT demo balance

---

## 🔍 Diagnostic Results

The diagnostic script revealed critical information:

### ✅ What's Working
- API connectivity: **PASS** (3,212 markets loaded)
- Authentication: **PASS** (API keys valid)
- Market data: **PASS** (XAG/USDT:USDT @ $84.16)
- Unified account endpoint: **ACCESSIBLE**

### ❌ What's Not Working
- Balance query: Returns **$0.00** (expected 100M+ USDT)
- Unified account coins: **Empty list** (no assets found)
- Trade history: **No trades** (expected if new demo account)
- Open orders: **None** (expected for fresh account)

### 🎯 Root Cause Analysis

**Most Likely Scenario:**
The API keys were generated from your **main/live account**, not the demo account shown in your screenshot.

**Evidence:**
1. API authentication works → Keys are valid
2. Balance returns $0 → No funds in this account
3. Empty coin list → Account has no assets at all
4. Screenshot shows 100M+ USDT → Different account entirely

**Conclusion:**
Bybit treats demo trading as a separate mode/account. API keys must be generated **while in demo mode** to access demo funds.

---

## 📋 Step-by-Step Resolution

### Step 1: Activate Demo Trading Mode

1. **Log into Bybit**
   ```
   Visit: https://www.bybit.com/en-US/login
   ```

2. **Navigate to Demo Trading**
   ```
   Click: "Trade" → "Demo Trading"
   OR visit directly: https://www.bybit.com/en/trade/demo
   ```

3. **Activate Demo Account** (if not already active)
   ```
   • Look for "Activate Demo Trading" button
   • Click to enable demo mode
   • Wait for virtual funds allocation (usually instant)
   • Verify you see "DEMO" badge in top-right corner
   ```

4. **Verify Demo Balance**
   ```
   • Check balance shows ~100M USDT
   • Confirm XAGUSDT perpetual contract is available
   • Take note of exact balance amount
   ```

---

### Step 2: Generate New API Keys FROM DEMO MODE

⚠️ **CRITICAL:** You MUST generate API keys while in demo mode!

1. **Stay in Demo Mode**
   ```
   • Ensure "DEMO" badge is visible
   • Do NOT switch back to live trading
   ```

2. **Navigate to API Management**
   ```
   • Click profile icon (top-right)
   • Select "API Management"
   • OR visit: https://www.bybit.com/en-US/user/security/api-management
   ```

3. **Create New API Key**
   ```
   • Click "Create New Key"
   • Select key type: "System Generated"
   • Name: "AutoTrade-Demo-[DATE]"
   ```

4. **Configure Permissions**
   ```
   ✓ Enable: "Read-Write"
   ✓ Enable: "Contract Trading" (for perpetuals)
   ✓ Enable: "Unified Trading" (if using unified account)
   ✗ Disable: "Withdrawal" (security best practice)
   ✗ Disable: "Transfer" (not needed for trading)
   ```

5. **Set IP Restrictions** (Recommended)
   ```
   • Add your server IP address
   • Or use "Any IP" for testing (less secure)
   ```

6. **Save Credentials**
   ```
   • Copy API Key immediately (shown only once!)
   • Copy API Secret immediately (shown only once!)
   • Store securely (password manager recommended)
   ```

7. **Verify Key Works**
   ```
   • The page should show "Demo Trading" indicator
   • Test with small API call before proceeding
   ```

---

### Step 3: Update Configuration

1. **Edit `.env` File**
   ```bash
   cd /home/admin/.openclaw/workspace/auto-trade-system
   nano .env
   ```

2. **Replace API Credentials**
   ```bash
   # OLD credentials (from live account)
   BYBIT_API_KEY=ShROT8PoWLCdmRaA9W
   BYBIT_API_SECRET=1xdtnJEgqmDlMZfz0CkXvjmfODlioiVAmGGD
   
   # NEW credentials (from demo account)
   BYBIT_API_KEY=[YOUR_NEW_DEMO_API_KEY]
   BYBIT_API_SECRET=[YOUR_NEW_DEMO_API_SECRET]
   ```

3. **Save and Exit**
   ```
   Ctrl+O → Enter → Ctrl+X
   ```

---

### Step 4: Validate New Configuration

1. **Run Diagnostic Script**
   ```bash
   cd /home/admin/.openclaw/workspace/auto-trade-system
   source .venv/bin/activate
   PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system \
     python scripts/diagnose_bybit_account.py
   ```

2. **Expected Results**
   ```
   [TEST 2] Standard Balance Endpoint
   ✅ Balance retrieved successfully
      USDT Total: $100,008,018.00  ← Should show demo balance!
      USDT Free: $100,008,018.00
      USDT Used: $0.00
   
   [TEST 3] Unified Account Endpoint
   ✅ Unified account data retrieved
      USDT Wallet Balance: $100,008,018.00
      USDT Available: $100,008,018.00
   ```

3. **Run Full Validation**
   ```bash
   python scripts/validate_bybit_automated.py
   ```

4. **Expected Output**
   ```
   TEST 1: API Configuration          ✅ PASS
   TEST 2: Demo Trading Connection    ✅ PASS (with real balance!)
   TEST 3: Mainnet Connection         ✅ PASS
   TEST 4: Market Data Fetching       ✅ PASS
   TEST 5: Order Placement Logic      ✅ PASS
   TEST 6: Risk Calculations          ✅ PASS
   
   Results: 6/6 passed
   ```

---

### Step 5: Test Order Placement (Optional)

Once balance is confirmed, you can test actual order placement:

1. **Enable Order Placement in Script**
   ```bash
   nano scripts/validate_bybit_automated.py
   ```

2. **Uncomment Order Code** (around line 180)
   ```python
   # BEFORE (disabled):
   print("   ⚠️  SKIPPED: Order placement disabled for safety")
   
   # AFTER (enabled):
   order = await client.create_market_order(
       symbol='XAG/USDT:USDT',
       side='buy',
       amount=1.0,
       leverage=1
   )
   print(f"   ✅ Order Placed: {order['order_id']}")
   ```

3. **Run Validation**
   ```bash
   python scripts/validate_bybit_automated.py
   ```

4. **Verify Order Execution**
   ```
   • Check script output for order ID
   • Log into Bybit web interface
   • Navigate to "Positions" or "Order History"
   • Confirm order appears in demo account
   ```

5. **Check Position**
   ```python
   # Quick position check
   python -c "
   import asyncio
   from app.infra.bybit_client import BybitClient
   
   async def check():
       client = BybitClient(testnet=False)
       positions = await client.fetch_open_positions()
       print(f'Open positions: {len(positions)}')
       for pos in positions:
           print(f\"  {pos['symbol']}: {pos['side']} {pos['size']}\")
       await client.close()
   
   asyncio.run(check())
   "
   ```

---

## 🚨 Troubleshooting

### Issue: Still Shows $0 Balance After New Keys

**Possible Causes:**
1. Generated keys while NOT in demo mode
2. Demo account not activated yet
3. Using wrong API endpoint

**Solutions:**
```bash
# 1. Verify demo mode is active
# Log into web interface, look for "DEMO" badge

# 2. Check unified account status
curl -X GET "https://api.bybit.com/v5/account/wallet-balance?accountType=UNIFIED" \
  -H "X-BAPI-API-KEY: YOUR_API_KEY" \
  -H "X-BAPI-SIGN: YOUR_SIGNATURE"

# 3. Try different account types
# UNIFIED, CONTRACT, FUND, SPOT
```

---

### Issue: "Insufficient Balance" Error When Placing Order

**Causes:**
- Account truly has no funds
- Funds locked in other positions
- Minimum order size not met

**Solutions:**
```python
# Check minimum order size
import ccxt.async_support as ccxt

async def check_limits():
    exchange = ccxt.bybit()
    await exchange.load_markets()
    market = exchange.market('XAG/USDT:USDT')
    print(f"Min amount: {market['limits']['amount']['min']}")
    print(f"Max amount: {market['limits']['amount']['max']}")
    await exchange.close()

asyncio.run(check_limits())
```

---

### Issue: API Key Permissions Error

**Error Message:**
```
{"retCode":10003,"retMsg":"API key permissions insufficient"}
```

**Solution:**
1. Go to API Management
2. Edit the API key
3. Enable "Contract Trading" permission
4. Enable "Unified Trading" if using unified account
5. Save changes
6. Wait 5 minutes for propagation

---

## 📊 Verification Checklist

Before considering setup complete, verify ALL items:

- [ ] Logged into Bybit web interface
- [ ] "DEMO" badge visible in top-right corner
- [ ] Balance shows 100M+ USDT (or expected demo amount)
- [ ] XAGUSDT perpetual contract accessible
- [ ] New API keys generated WHILE IN DEMO MODE
- [ ] API keys have "Contract Trading" permission
- [ ] API keys have "Read-Write" access
- [ ] `.env` file updated with new credentials
- [ ] Diagnostic script shows non-zero balance
- [ ] Validation script passes all 6 tests
- [ ] Can fetch XAG/USDT:USDT ticker successfully
- [ ] (Optional) Test order placed and visible in web interface
- [ ] (Optional) Position appears in open positions list

---

## 🎯 Success Criteria

Setup is complete when:

1. ✅ `diagnose_bybit_account.py` shows USDT balance > $0
2. ✅ `validate_bybit_automated.py` passes all 6 tests
3. ✅ Market data fetches correctly (XAG/USDT:USDT @ ~$84)
4. ✅ Orders can be placed (if enabled in script)
5. ✅ Positions can be queried and viewed

---

## 📞 Support Resources

### Bybit Documentation
- **API Docs:** https://bybit-exchange.github.io/docs/v5/intro
- **Demo Trading:** https://www.bybit.com/en/help-center/article/Demo-Trading
- **API Management:** https://www.bybit.com/en/help-center/article/How-to-create-API-key

### Common Issues
- **API Error Codes:** https://bybit-exchange.github.io/docs/v5/error
- **Rate Limits:** https://bybit-exchange.github.io/docs/v5/rate-limit
- **Testnet vs Demo:** https://www.bybit.com/en/help-center/article/Testnet-vs-Demo

### Community Support
- **Bybit Forum:** https://forum.bybit.com/
- **Discord:** https://discord.gg/bybit
- **Telegram:** https://t.me/BybitEnglish

---

## 🔄 Alternative Approach: Use Existing Live Account

If demo account setup proves difficult, you can:

1. **Fund Live Account** with small amount ($10-50)
2. **Use Conservative Settings** (1x leverage, tiny position sizes)
3. **Test with Real Money** (accepting small losses as learning cost)

**Configuration for Live Testing:**
```python
# In validation scripts
client = BybitClient(testnet=False)  # Use mainnet

# Tiny test order
order = await client.create_market_order(
    symbol='XAG/USDT:USDT',
    side='buy',
    amount=0.1,  # 0.1 oz silver (~$8.40)
    leverage=1    # No leverage
)
```

⚠️ **WARNING:** This uses REAL money. Only do this if you accept potential losses.

---

## 📝 Notes

### Why Demo Trading is Important
- **Risk-Free Learning:** Practice without financial risk
- **Strategy Testing:** Validate trading algorithms safely
- **API Familiarity:** Learn exchange mechanics
- **Bug Detection:** Find issues before live deployment

### Demo Trading Limitations
- **Market Conditions:** May not perfectly match live markets
- **Slippage:** Demo may have better fills than reality
- **Liquidity:** Demo might not reflect real liquidity constraints
- **Psychology:** No emotional pressure like real trading

### Best Practices
- Always test thoroughly in demo before going live
- Start with small position sizes when transitioning to live
- Monitor performance metrics closely during first week
- Keep detailed logs of all trades for analysis

---

## 🚀 Next Steps After Setup

Once demo account is working:

1. **Implement Paper Trading Logic**
   - Track virtual P&L
   - Simulate slippage and fees
   - Record trade history

2. **Add Monitoring & Alerts**
   - Balance threshold alerts
   - Position size limits
   - Daily P&L reports

3. **Develop Strategy Backtesting**
   - Historical data analysis
   - Performance metrics
   - Risk-adjusted returns

4. **Plan Live Deployment**
   - Gradual capital allocation
   - Risk management rules
   - Emergency stop procedures

---

**Last Updated:** May 12, 2026  
**Action Required:** Generate new API keys from demo account  
**Estimated Time:** 15-30 minutes  
