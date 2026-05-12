# Bybit Trading Restrictions - Analysis & Solutions

**Date:** May 13, 2026  
**Status:** ⚠️ **RESTRICTIONS DETECTED** - Action Required

---

## 🚨 Current Issue

### Error Encountered on Testnet:
```
retCode: 10024
retMsg: "Dear User, The product or service you are seeking to access is not 
available to you due to regulatory restrictions."
```

### Error Encountered on Demo Trading:
```
retCode: 10032
retMsg: "Demo trading are not supported."
```

---

## 📊 Root Cause Analysis

### Problem 1: Testnet Regulatory Restriction (Error 10024)

**What it means:**
Your Bybit Testnet account has regional or KYC restrictions preventing derivatives (perpetual swap) trading.

**Common causes:**
1. **Geographic Restrictions** - Server IP from restricted region
2. **KYC Not Completed** - Testnet account lacks identity verification
3. **Account Type** - Derivatives trading not enabled
4. **Testnet Limitations** - Bybit periodically restricts testnet features

### Problem 2: Demo Trading Not Supported in CCXT (Error 10032)

**What it means:**
CCXT library doesn't fully support Bybit Demo Trading API endpoints.

**Why:**
- Demo Trading uses different API structure than standard V5 API
- CCXT focuses on live trading and testnet
- Demo Trading requires official `pybit` SDK for full support

---

## ✅ Recommended Solutions

### Solution 1: Complete KYC on Testnet (Recommended)

**Steps:**
1. Visit [Bybit Testnet](https://testnet.bybit.com/)
2. Log in with your testnet account
3. Go to **Profile** → **Identity Verification**
4. Complete Level 1 KYC (basic verification)
5. Wait for approval (usually instant on testnet)
6. Retry the order placement test

**Estimated Time:** 5-10 minutes  
**Success Rate:** High (if geographic restrictions don't apply)

---

### Solution 2: Check Geographic Restrictions

**Check your server's IP location:**
```bash
curl https://ipinfo.io/country
```

**Commonly restricted regions for derivatives:**
- Mainland China
- United States (certain states)
- Singapore
- Quebec, Canada
- Certain Middle Eastern countries

**If restricted:**
- Use a VPS in an allowed region (e.g., Singapore, Netherlands, Japan)
- Contact Bybit support for exceptions
- Consider using spot trading instead (less restrictive)

---

### Solution 3: Create New Testnet Account

**Steps:**
1. Visit [Bybit Testnet Signup](https://testnet.bybit.com/)
2. Create account with different email
3. **Immediately complete KYC verification**
4. Generate new API keys with full permissions:
   - ✅ Order - Trade
   - ✅ Position - Read & Write
   - ✅ Account - Read
   - ✅ Wallet - Read
5. Update `.env` with new credentials
6. Retry test

**Estimated Time:** 15-20 minutes  
**Success Rate:** Medium (depends on IP location)

---

### Solution 4: Switch to Spot Trading (Workaround)

**Why this might work:**
Spot trading often has fewer regulatory restrictions than derivatives.

**Current limitation:**
Our `BybitClient` is configured for derivatives (perpetual swaps). To use spot:

**Option A: Modify symbol format**
```python
# Change from perpetual swap to spot
test_symbol = "XRP/USDT"  # Spot (no :USDT suffix)
# Instead of
test_symbol = "XRP/USDT:USDT"  # Perpetual swap
```

**Option B: Create spot-specific client**
Would require code changes to `BybitClient` to support spot market type.

**Note:** This requires code modifications beyond current scope.

---

### Solution 5: Use Official Pybit SDK for Demo Trading

**Why:**
CCXT doesn't support Demo Trading, but official `pybit` SDK does.

**Implementation required:**
1. Install pybit: `pip install pybit`
2. Create separate `BybitDemoClient` class using pybit
3. Implement demo-specific API calls
4. Maintain unified interface with BaseExchange

**Effort:** Medium (requires new implementation)  
**Benefit:** Full Demo Trading support

---

### Solution 6: Contact Bybit Support

**When to use:**
If all other solutions fail

**Steps:**
1. Visit [Bybit Testnet Help Center](https://testnet.bybit.com/en/help-center)
2. Submit ticket with:
   - Error code: 10024
   - Issue: Regulatory restriction on derivatives trading
   - Request: Enable testnet derivatives access
   - Include: Testnet account email
3. Wait for response (1-3 business days)

---

## 🔍 Diagnostic Steps

Run these commands to gather more information:

### 1. Check Server IP Location
```bash
curl https://ipinfo.io/country
curl https://ipinfo.io/ip
```

### 2. Verify Testnet Account Status
- Log into [testnet.bybit.com](https://testnet.bybit.com/)
- Check Profile → Identity Verification status
- Verify API key permissions at User → Security → API Management

### 3. Test Manual Order Placement
- Try placing small order via testnet web interface
- See if restriction is account-wide or API-only
- Check if spot trading works (different from derivatives)

### 4. Check Testnet Announcements
- Visit [Testnet Announcements](https://testnet.bybit.com/en-US/announcements)
- Look for maintenance notices or feature restrictions

---

## 📋 Current Configuration Status

### Testnet Credentials (Currently Active):
```bash
BYBIT_DEMO_API_KEY="AEYrjMN6Gs2uYBGa3y"
BYBIT_DEMO_API_SECRET="Px2qeSlI9wo9EmysDHewrX4NxJctb7rfSnt3"
BYBIT_USE_DEMO_DOMAIN=false  # Using testnet
```

### Demo Trading Credentials (Available but not working with CCXT):
```bash
BYBIT_DEMO_API_KEY="EJswnKqHaQKyvY2sgz"
BYBIT_DEMO_API_SECRET="Yzfufhz4pmVLKFx6JL1t0GR4Nj7VtPHAzTzg"
```

---

## 🎯 Immediate Action Plan

### Step 1: Quick Diagnostics (5 minutes)
```bash
# Check IP location
curl https://ipinfo.io/country

# Verify testnet login
# Visit: https://testnet.bybit.com/

# Check KYC status
# Profile → Identity Verification
```

### Step 2: If KYC Not Complete (10 minutes)
- Complete KYC on testnet
- Retry order placement test

### Step 3: If Still Restricted (15 minutes)
- Create new testnet account with immediate KYC
- Generate new API keys
- Update `.env` and retry

### Step 4: If Geographic Restriction (Ongoing)
- Option A: Use VPS in allowed region
- Option B: Contact Bybit support
- Option C: Switch to spot trading (code changes needed)

---

## 📝 Code Changes Made

### Enhanced Error Handling
Added support for error code 10024 in `app/infra/bybit_client.py`:

```python
elif '"retCode":10024' in error_msg or '10024' in error_msg:
    logger.error("❌ Bybit Error 10024: Regulatory restriction")
    logger.error("   Possible causes:")
    logger.error("   1. Account not KYC verified on testnet")
    logger.error("   2. Geographic restrictions for your region")
    logger.error("   3. Derivatives trading not enabled")
    logger.error("   Solutions:")
    logger.error("   - Complete KYC verification on testnet.bybit.com")
    logger.error("   - Contact Bybit support for testnet access")
    logger.error("   - Try spot trading instead of derivatives")
```

### Created Diagnostic Script
- `scripts/diagnose_bybit_regulatory_issue.py` - Comprehensive diagnostic tool
- `scripts/test_bybit_demo_order.py` - Demo Trading test (limited by CCXT support)

---

## 💡 Key Insights

### Why Both Environments Failed:

1. **Testnet (api-testnet.bybit.com):**
   - ❌ Error 10024: Regulatory restrictions
   - Likely cause: Geographic or KYC limitations
   - Solution: Complete KYC or change IP location

2. **Demo Trading (api-demo.bybit.com):**
   - ❌ Error 10032: Not supported by CCXT
   - Cause: CCXT doesn't implement Demo Trading endpoints
   - Solution: Would need pybit SDK integration

### Best Path Forward:

**Immediate:** Complete KYC on existing testnet account  
**Alternative:** Create new testnet account with KYC  
**Long-term:** Consider pybit SDK integration for Demo Trading support

---

## 📚 References

- [Bybit Testnet](https://testnet.bybit.com/)
- [Bybit Demo Trading](https://www.bybit.com/en/trade/demo)
- [Bybit API Documentation](https://bybit-exchange.github.io/docs/v5/intro)
- [Bybit Error Codes](https://bybit-exchange.github.io/docs/v5/error)
- [Pybit SDK](https://github.com/bybit-exchange/pybit)
- [CCXT Bybit Implementation](https://docs.ccxt.com/#/exchanges/bybit)

---

## ✅ Next Steps Checklist

- [ ] Run diagnostic script: `python3 scripts/diagnose_bybit_regulatory_issue.py`
- [ ] Check server IP country: `curl https://ipinfo.io/country`
- [ ] Log into testnet and verify KYC status
- [ ] Complete KYC if not done
- [ ] Retry order placement test
- [ ] If still blocked, create new testnet account
- [ ] Consider spot trading workaround
- [ ] Evaluate pybit SDK integration for Demo Trading

---

**Last Updated:** May 13, 2026  
**Configuration:** Testnet mode active (`BYBIT_USE_DEMO_DOMAIN=false`)  
**Status:** Awaiting KYC completion or account recreation
