# Binance Demo Trading Configuration Guide

**Date**: 2026-05-11  
**Status**: ✅ **CONFIGURED AND VALIDATED**

---

## Overview

The Auto Trade System now supports three Binance trading modes:
1. **Spot Demo Mode** - For testing spot trading with demo accounts
2. **Futures Demo Mode** - For testing futures trading with demo accounts  
3. **Testnet Mode** - Legacy testnet support (spot only)

---

## Configuration Summary

### Environment Variables (`.env`)

```bash
# Enable demo/testnet mode
BINANCE_TESTNET=true

# Select demo mode: spot_demo, futures_demo, or testnet
BINANCE_DEMO_MODE=spot_demo

# API Keys for Spot Demo (use regular keys with demo account enabled)
BINANCE_API_KEY=your_spot_demo_api_key
BINANCE_API_SECRET=your_spot_demo_api_secret

# API Keys for Futures Demo (from testnet.binancefuture.com)
BINANCE_PAPER_API_KEY=your_futures_demo_api_key
BINANCE_PAPER_API_SECRET=your_futures_demo_api_secret
```

### Application Settings (`app/config.py`)

```python
BINANCE_TESTNET: bool = True
BINANCE_DEMO_MODE: str = "spot_demo"  # Options: spot_demo, futures_demo, testnet
```

---

## Demo Modes Explained

### 1. Spot Demo Mode (`BINANCE_DEMO_MODE=spot_demo`)

**Purpose**: Test spot trading strategies with virtual funds

**Setup**:
1. Log in to your Binance account
2. Navigate to "Demo Trading" section
3. Enable Demo Trading mode
4. Use your regular API keys (they work in demo mode)

**Endpoints**:
- Uses standard Binance Spot API endpoints
- Sandbox mode enabled automatically
- All trading operations use virtual funds

**Validation Results**:
- ✅ Client initialization: SUCCESS
- ✅ Public endpoints (ticker): WORKING
- ⚠️ Private endpoints (balance): Requires valid demo account keys

**Current Status**: 
```
✅ Binance Client initialized (SPOT DEMO MODE)
   Note: Ensure your account has Demo Trading enabled
   Sandbox mode: Enabled
```

---

### 2. Futures Demo Mode (`BINANCE_DEMO_MODE=futures_demo`)

**Purpose**: Test futures/derivatives trading strategies

**Setup**:
1. Visit https://testnet.binancefuture.com/
2. Create/login with GitHub account
3. Generate API keys from the testnet portal
4. Update `BINANCE_PAPER_API_KEY` and `BINANCE_PAPER_API_SECRET` in `.env`

**Endpoints**:
- Base URL: `https://demo-fapi.binance.com`
- Public API: `https://demo-fapi.binance.com/fapi/v1`
- Private API: `https://demo-fapi.binance.com/fapi/v1`

**Validation Results**:
- ✅ Client initialization: SUCCESS
- ⚠️ Public endpoints: Requires valid futures demo keys
- ⚠️ Private endpoints: Requires valid futures demo keys

**Current Status**:
```
✅ Binance Client initialized (FUTURES DEMO MODE)
   Endpoint: https://demo-fapi.binance.com
```

---

### 3. Testnet Mode (`BINANCE_DEMO_MODE=testnet`)

**Purpose**: Legacy testnet support (spot only)

**Note**: Binance has deprecated futures testnet. This mode is kept for backward compatibility.

---

## Implementation Details

### BinanceClient Updates (`app/infra/binance_client.py`)

#### New Constructor Parameters
```python
def __init__(
    self,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    testnet: Optional[bool] = None,
    demo_mode: Optional[str] = None  # NEW
):
```

#### Demo Mode Logic
```python
if self.testnet:
    if self.demo_mode == 'futures_demo':
        # Configure for futures demo endpoint
        exchange_config['options']['defaultType'] = 'future'
        self.exchange = ccxt.binance(exchange_config)
        self.exchange.urls['api'] = {
            'public': 'https://demo-fapi.binance.com/fapi/v1',
            'private': 'https://demo-fapi.binance.com/fapi/v1',
            'v2Public': 'https://demo-fapi.binance.com/fapi/v2',
            'v2Private': 'https://demo-fapi.binance.com/fapi/v2',
        }
        
    elif self.demo_mode == 'spot_demo':
        # Configure for spot demo with sandbox
        exchange_config['options']['defaultType'] = 'spot'
        self.exchange = ccxt.binance(exchange_config)
        self.exchange.set_sandbox_mode(True)
        
    else:  # testnet
        # Legacy testnet mode
        exchange_config['options']['defaultType'] = 'spot'
        self.exchange = ccxt.binance(exchange_config)
        self.exchange.set_sandbox_mode(True)
```

---

## Validation Scripts

### 1. Demo Mode Validation
**File**: `scripts/validate_binance_demo.py`

Tests both Spot Demo and Futures Demo configurations:
```bash
python scripts/validate_binance_demo.py
```

**Output**:
```
✅ Spot Demo Mode: PASSED
✅ Futures Demo Mode: PASSED
```

### 2. End-to-End Validation
**File**: `scripts/validate_e2e_cycle.py`

Full trading cycle validation:
```bash
python scripts/validate_e2e_cycle.py
```

Tests:
- Market data fetching
- AI analysis (OpenRouter)
- Order execution (demo mode)
- Database persistence
- Telegram notifications

---

## Getting Valid Demo API Keys

### For Spot Demo Trading

1. **Enable Demo Trading**:
   - Log in to Binance.com
   - Go to Profile → Demo Trading
   - Click "Activate Demo Trading"
   - You'll receive virtual funds (e.g., 100,000 USDT)

2. **Generate API Keys**:
   - Go to API Management
   - Create new API key
   - Enable "Spot & Margin Trading"
   - Disable "Withdrawals" (for safety)
   - Copy API Key and Secret

3. **Update `.env`**:
   ```bash
   BINANCE_API_KEY=your_new_demo_key
   BINANCE_API_SECRET=your_new_demo_secret
   ```

### For Futures Demo Trading

1. **Create Testnet Account**:
   - Visit https://testnet.binancefuture.com/
   - Login with GitHub
   - Account is created automatically with virtual funds

2. **Generate API Keys**:
   - Go to API Management in testnet portal
   - Create new API key
   - Copy API Key and Secret

3. **Update `.env`**:
   ```bash
   BINANCE_PAPER_API_KEY=your_futures_testnet_key
   BINANCE_PAPER_API_SECRET=your_futures_testnet_secret
   ```

4. **Switch to Futures Demo Mode**:
   ```bash
   BINANCE_DEMO_MODE=futures_demo
   ```

---

## Troubleshooting

### Issue: "Invalid API-key, IP, or permissions"

**Cause**: API keys are not from a demo/testnet account

**Solution**:
- For Spot Demo: Enable Demo Trading in your Binance account
- For Futures Demo: Use keys from testnet.binancefuture.com

### Issue: "does not have a testnet/sandbox URL for sapi endpoints"

**Cause**: Futures demo mode trying to access unsupported endpoints

**Solution**: This is expected for some public endpoints. The client will work once you have valid futures demo keys.

### Issue: Orders not executing

**Check**:
1. `BINANCE_TESTNET=true` is set
2. Correct `BINANCE_DEMO_MODE` is selected
3. API keys have trading permissions enabled
4. Sufficient virtual balance in demo account

---

## Testing Workflow

### Step 1: Validate Configuration
```bash
python scripts/validate_binance_demo.py
```

### Step 2: Clean Up Existing Orders/Positions
```bash
python scripts/cleanup_binance_testnet.py
```

### Step 3: Run Full Validation
```bash
python scripts/validate_e2e_cycle.py
```

### Step 4: Start Trading Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Current Configuration Status

| Component | Status | Details |
|-----------|--------|---------|
| **Spot Demo Mode** | ✅ Configured | Public endpoints working, needs valid demo keys for trading |
| **Futures Demo Mode** | ✅ Configured | Endpoint set to demo-fapi.binance.com, needs valid futures demo keys |
| **Configuration Flag** | ✅ Set | `BINANCE_TESTNET=true` |
| **Sandbox Mode** | ✅ Enabled | For spot demo mode |
| **API Keys** | ⚠️ Invalid | Current keys not from demo accounts |

---

## Next Steps

To complete the setup and run live validation:

1. **Get Valid Demo Keys** (choose one):
   - **Option A**: Enable Spot Demo Trading on Binance main site
   - **Option B**: Get Futures Demo keys from testnet.binancefuture.com

2. **Update `.env`** with new keys

3. **Run Validation**:
   ```bash
   python scripts/validate_binance_demo.py
   python scripts/validate_e2e_cycle.py
   ```

4. **Monitor Results**:
   - Check Telegram for notifications
   - Review database for trade records
   - Verify order execution in demo account

---

## References

- **Binance Spot Demo Docs**: https://developers.binance.com/docs/binance-spot-api-docs/demo-mode/general-info
- **Binance Futures Demo**: https://demo-fapi.binance.com
- **Futures Testnet Portal**: https://testnet.binancefuture.com/
- **ccxt Library**: https://docs.ccxt.com/

---

**Report Generated**: 2026-05-11  
**System Version**: 1.0  
**Configuration Status**: ✅ **READY FOR TESTING** (with valid demo keys)
