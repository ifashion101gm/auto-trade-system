# Execution Modes Guide

## Overview

The Auto Trade System supports three distinct execution modes that control how trade proposals are handled. This allows you to gradually increase automation as you gain confidence in the system.

---

## 🎯 Three Execution Modes

### 1. Proposal Mode (`proposal`)

**Behavior:** AI analyzes market and generates trade proposals, but does NOT execute them.

**Use Case:** 
- Initial testing phase
- Manual review of all trades
- Learning how the AI makes decisions
- Backtesting strategy ideas

**Workflow:**
```
Market Data → AI Analysis → Trade Proposal → API Response (NO EXECUTION)
                                                    ↓
                                            You manually execute
                                            on exchange if desired
```

**Configuration:**
```bash
EXECUTION_MODE=proposal
```

**API Endpoint:**
```bash
POST /trading/paper-trading/run-cycle
```

**Response:**
```json
{
  "status": "success",
  "trade_proposal": {
    "symbol": "BTC/USDT",
    "side": "LONG",
    "entry_price": 45000.0,
    "stop_loss": 44100.0,
    "take_profit": 46800.0,
    "leverage": 2,
    "confidence": 0.85
  },
  "execution_mode": "proposal",
  "message": "Trade proposal generated. Manual execution required."
}
```

---

### 2. Semi-Auto Mode (`semi-auto`) ⭐ RECOMMENDED

**Behavior:** AI generates proposal and saves it to database. Human must explicitly confirm before execution.

**Use Case:**
- Production trading with oversight
- Balancing automation with human judgment
- Risk management with manual approval
- Default mode for most users

**Workflow:**
```
Market Data → AI Analysis → Trade Proposal → Save to DB → Return Proposal ID
                                                        ↓
                                          You review and call confirm endpoint
                                                        ↓
                                          POST /trading/confirm-trade/{id}
                                                        ↓
                                              Order executed on exchange
```

**Configuration:**
```bash
EXECUTION_MODE=semi-auto
```

**Step 1: Generate Proposal**
```bash
POST /trading/paper-trading/run-cycle
```

**Response:**
```json
{
  "status": "success",
  "proposal_id": "prop_12345",
  "trade_proposal": {
    "symbol": "BTC/USDT",
    "side": "LONG",
    "entry_price": 45000.0,
    "stop_loss": 44100.0,
    "take_profit": 46800.0,
    "leverage": 2
  },
  "execution_mode": "semi-auto",
  "message": "Proposal saved. Call /trading/confirm-trade/prop_12345 to execute."
}
```

**Step 2: Confirm Execution**
```bash
POST /trading/confirm-trade/prop_12345
```

**Response:**
```json
{
  "status": "executed",
  "order_id": "binance_order_98765",
  "filled_price": 45005.50,
  "execution_time_ms": 245
}
```

**Safety Features:**
- Proposals expire after 5 minutes (prevents stale executions)
- Can reject/cancel proposals if market conditions change
- Full audit trail in database
- Telegram notification sent on confirmation

---

### 3. Fully-Auto Mode (`fully-auto`)

**Behavior:** AI generates proposal and immediately executes on exchange without human intervention.

**Use Case:**
- High-frequency trading strategies
- Fully automated systems with proven track record
- After extensive testing and validation
- **WARNING:** Use with real funds only after thorough testing

**Workflow:**
```
Market Data → AI Analysis → Trade Proposal → IMMEDIATE EXECUTION → Telegram Alert
```

**Configuration:**
```bash
EXECUTION_MODE=fully-auto
```

**API Endpoint:**
```bash
POST /trading/paper-trading/run-cycle
```

**Response:**
```json
{
  "status": "executed",
  "order_id": "binance_order_98765",
  "trade_proposal": {
    "symbol": "BTC/USDT",
    "side": "LONG",
    "entry_price": 45000.0,
    "stop_loss": 44100.0,
    "take_profit": 46800.0,
    "leverage": 2
  },
  "execution_mode": "fully-auto",
  "filled_price": 45005.50,
  "execution_time_ms": 312,
  "message": "Trade executed automatically on Binance Testnet"
}
```

**⚠️ Critical Warnings:**
1. **Test extensively on testnet first** - At least 100 successful paper trades
2. **Start with small position sizes** - Limit initial risk
3. **Monitor continuously** - Watch for unexpected behavior
4. **Have emergency stop procedure** - Know how to pause the system
5. **Set conservative risk parameters** - Lower leverage, tighter stops

---

## 🔧 How to Switch Modes

### Method 1: Edit `.env` File

```bash
# Open .env file
nano .env

# Change this line:
EXECUTION_MODE=semi-auto

# To:
EXECUTION_MODE=proposal
# or
EXECUTION_MODE=fully-auto

# Save and restart the application
```

### Method 2: Environment Variable

```bash
# Set before starting application
export EXECUTION_MODE=proposal

# Start application
uvicorn app.main:app --reload
```

### Method 3: Runtime Override (Advanced)

You can override the mode per-request by passing it in the API call:

```bash
POST /trading/paper-trading/run-cycle
Content-Type: application/json

{
  "market_data": {...},
  "execution_mode_override": "proposal"  # Overrides config for this request
}
```

---

## 📊 Mode Comparison Table

| Feature | Proposal | Semi-Auto | Fully-Auto |
|---------|----------|-----------|------------|
| **AI Analysis** | ✅ | ✅ | ✅ |
| **Trade Proposal** | ✅ | ✅ | ✅ |
| **Database Save** | ❌ | ✅ | ✅ |
| **Auto Execution** | ❌ | ❌ | ✅ |
| **Human Approval** | N/A | ✅ Required | ❌ Not Required |
| **Telegram Alert** | Optional | On Confirm | Immediate |
| **Risk Level** | 🟢 Low | 🟡 Medium | 🔴 High |
| **Best For** | Testing | Production | Advanced Users |
| **Recommended** | Beginners | Most Users | Experts Only |

---

## 🛡️ Safety Checklist by Mode

### Before Using Proposal Mode
- [ ] API keys configured
- [ ] Database initialized
- [ ] Understand trade proposal structure
- [ ] Know how to manually execute on exchange

### Before Using Semi-Auto Mode
- [ ] All Proposal mode checks completed
- [ ] Telegram notifications working
- [ ] Tested proposal confirmation flow
- [ ] Reviewed default risk parameters
- [ ] Set appropriate position sizes

### Before Using Fully-Auto Mode
- [ ] All Semi-Auto mode checks completed
- [ ] **At least 100 successful testnet trades**
- [ ] **Positive P&L over 30+ days**
- [ ] Circuit breaker tested and understood
- [ ] Emergency stop procedure documented
- [ ] Monitoring/alerting in place
- [ ] Start with minimal capital
- [ ] Have backup internet/connection

---

## 🔄 Transition Strategy

### Phase 1: Learning (Week 1-2)
**Mode:** `proposal`

- Run system daily
- Review every trade proposal
- Manually execute promising trades
- Track performance in spreadsheet
- Learn AI decision patterns

### Phase 2: Validation (Week 3-4)
**Mode:** `semi-auto`

- Let AI generate proposals
- Review and confirm/reject each one
- Build confidence in system
- Refine risk parameters
- Monitor Telegram alerts

### Phase 3: Automation (Month 2+)
**Mode:** `semi-auto` → `fully-auto` (gradual)

- Start with small position sizes
- Monitor first 50 auto-executed trades closely
- If profitable, gradually increase size
- Never skip monitoring entirely
- Keep semi-auto as fallback option

---

## 🚨 Emergency Procedures

### How to Pause Trading

**Method 1: Circuit Breaker (Automatic)**
System automatically pauses after 3 consecutive failures.

**Method 2: Manual Pause via API**
```bash
POST /ai/pause
{
  "reason": "Emergency stop - unusual market conditions"
}
```

**Method 3: Change Execution Mode**
```bash
# In .env file
EXECUTION_MODE=proposal  # Stops all auto-execution

# Restart application
```

**Method 4: Kill Process**
```bash
# Find process
ps aux | grep uvicorn

# Kill it
kill <PID>
```

### How to Resume Trading

```bash
# Reset circuit breaker
POST /ai/reset-circuit-breaker

# Or change mode back
EXECUTION_MODE=semi-auto

# Restart application
```

---

## 💡 Best Practices

### 1. Start Conservative
```bash
# Conservative settings for beginners
EXECUTION_MODE=proposal
BINANCE_TESTNET=true
ACTIVE_EXCHANGE=binance
MEXC_DEFAULT_MARKET_TYPE=futures  # or spot for lower risk
```

### 2. Use Testnet Extensively
```bash
# Always test on testnet first
BINANCE_TESTNET=true

# Switch to mainnet only after validation
# BINANCE_TESTNET=false  # Uncomment when ready
```

### 3. Monitor Closely
- Check Telegram alerts regularly
- Review database records daily
- Track P&L weekly
- Adjust parameters monthly

### 4. Document Everything
- Keep trading journal
- Note why you confirmed/rejected trades
- Record system issues
- Track performance metrics

### 5. Have Exit Strategy
- Define max loss threshold
- Know how to close all positions
- Keep emergency contact info handy
- Test shutdown procedure regularly

---

## 📞 Troubleshooting

### Issue: Trades not executing in fully-auto mode

**Check:**
1. Is `EXECUTION_MODE=fully-auto` in `.env`?
2. Are exchange API keys valid?
3. Is `BINANCE_TESTNET` set correctly?
4. Check logs for error messages

**Solution:**
```bash
# Verify configuration
python -c "from app.config import settings; print(settings.EXECUTION_MODE)"

# Check API connectivity
python -c "from app.infra.binance_client import BinanceClient; import asyncio; c=BinanceClient(); print(asyncio.run(c.fetch_balance()))"
```

### Issue: Confirmation endpoint returns 404

**Cause:** Proposal ID doesn't exist or expired

**Solution:**
- Ensure proposal was created in semi-auto mode
- Check proposal hasn't expired (5 min timeout)
- Verify proposal_id in URL matches response

### Issue: System paused unexpectedly

**Cause:** Circuit breaker triggered (3 consecutive failures)

**Solution:**
```bash
# Check status
GET /ai/status

# Reset if safe to continue
POST /ai/reset-circuit-breaker
```

---

## 🎓 Summary

- **Proposal Mode:** Learn and observe
- **Semi-Auto Mode:** Control with convenience ⭐
- **Fully-Auto Mode:** Maximum automation (experts only)

**Recommendation:** Start with `proposal`, move to `semi-auto` after 2 weeks, consider `fully-auto` only after 2+ months of profitable semi-auto trading.

**Remember:** There's no rush to automate. Many professional traders use semi-auto mode indefinitely because it provides the best balance of efficiency and control.

---

*Last updated: May 10, 2026*
