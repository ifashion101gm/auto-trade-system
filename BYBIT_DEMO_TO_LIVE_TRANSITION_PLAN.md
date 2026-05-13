# Bybit Demo → Live Trading Transition Plan - Gold Bot V2 Elite

**Strategy**: Gold Bot Version 2 Elite (95% Pro Level)  
**Primary Gate**: **$100 USD Net Profit from $100 Starting Balance**  
**Current Environment**: Bybit Demo (`BYBIT_USE_DEMO_DOMAIN=true`) ✅  
**Starting Balance**: $100.00 (virtual funds)  
**Current Progress**: $0.00 profit (0 trades executed)  
**Target Symbol**: XAU/USDT:USDT (Gold Perpetual Swap)  
**Date Created**: May 13, 2026  
**Last Updated**: May 13, 2026 (Balance verified)  
**Status**: 🚦 READY TO BEGIN - Configuration updates needed  

---

## 🎯 EXECUTIVE SUMMARY: THE $100 GATE

### Critical Rule
**NO LIVE TRADING is authorized until the system achieves $100 NET PROFIT in Bybit Demo environment.**

Starting from **$100 virtual balance**, the system must generate **$100 profit** (100% return) before live trading authorization. This is a **non-negotiable gate**. The demo environment serves as the proving ground where the strategy must demonstrate it can generate consistent profits with elite risk management before real capital is at risk.

### Why $100 Demo Profit from $100 Starting Balance?
- **Proves Strategy Viability**: Doubling account demonstrates clear edge
- **Validates Risk Management**: Achieving 100% return without exceeding 2% daily DD shows discipline
- **Tests All 11 Agents**: Master Controller, Market Scanner, Strategy, Risk Manager, Execution, etc.
- **Builds Confidence**: Statistical evidence before committing real funds
- **Realistic Timeline**: Achievable in 4-8 weeks with proper execution (2-4 trades/day)

### Current Status (May 13, 2026)
- ✅ Demo environment configured (`BYBIT_USE_DEMO_DOMAIN=true`)
- ✅ Starting balance: $100.00
- ⚠️ Configuration needs updates (ACTIVE_EXCHANGE, risk parameters)
- ⏳ Ready to begin trading toward $100 profit goal

---

## 🚀 IMMEDIATE ACTION ITEMS (Do This Now)

### Step 1: Update .env Configuration (5 minutes)

Open `.env` file and make these **4 critical changes**:

```bash
# Line 132: Change active exchange
ACTIVE_EXCHANGE=bybit                    # Was: binance

# Line 94: Reduce automation for safety  
EXECUTION_MODE=semi-auto                 # Was: fully-auto

# Line 141: Reduce leverage
GOLD_MAX_LEVERAGE=3                      # Was: 5

# Line 142: Reduce risk per trade
GOLD_RISK_PER_TRADE=0.005                # Was: 0.01 (now 0.5%)
```

Save the file.

### Step 2: Restart Application

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 3: Verify Configuration

```bash
python scripts/check_bybit_demo_balance.py
```

**Expected Output:**
```
✅ Using Demo Environment
✅ Active exchange is Bybit
✅ Risk per trade is conservative (0.50%)
✅ Leverage is conservative (3x)
```

### Step 4: Begin Trading

Once configuration is verified, start executing trades toward the $100 profit goal!

---

## 📋 CURRENT CONFIGURATION STATUS

### Current Account Status (Verified May 13, 2026)

```bash
Starting Balance: $100.00 (virtual funds in Bybit Demo)
Current Balance: $100.00
Cumulative Profit: $0.00
Total Trades: 0
Closed Trades: 0
Progress to Goal: 0%
```

**Configuration Status**:
- ✅ `BYBIT_USE_DEMO_DOMAIN=true` (Using api-demo.bybit.com)
- ❌ `ACTIVE_EXCHANGE=binance` (Must change to 'bybit')
- ⚠️ `EXECUTION_MODE=fully-auto` (Should be 'semi-auto' for safety)
- ⚠️ `GOLD_RISK_PER_TRADE=0.01` (Too high, change to 0.005 = 0.5%)
- ⚠️ `GOLD_MAX_LEVERAGE=5` (Too high, change to 3)

**Current .env Settings** (as of May 13, 2026):

```bash
# ✅ CORRECT - Using Demo Environment
BYBIT_USE_DEMO_DOMAIN=true              # Line 80
BYBIT_DEMO_API_KEY="EJswnKqHaQKyvY2sgz"              # Line 74
BYBIT_DEMO_API_SECRET="Yzfufhz4pmVLKFx6JL1t0GR4Nj7VtPHAzTzg"  # Line 75

# ❌ NEEDS ADJUSTMENT
ACTIVE_EXCHANGE=binance                 # Line 132 - Must change to 'bybit'
EXECUTION_MODE=fully-auto               # Line 94 - Should be 'semi-auto'
GOLD_RISK_PER_TRADE=0.01                # Line 142 - Too high, change to 0.005
GOLD_MAX_LEVERAGE=5                     # Line 141 - Too high, change to 3

# ✅ CORRECT
TELEGRAM_BOT_TOKEN=configured           # Line 104
TELEGRAM_CHAT_ID=configured             # Line 107
DATABASE_URL=postgresql://...           # Line 13
```

### Required Configuration Changes

**Edit `.env` file immediately:**

```bash
# Line 132: Change active exchange
ACTIVE_EXCHANGE=bybit                    # Was: binance

# Line 94: Reduce automation for safety
EXECUTION_MODE=semi-auto                 # Was: fully-auto

# Line 98: Lower auto-execute threshold
AUTO_EXECUTE_THRESHOLD_USD=15.0          # Was: 100.0

# Lines 141-143: Adjust risk parameters
GOLD_MAX_LEVERAGE=3                      # Was: 5
GOLD_RISK_PER_TRADE=0.005                # Was: 0.01 (now 0.5%)
GOLD_MIN_CONFIDENCE=0.75                 # Add this line (elite threshold)
```

**After changes:**
```bash
# Restart application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 🚀 PHASE 1: CONFIGURATION ALIGNMENT (Day 0)

### Step 1.1: Update .env File
- [ ] Change `ACTIVE_EXCHANGE` from `binance` to `bybit`
- [ ] Change `EXECUTION_MODE` from `fully-auto` to `semi-auto`
- [ ] Change `GOLD_RISK_PER_TRADE` from `0.01` to `0.005`
- [ ] Change `GOLD_MAX_LEVERAGE` from `5` to `3`
- [ ] Add `GOLD_MIN_CONFIDENCE=0.75`
- [ ] Save file and restart application

### Step 1.2: Verify Demo Connectivity
```bash
python scripts/check_bybit_demo_readiness.py
```

**Expected Output:**
```
✅ Bybit Demo Environment: READY
✅ Starting Balance: $100.00 (virtual)
✅ Risk Parameters: 0.5% per trade, 3x leverage
✅ Safety Systems: Active
```

### Step 1.3: Confirm Telegram Alerts
```bash
python -c "
import asyncio
from app.infra.telegram_notifier import TelegramNotifier

async def test():
    notifier = TelegramNotifier()
    success = await notifier.send_message('🧪 Gold Bot V2 Elite - Demo Validation Starting')
    print('✅ Telegram working' if success else '❌ Telegram failed')

asyncio.run(test())
"
```

**Phase 1 Complete When:**
- [ ] All configuration changes applied
- [ ] Demo API connectivity verified
- [ ] Telegram alerts working
- [ ] Application restarted successfully

---

## 💰 PHASE 2: $100 DEMO PROFIT EXECUTION (Days 1-60)

### Success Metrics Dashboard

**PRIMARY GOAL: Achieve $100 NET PROFIT from $100 Starting Balance (100% return)**

**Current Status**: $0.00 profit / $100.00 target (0% complete)

| Metric | Elite Target | Minimum Acceptable | Current Status |
|--------|--------------|-------------------|----------------|
| **Cumulative Profit** | **$100** | **$100 (REQUIRED)** | **$0.00** |
| Total Closed Trades | 50+ | 30+ | 0 |
| Win Rate | ≥60% | ≥55% | N/A |
| Profit Factor | ≥2.0 | ≥1.5 | N/A |
| Max Drawdown | ≤2% | ≤5% | 0% |
| Avg R:R Ratio | ≥2:1 | ≥1.5:1 | N/A |
| Consecutive Losses Max | 2 | 3 | 0 |
| Daily DD Breaches | 0 | ≤2 | 0 |

**Critical Rule**: If ANY metric fails minimum acceptable threshold → Continue demo trading until all criteria pass.

### Daily Trading Protocol

**Risk Parameters (Elite):**
- Risk per trade: 0.5% ($0.50 on $100 balance)
- Max daily loss: 2% ($2.00) → STOP TRADING if reached
- Max consecutive losses: 2 → PAUSE after 2 losses
- Max open positions: 1
- Leverage: 3x maximum
- Min confidence score: 75/100

**Session Rules:**
- Trade London session (8:00-17:00 UTC) or NY session (13:00-22:00 UTC)
- Avoid high-impact news (CPI, NFP, FOMC)
- Maximum 2-4 trades per day
- No revenge trading after losses

**Exit Strategy (Multi-Layer TP):**
- 40% close at 1R (risk-reward 1:1)
- 40% close at 2R (risk-reward 2:1)
- 20% runner with trailing stop (EMA20 or ATR-based)

### Progress Tracking Template

**Daily Log** (Start filling this out from Day 1):
```
Date: ___________
Starting Balance: $100.00
Current Balance: $_____
Trades Executed Today: _____
Wins: _____ | Losses: _____
Daily P/L: $_____
Cumulative Profit: $_____ (Target: $100)
Max DD Today: _____%
Notes: ____________________
```

**Weekly Summary**:
```
Week: _____
Total Trades: _____
Win Rate: _____%
Weekly P/L: $_____
Cumulative Profit: $_____ / $100.00 target
Best Trade: $_____
Worst Trade: $_____
Lessons Learned: ____________________
```

### Milestone Checkpoints

**Checkpoint 1: $25 Profit (25% of goal)**
- [ ] Review first 10-15 trades
- [ ] Verify win rate ≥55%
- [ ] Confirm max DD ≤5%
- [ ] Assess AI confidence accuracy
- [ ] **Current**: $0.00 → Need $25.00

**Checkpoint 2: $50 Profit (50% of goal - HALFWAY)**
- [ ] Analyze best/worst setups
- [ ] Review session timing effectiveness
- [ ] Check if position sizing optimal
- [ ] Adjust filters if needed
- [ ] **Current**: $0.00 → Need $50.00

**Checkpoint 3: $75 Profit (75% of goal)**
- [ ] Comprehensive performance review
- [ ] Verify consistency across market conditions
- [ ] Test self-learning adjustments
- [ ] Prepare for final push to $100
- [ ] **Current**: $0.00 → Need $75.00

**FINAL MILESTONE: $100 Profit (100% of goal - GOAL ACHIEVED)**
- [ ] All success criteria met
- [ ] Ready for Phase 3 verification
- [ ] **Current**: $0.00 → Need $100.00

---

## 🔍 PHASE 3: MILESTONE VERIFICATION (When Profit = $100)

### Step 3.1: Run Comprehensive Validation

```bash
python scripts/check_bybit_demo_readiness.py
```

**Required Results:**
```
✅ Cumulative Profit: $100+ achieved
✅ Win Rate: ≥55% (≥60% elite)
✅ Profit Factor: ≥1.5 (≥2.0 elite)
✅ Max Drawdown: ≤5% (≤2% elite)
✅ R:R Ratio: ≥1.5:1 (≥2:1 elite)
✅ Total Trades: ≥30 (≥50 elite)
```

### Step 3.2: Quality Assessment

**Trade Quality Review:**
- [ ] Entry logic followed Smart Money principles
- [ ] Stop losses respected (no manual overrides)
- [ ] Take profits executed according to plan (40%/40%/20%)
- [ ] Trailing stops activated correctly
- [ ] AI confidence scores correlated with outcomes
- [ ] Session timing filters effective
- [ ] News avoidance protocol followed

**Risk Management Review:**
- [ ] Daily DD limit (2%) never exceeded more than 2 times
- [ ] Consecutive loss pause (2 losses) triggered correctly
- [ ] Position sizing remained at 0.5% throughout
- [ ] Leverage stayed ≤3x on all trades
- [ ] No overtrading (max 2-4 trades/day)

**System Reliability Review:**
- [ ] Zero critical API errors
- [ ] Telegram alerts delivered consistently
- [ ] Database persistence reliable (no data loss)
- [ ] WebSocket reconnections <5 total
- [ ] Circuit breaker never triggered unexpectedly

### Step 3.3: Performance Analysis

**Statistical Significance Check:**
```bash
python -c "
import asyncio
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
from sqlalchemy import select, func

async def analyze():
    async with async_session_maker() as db:
        # Get all closed Bybit trades
        result = await db.execute(
            select(PaperTrades)
            .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
            .order_by(PaperTrades.ts_close)
        )
        trades = result.scalars().all()
        
        if not trades:
            print('No trades found')
            return
        
        # Calculate metrics
        total = len(trades)
        wins = sum(1 for t in trades if t.profit and t.profit > 0)
        losses = total - wins
        win_rate = (wins / total) * 100
        
        gross_profit = sum(t.profit for t in trades if t.profit > 0)
        gross_loss = abs(sum(t.profit for t in trades if t.profit < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        net_profit = gross_profit - gross_loss
        
        print(f'=== DEMO PERFORMANCE ANALYSIS ===')
        print(f'Total Trades: {total}')
        print(f'Win Rate: {win_rate:.2f}%')
        print(f'Profit Factor: {profit_factor:.2f}')
        print(f'Net Profit: \${net_profit:.2f}')
        print(f'Gross Profit: \${gross_profit:.2f}')
        print(f'Gross Loss: \${gross_loss:.2f}')
        
        # Check if meets criteria
        print(f'\\n=== CRITERIA CHECK ===')
        print(f'✅ Net Profit ≥ \$100: {\"PASS\" if net_profit >= 100 else \"FAIL\"}')
        print(f'✅ Win Rate ≥ 55%: {\"PASS\" if win_rate >= 55 else \"FAIL\"}')
        print(f'✅ Profit Factor ≥ 1.5: {\"PASS\" if profit_factor >= 1.5 else \"FAIL\"}')
        print(f'✅ Total Trades ≥ 30: {\"PASS\" if total >= 30 else \"FAIL\"}')

asyncio.run(analyze())
"
```

### Step 3.4: Go/No-Go Decision

**GO Criteria (ALL must be TRUE):**
- ✅ Cumulative profit ≥ $100
- ✅ Win rate ≥ 55%
- ✅ Profit factor ≥ 1.5
- ✅ Max drawdown ≤ 5%
- ✅ Total trades ≥ 30
- ✅ No critical system failures
- ✅ Telegram alerts working
- ✅ Database integrity verified

**Decision:**
- [ ] **GO** - Proceed to Phase 4 (Live Trading)
- [ ] **NO-GO** - Continue demo trading until all criteria met

---

## 🎯 PHASE 4: LIVE TRADING AUTHORIZATION (After $100 Demo Profit)

### Step 4.1: Fund Live Account

**Action Required:**
1. Log into Bybit.com (NOT demo mode)
2. Deposit minimum $100 USDT to futures account
3. Generate LIVE API keys:
   - Account → API Management
   - Create new key with Read + Trade permissions
   - **DO NOT enable withdrawal**
   - Whitelist IP if using VPS
4. Save API Key and Secret securely

### Step 4.2: Switch Configuration to Live

**Update `.env` file:**

```bash
# CRITICAL CHANGES FOR LIVE TRADING

# Line 80: Switch to live domain
BYBIT_USE_DEMO_DOMAIN=false             # Was: true

# Lines 70-71: Use live API keys
BYBIT_API_KEY=YOUR_LIVE_KEY_HERE        # Replace with actual live key
BYBIT_API_SECRET=YOUR_LIVE_SECRET_HERE  # Replace with actual live secret

# Keep demo keys commented for reference
# BYBIT_DEMO_API_KEY="EJswnKqH..."
# BYBIT_DEMO_API_SECRET="Yzfufhz4..."

# Line 132: Already set
ACTIVE_EXCHANGE=bybit                   # ✅ Correct

# Line 94: Keep conservative
EXECUTION_MODE=semi-auto                # ✅ Safe for start

# Lines 141-143: Keep elite parameters
GOLD_MAX_LEVERAGE=3                     # ✅ Conservative
GOLD_RISK_PER_TRADE=0.005               # ✅ 0.5% risk
GOLD_MIN_CONFIDENCE=0.75                # ✅ Elite threshold
```

### Step 4.3: Verify Live API Connection

```bash
python scripts/verify_bybit_live_api.py
```

**Expected Output:**
```
✅ USDT Balance: [your actual balance]
✅ No open positions
✅ API permissions verified
✅ Ready for live trading
```

### Step 4.4: First Live Trade Protocol

**Conservative Start:**
- [ ] Execute first trade with 0.25% risk ($0.25 on $100) - HALF normal size
- [ ] Monitor entry execution closely
- [ ] Verify SL/TP levels set correctly
- [ ] Confirm Telegram alert received
- [ ] Watch position via dashboard
- [ ] Document everything in journal

**If First Trade Successful:**
- Increase to normal 0.5% risk on second trade
- Continue monitoring closely for first week

**If First Trade Has Issues:**
- Stop immediately
- Debug problem
- Return to demo if needed

### Step 4.5: Live Trading Monitoring Plan

**Daily Checks:**
- [ ] Review all Telegram alerts
- [ ] Verify account balance
- [ ] Check open positions
- [ ] Review daily P/L
- [ ] Monitor for errors
- [ ] Update trading journal

**Weekly Reviews:**
- [ ] Analyze win rate vs. demo performance
- [ ] Compare profit factor
- [ ] Review drawdown levels
- [ ] Assess slippage impact
- [ ] Adjust parameters if needed
- [ ] Withdraw profits if threshold met

**Monthly Assessments:**
- [ ] Full performance review
- [ ] Compare live vs. demo results
- [ ] Evaluate risk management
- [ ] Consider scaling position sizes
- [ ] Track progress toward goals

---

## 📊 SUCCESS METRICS TRACKING

### Demo Phase Progress Tracker

**Copy this template and update daily:**

```
=== GOLD BOT V2 ELITE - DEMO PROGRESS ===

Date Started: ___________
Starting Balance: $100.00

Week 1:
  Day 1: Balance $_____ | P/L $_____ | Cumulative $_____
  Day 2: Balance $_____ | P/L $_____ | Cumulative $_____
  Day 3: Balance $_____ | P/L $_____ | Cumulative $_____
  Day 4: Balance $_____ | P/L $_____ | Cumulative $_____
  Day 5: Balance $_____ | P/L $_____ | Cumulative $_____
  Week Total: $_____

Week 2:
  ...

CONTINUE UNTIL CUMULATIVE PROFIT REACHES $100

Final Stats:
  Total Days: _____
  Total Trades: _____
  Final Balance: $_____
  Cumulative Profit: $_____
  Win Rate: _____%
  Profit Factor: _____
  Max Drawdown: _____%
```

### Live Phase Targets (Post-$100 Demo Achievement)

**Conservative Goals:**
- Month 1: +3-5% ($3-5 on $100)
- Month 2: +5-8% ($5-8 on $100)
- Month 3: +8-12% ($8-12 on $100)

**Withdrawal Strategy:**
- At $50 profit: Withdraw 50%, reinvest 50%
- At $100 profit: Withdraw 70%, reinvest 30%
- Monthly: Review and adjust

---

## ⚠️ CRITICAL SAFETY RULES

### Red Flags - STOP Trading Immediately If:

- ❌ Daily drawdown reaches 2%
- ❌ 2 consecutive losses occur
- ❌ API errors persist > 5 minutes
- ❌ Telegram alerts stop working
- ❌ Position sizing behaves unexpectedly
- ❌ Slippage exceeds 0.2% consistently
- ❌ Major news event announced unexpectedly
- ❌ Cumulative profit drops below $0 in demo

### Emergency Procedures

**If System Malfunctions:**
1. Stop all trading immediately
2. Close any open positions manually via Bybit interface
3. Check logs for error messages
4. Contact support if needed
5. Do NOT restart until issue identified

**If Daily DD Limit Hit:**
1. System should auto-pause
2. Verify no new trades executing
3. Review what caused losses
4. Wait until next trading day
5. Resume with caution

**If Live Trading Shows Problems:**
1. Switch back to demo mode immediately
2. Set `BYBIT_USE_DEMO_DOMAIN=true`
3. Debug issues in safe environment
4. Only return to live after fixing
5. Start with smaller position sizes

---

## 📝 FINAL AUTHORIZATION CHECKLIST

### Before Going Live - Final Verification

**Demo Performance:**
- [ ] Cumulative profit ≥ $100 ✅
- [ ] Win rate ≥ 55% ✅
- [ ] Profit factor ≥ 1.5 ✅
- [ ] Max drawdown ≤ 5% ✅
- [ ] Total trades ≥ 30 ✅
- [ ] R:R ratio ≥ 1.5:1 ✅

**Technical Readiness:**
- [ ] Live API keys generated ✅
- [ ] Live account funded ($100+) ✅
- [ ] Telegram alerts tested ✅
- [ ] Database backup completed ✅
- [ ] Emergency procedures documented ✅

**Configuration:**
- [ ] `.env` updated for live mode ✅
- [ ] `BYBIT_USE_DEMO_DOMAIN=false` ✅
- [ ] Live API keys configured ✅
- [ ] Risk parameters verified ✅
- [ ] Application restarted ✅

**Mental Preparation:**
- [ ] Understand risks involved ✅
- [ ] Accept potential losses ✅
- [ ] Committed to discipline ✅
- [ ] Emergency plan memorized ✅
- [ ] Journal template ready ✅

### Trader Declaration

I, _________________________, hereby confirm:

- [ ] I have achieved $100 profit in Bybit Demo
- [ ] All success criteria have been met
- [ ] I understand live trading involves real financial risk
- [ ] I am using only capital I can afford to lose
- [ ] I will follow all safety rules and risk limits
- [ ] I will monitor trades daily and maintain journal
- [ ] I accept full responsibility for trading decisions
- [ ] I will stop trading if red flags appear

**Signature**: _________________________  
**Date**: ___________  
**Time**: ___________

**Authorization**: [ ] **APPROVED FOR LIVE TRADING** | [ ] **DENIED - CONTINUE DEMO**

---

## 🔄 POST-LAUNCH REVIEW SCHEDULE

**Week 1 (Live):**
- Daily reviews, manual oversight of ALL trades
- Verify live execution matches demo performance
- Monitor slippage and fill quality
- Check Telegram alert accuracy

**Week 2-4 (Live):**
- Every-other-day reviews
- Compare live vs. demo metrics
- Assess consistency
- Adjust if significant deviations

**Month 2 (Live):**
- Weekly reviews
- Consider increasing position size to 0.7% if win rate >60%
- Evaluate self-learning adjustments
- Track monthly return vs. target (3-8%)

**Month 3 (Live):**
- Full monthly assessment
- Decide on scaling strategy
- Implement withdrawal plan if profitable
- Document lessons learned
- Consider Version 3 Institutional upgrade

---

*Document Version: 2.0 (Revised for $100 Demo Gate)*  
*Created: May 13, 2026*  
*Strategy: Gold Bot V2 Elite (95% Pro Level)*  
*Next Review: When demo profit reaches $25, $50, $75, $100*  

---

**REMEMBER**: The $100 demo profit is your ticket to live trading. Without it, you're gambling, not trading. Prove your edge first, then scale with confidence.

**Discipline > Emotion. Consistency > Aggression. Capital Preservation > Quick Profits.**

**Good luck, trader! 🎯💰**
