# MEXC Live Trading - Go/No-Go Checklist

## Overview

This document defines the comprehensive criteria for transitioning from **paper trading on Binance Testnet** to **live trading with real funds on MEXC**. 

**⚠️ CRITICAL WARNING**: Never skip validation steps. Real money is at risk.

---

## 📊 Phase 1: Paper Trading Validation (Binance Testnet)

### 1.1 Minimum Trading Volume

**Criteria**: Complete at least **50 successful paper trades** before considering live trading.

**Rationale**: 
- Statistical significance for performance metrics
- Exposure to various market conditions
- Validates strategy across different regimes

**Verification Command**:
```bash
python -c "
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
import asyncio
from sqlalchemy import select

async def check():
    async with async_session_maker() as db:
        result = await db.execute(select(PaperTrades))
        trades = result.scalars().all()
        print(f'Total Paper Trades: {len(trades)}')
        
        # Count by status
        open_trades = sum(1 for t in trades if t.status == 'open')
        closed_trades = sum(1 for t in trades if t.status == 'closed')
        print(f'Open Trades: {open_trades}')
        print(f'Closed Trades: {closed_trades}')
        
        if closed_trades >= 50:
            print('✅ PASS: Minimum trade volume achieved')
        else:
            print(f'❌ FAIL: Need {50 - closed_trades} more closed trades')

asyncio.run(check())
"
```

**Status**: [ ] PASS | [ ] FAIL  
**Current Count**: _____ / 50  
**Date Achieved**: ___________

---

### 1.2 Win Rate Threshold

**Criteria**: Maintain a **win rate ≥ 55%** over the last 50 trades.

**Rationale**:
- Ensures strategy has positive expectancy
- Accounts for transaction costs and slippage
- Provides buffer for live trading variance

**Calculation**:
```
Win Rate = (Winning Trades / Total Closed Trades) × 100
```

**Verification Command**:
```bash
python -c "
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
import asyncio
from sqlalchemy import select

async def check():
    async with async_session_maker() as db:
        result = await db.execute(
            select(PaperTrades)
            .where(PaperTrades.status == 'closed')
            .order_by(PaperTrades.ts_close.desc())
            .limit(50)
        )
        trades = result.scalars().all()
        
        if len(trades) < 10:
            print('⚠️  Insufficient data (need at least 10 closed trades)')
            return
        
        wins = sum(1 for t in trades if t.profit and t.profit > 0)
        win_rate = (wins / len(trades)) * 100
        
        print(f'Last {len(trades)} Trades:')
        print(f'  Wins: {wins}')
        print(f'  Losses: {len(trades) - wins}')
        print(f'  Win Rate: {win_rate:.2f}%')
        
        if win_rate >= 55:
            print('✅ PASS: Win rate meets threshold (≥55%)')
        else:
            print(f'❌ FAIL: Win rate {win_rate:.2f}% below 55% threshold')

asyncio.run(check())
"
```

**Status**: [ ] PASS | [ ] FAIL  
**Current Win Rate**: _____%  
**Target**: ≥ 55%

---

### 1.3 Profit Factor

**Criteria**: Achieve a **profit factor ≥ 1.5** over the validation period.

**Rationale**:
- Measures risk-adjusted returns
- Profit Factor = Gross Profit / Gross Loss
- Values > 1.0 indicate profitability
- Target of 1.5 provides safety margin

**Calculation**:
```
Profit Factor = Sum(Profits from Winning Trades) / Sum(Losses from Losing Trades)
```

**Verification Command**:
```bash
python -c "
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
import asyncio
from sqlalchemy import select

async def check():
    async with async_session_maker() as db:
        result = await db.execute(
            select(PaperTrades).where(PaperTrades.status == 'closed')
        )
        trades = result.scalars().all()
        
        if not trades:
            print('⚠️  No closed trades yet')
            return
        
        gross_profit = sum(t.profit for t in trades if t.profit and t.profit > 0)
        gross_loss = abs(sum(t.profit for t in trades if t.profit and t.profit < 0))
        
        if gross_loss == 0:
            profit_factor = float('inf')
        else:
            profit_factor = gross_profit / gross_loss
        
        print(f'Performance Metrics:')
        print(f'  Gross Profit: \${gross_profit:.2f}')
        print(f'  Gross Loss: \${gross_loss:.2f}')
        print(f'  Net P&L: \${gross_profit - gross_loss:.2f}')
        print(f'  Profit Factor: {profit_factor:.2f}')
        
        if profit_factor >= 1.5:
            print('✅ PASS: Profit factor meets threshold (≥1.5)')
        else:
            print(f'❌ FAIL: Profit factor {profit_factor:.2f} below 1.5 threshold')

asyncio.run(check())
"
```

**Status**: [ ] PASS | [ ] FAIL  
**Current Profit Factor**: _____  
**Target**: ≥ 1.5

---

### 1.4 Maximum Drawdown

**Criteria**: Maintain **maximum drawdown ≤ 15%** during validation period.

**Rationale**:
- Protects capital preservation
- Indicates risk management effectiveness
- Lower drawdown = more sustainable strategy

**Calculation**:
```
Drawdown % = (Peak Balance - Current Balance) / Peak Balance × 100
```

**Verification Command**:
```bash
python -c "
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
import asyncio
from sqlalchemy import select, func

async def check():
    async with async_session_maker() as db:
        result = await db.execute(
            select(PaperTrades)
            .where(PaperTrades.status == 'closed')
            .order_by(PaperTrades.ts_close)
        )
        trades = result.scalars().all()
        
        if not trades:
            print('⚠️  No closed trades yet')
            return
        
        # Calculate cumulative P&L
        initial_balance = 100.0  # Starting balance
        balance = initial_balance
        peak_balance = initial_balance
        max_drawdown = 0.0
        
        for trade in trades:
            if trade.profit:
                balance += trade.profit
                if balance > peak_balance:
                    peak_balance = balance
                
                drawdown = (peak_balance - balance) / peak_balance * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        
        print(f'Drawdown Analysis:')
        print(f'  Initial Balance: \${initial_balance:.2f}')
        print(f'  Current Balance: \${balance:.2f}')
        print(f'  Peak Balance: \${peak_balance:.2f}')
        print(f'  Max Drawdown: {max_drawdown:.2f}%')
        
        if max_drawdown <= 15:
            print('✅ PASS: Drawdown within acceptable range (≤15%)')
        else:
            print(f'❌ FAIL: Drawdown {max_drawdown:.2f}% exceeds 15% limit')

asyncio.run(check())
"
```

**Status**: [ ] PASS | [ ] FAIL  
**Current Max Drawdown**: _____%  
**Limit**: ≤ 15%

---

### 1.5 Average Risk-Reward Ratio

**Criteria**: Maintain **average risk-reward ratio ≥ 1.5:1**.

**Rationale**:
- Ensures winners are larger than losers
- Compensates for imperfect win rates
- Critical for long-term profitability

**Verification Command**:
```bash
python -c "
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
import asyncio
from sqlalchemy import select

async def check():
    async with async_session_maker() as db:
        result = await db.execute(
            select(PaperTrades).where(PaperTrades.status == 'closed')
        )
        trades = result.scalars().all()
        
        if not trades:
            print('⚠️  No closed trades yet')
            return
        
        # Calculate average risk-reward
        total_risk = 0
        total_reward = 0
        count = 0
        
        for trade in trades:
            if trade.entry_price and trade.stop_loss and trade.profit:
                risk = abs(trade.entry_price - trade.stop_loss)
                if trade.side == 'LONG':
                    reward = trade.profit / trade.qty if trade.qty else 0
                else:
                    reward = abs(trade.profit / trade.qty) if trade.qty else 0
                
                if risk > 0:
                    total_risk += risk
                    total_reward += reward
                    count += 1
        
        if count > 0:
            avg_rr = total_reward / total_risk
            print(f'Risk-Reward Analysis:')
            print(f'  Average Risk: \${total_risk/count:.2f}')
            print(f'  Average Reward: \${total_reward/count:.2f}')
            print(f'  Risk-Reward Ratio: {avg_rr:.2f}:1')
            
            if avg_rr >= 1.5:
                print('✅ PASS: Risk-reward ratio meets threshold (≥1.5:1)')
            else:
                print(f'❌ FAIL: Risk-reward ratio {avg_rr:.2f}:1 below 1.5:1 threshold')
        else:
            print('⚠️  Insufficient data for risk-reward calculation')

asyncio.run(check())
"
```

**Status**: [ ] PASS | [ ] FAIL  
**Current R:R Ratio**: _____:1  
**Target**: ≥ 1.5:1

---

## 🔧 Phase 2: Technical Infrastructure Verification

### 2.1 MEXC API Connectivity

**Criteria**: Successfully connect to MEXC API and retrieve account information.

**Steps**:
1. Generate MEXC API keys (Spot + Futures)
2. Enable required permissions (Read, Trade)
3. Whitelist IP addresses if using VPS
4. Test connectivity

**Verification Command**:
```bash
python -c "
import asyncio
from app.infra.mexc_client import MEXCClient

async def test():
    client = MEXCClient(
        api_key='YOUR_MEXC_API_KEY',
        api_secret='YOUR_MEXC_API_SECRET',
        market_type='futures'  # or 'spot'
    )
    
    try:
        # Test connection
        balance = await client.fetch_balance()
        print('✅ MEXC API Connection: SUCCESS')
        print(f'   Account Balance: {balance}')
        
        # Test ticker fetch
        ticker = await client.fetch_ticker('BTC/USDT')
        print(f'✅ Market Data Fetch: SUCCESS')
        print(f'   BTC/USDT Price: \${ticker[\"last_price\"]}')
        
        await client.close()
        
    except Exception as e:
        print(f'❌ MEXC API Connection: FAILED')
        print(f'   Error: {e}')

asyncio.run(test())
"
```

**Status**: [ ] PASS | [ ] FAIL  
**API Keys Configured**: [ ] Yes [ ] No  
**IP Whitelisted**: [ ] Yes [ ] No [ ] N/A  
**Test Date**: ___________

---

### 2.2 MEXC Fee Structure Verification

**Criteria**: Understand and account for MEXC trading fees in strategy calculations.

**MEXC Fee Schedule** (Verify current rates):
- **Spot Trading**: 
  - Maker: 0.1%
  - Taker: 0.1%
- **Futures Trading**:
  - Maker: 0.02%
  - Taker: 0.06%

**Impact Analysis**:
```
For \$100 position:
- Spot fee (taker): \$0.10 per trade
- Futures fee (taker): \$0.06 per trade
- Round-trip cost: 2× fee amount
```

**Verification Steps**:
1. Check current fee schedule on MEXC website
2. Confirm fee tier based on trading volume
3. Update strategy to account for fees
4. Verify fees in test trades

**Status**: [ ] PASS | [ ] FAIL  
**Fee Tier**: ___________  
**Effective Fee Rate**: _____%  
**Verified On**: ___________

---

### 2.3 Telegram Alert System

**Criteria**: Receive timely and accurate Telegram notifications for all trade events.

**Test Checklist**:
- [ ] Trade proposal notifications received
- [ ] Order execution confirmations received
- [ ] Position closure alerts with P&L received
- [ ] Error/warning notifications functional
- [ ] Message formatting correct and readable

**Verification Command**:
```bash
python -c "
import asyncio
from app.infra.telegram_notifier import TelegramNotifier

async def test():
    notifier = TelegramNotifier()
    
    # Test basic message
    success = await notifier.send_message(
        '🧪 MEXC Live Trading Test\\n\\nSystem validation in progress.'
    )
    
    if success:
        print('✅ Telegram Notifications: WORKING')
        print('   Check your Telegram for test message')
    else:
        print('❌ Telegram Notifications: FAILED')
        print('   Verify BOT_TOKEN and CHAT_ID in .env')

asyncio.run(test())
"
```

**Status**: [ ] PASS | [ ] FAIL  
**Bot Token Valid**: [ ] Yes [ ] No  
**Chat ID Correct**: [ ] Yes [ ] No  
**Test Message Received**: [ ] Yes [ ] No

---

### 2.4 Database Persistence Reliability

**Criteria**: All trade events persist correctly to database with no data loss.

**Verification Steps**:
1. Execute 10 test trades on testnet
2. Verify all records in database
3. Check data integrity (no NULL values in critical fields)
4. Confirm timestamps are accurate
5. Validate P&L calculations

**Verification Command**:
```bash
python -c "
import asyncio
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades, DecisionJournal, TradeProposals
from sqlalchemy import select

async def check():
    async with async_session_maker() as db:
        # Check PaperTrades
        result = await db.execute(select(PaperTrades))
        trades = result.scalars().all()
        
        # Check for data integrity issues
        issues = []
        for trade in trades[-10:]:  # Last 10 trades
            if not trade.symbol:
                issues.append(f'Trade {trade.id}: Missing symbol')
            if not trade.entry_price:
                issues.append(f'Trade {trade.id}: Missing entry price')
            if trade.status == 'closed' and not trade.exit_price:
                issues.append(f'Trade {trade.id}: Missing exit price')
        
        print(f'Database Integrity Check:')
        print(f'  Total Trades: {len(trades)}')
        print(f'  Recent Trades Checked: 10')
        
        if not issues:
            print('✅ Database Persistence: RELIABLE')
            print('   All critical fields populated')
        else:
            print('❌ Database Persistence: ISSUES FOUND')
            for issue in issues:
                print(f'   - {issue}')

asyncio.run(check())
"
```

**Status**: [ ] PASS | [ ] FAIL  
**Data Integrity**: [ ] Verified [ ] Issues Found  
**Last Check**: ___________

---

### 2.5 Circuit Breaker & Safety Mechanisms

**Criteria**: All safety mechanisms functional and tested.

**Safety Features to Verify**:
- [ ] Daily drawdown limit stops trading
- [ ] Loss streak protection activates correctly
- [ ] Circuit breaker pauses on consecutive failures
- [ ] Manual pause/resume works via API
- [ ] Emergency stop functionality tested

**Verification Command**:
```bash
python -c "
from app.ai.optimized_agents import DeterministicRiskManager

# Test safety mechanisms
risk_mgr = DeterministicRiskManager(
    max_risk_per_trade=0.01,
    max_daily_drawdown=0.05,
    max_loss_streak=3,
    account_balance=100
)

print('Safety Mechanism Tests:')
print('-' * 60)

# Test loss streak protection
for i in range(3):
    risk_mgr.update_after_trade(profit=-1.0, won=False)

check = risk_mgr.should_stop_trading()
if check['should_stop']:
    print('✅ Loss Streak Protection: WORKING')
    print(f'   Stopped after {check[\"loss_streak\"]} consecutive losses')
else:
    print('❌ Loss Streak Protection: FAILED')

# Test daily drawdown
risk_mgr.daily_pnl = -6.0  # 6% drawdown on \$100
check = risk_mgr.should_stop_trading()
if check['should_stop']:
    print('✅ Daily Drawdown Limit: WORKING')
    print(f'   Stopped at {check[\"daily_pnl\"]} drawdown')
else:
    print('❌ Daily Drawdown Limit: FAILED')
"
```

**Status**: [ ] PASS | [ ] FAIL  
**All Safeties Tested**: [ ] Yes [ ] No  
**Test Date**: ___________

---

## 💰 Phase 3: Financial Readiness

### 3.1 Capital Allocation

**Criteria**: Determine and allocate appropriate capital for live trading.

**Recommendations**:
- **Starting Capital**: \$100-\$500 (low-risk validation)
- **Risk Per Trade**: 1% of account balance
- **Maximum Daily Loss**: 5% of account balance
- **Never risk more than you can afford to lose**

**Capital Planning Worksheet**:
```
Initial Capital: \$_______
Risk Per Trade (1%): \$_______
Max Daily Loss (5%): \$_______
Emergency Reserve: \$_______
Total Allocated: \$_______
```

**Status**: [ ] PASS | [ ] FAIL  
**Capital Allocated**: \$_______  
**Source of Funds**: ___________

---

### 3.2 Withdrawal Strategy

**Criteria**: Define clear profit withdrawal rules.

**Recommended Strategy**:
- Withdraw 50% of profits monthly
- Keep 50% compounding in account
- Reassess after 3 months

**Withdrawal Plan**:
```
Profit Threshold for Withdrawal: \$_______
Withdrawal Frequency: [ ] Weekly [ ] Monthly [ ] Quarterly
Withdrawal Percentage: _____%
Reinvestment Percentage: _____%
```

**Status**: [ ] DEFINED | [ ] NOT DEFINED

---

## 📋 Phase 4: Final Pre-Launch Checklist

### 4.1 Configuration Review

**Verify .env Settings**:
```bash
# Switch to MEXC
ACTIVE_EXCHANGE=mexc
BINANCE_TESTNET=false  # Not applicable for MEXC

# MEXC API Keys (REAL KEYS FOR LIVE TRADING)
MEXC_API_KEY=your_real_api_key_here
MEXC_API_SECRET=your_real_api_secret_here

# Execution Mode (start conservative)
EXECUTION_MODE=semi-auto
AUTO_EXECUTE_THRESHOLD_USD=50.0  # Lower threshold for live trading

# Safety First
APP_ENV=production
LOG_LEVEL=INFO
```

**Configuration Checklist**:
- [ ] ACTIVE_EXCHANGE set to 'mexc'
- [ ] MEXC API keys configured (real keys)
- [ ] EXECUTION_MODE set to 'semi-auto' (recommended)
- [ ] AUTO_EXECUTE_THRESHOLD_USD adjusted appropriately
- [ ] Telegram bot token verified
- [ ] Database path confirmed

**Status**: [ ] COMPLETE | [ ] INCOMPLETE

---

### 4.2 Dry Run on MEXC Testnet (If Available)

**Criteria**: Execute at least 10 trades on MEXC test environment before live trading.

**Note**: MEXC may not have a public testnet. If unavailable, proceed with extreme caution using minimal capital.

**Alternative Approach**:
1. Start with minimum position sizes
2. Use semi-auto mode for all trades initially
3. Monitor every trade manually for first week
4. Gradually increase automation as confidence grows

**Status**: [ ] COMPLETED | [ ] SKIPPED (No Testnet) | [ ] NOT APPLICABLE  
**Dry Run Trades**: _____ / 10  
**Results**: ___________

---

### 4.3 Monitoring Plan

**Criteria**: Establish monitoring routine for live trading.

**Daily Checks**:
- [ ] Review Telegram notifications
- [ ] Check account balance
- [ ] Verify open positions
- [ ] Review P&L for the day
- [ ] Check for any error messages

**Weekly Reviews**:
- [ ] Analyze win rate and profit factor
- [ ] Review drawdown levels
- [ ] Assess strategy performance
- [ ] Adjust parameters if needed
- [ ] Withdraw profits if threshold met

**Monthly Assessments**:
- [ ] Comprehensive performance review
- [ ] Compare vs. paper trading results
- [ ] Evaluate risk management effectiveness
- [ ] Consider scaling up or down
- [ ] Update strategy based on learnings

**Status**: [ ] PLAN ESTABLISHED | [ ] NOT YET

---

## 🎯 GO/NO-GO Decision Matrix

### Scoring System

Rate each criterion:
- ✅ **PASS** (2 points): Meets or exceeds threshold
- ⚠️ **PARTIAL** (1 point): Close but needs improvement
- ❌ **FAIL** (0 points): Does not meet minimum requirement

### Minimum Requirements

**You MUST have ALL of the following to proceed**:
1. ✅ At least 50 completed paper trades
2. ✅ Win rate ≥ 55%
3. ✅ Profit factor ≥ 1.5
4. ✅ Maximum drawdown ≤ 15%
5. ✅ MEXC API connectivity verified
6. ✅ Telegram alerts working
7. ✅ Database persistence reliable
8. ✅ All safety mechanisms tested

### Decision Thresholds

**Total Score Required**: 
- **Minimum**: 16/16 points (ALL criteria must pass)
- **Recommended**: Wait until all criteria pass

**GO Decision**: All 8 critical criteria PASS ✅  
**NO-GO Decision**: Any critical criterion FAILS ❌

---

## 📝 Final Authorization

### Trader Declaration

I, _________________________, hereby confirm that:

- [ ] I have completed all validation steps above
- [ ] I understand the risks involved in live trading
- [ ] I am using only capital I can afford to lose
- [ ] I have established proper risk management
- [ ] I will monitor trades regularly
- [ ] I will withdraw profits according to my plan
- [ ] I accept full responsibility for trading decisions

**Signature**: _________________________  
**Date**: ___________

### System Readiness Confirmation

**Paper Trading Performance**:
- Total Trades: _____
- Win Rate: _____%
- Profit Factor: _____
- Max Drawdown: _____%
- Validation Period: _____ days

**Technical Verification**:
- MEXC API: [ ] Connected [ ] Failed
- Telegram: [ ] Working [ ] Failed
- Database: [ ] Reliable [ ] Issues
- Safety Systems: [ ] Tested [ ] Not Tested

**Final Decision**: [ ] **GO** - Proceed to Live Trading | [ ] **NO-GO** - Continue Validation

**Authorized By**: _________________________  
**Date**: ___________  
**Time**: ___________

---

## ⚠️ Important Reminders

1. **Start Small**: Begin with minimum position sizes
2. **Monitor Closely**: Watch every trade for the first week
3. **Stay Conservative**: Use semi-auto mode initially
4. **Withdraw Profits**: Don't let greed override discipline
5. **Keep Learning**: Continuously improve based on results
6. **Emergency Plan**: Know how to stop immediately if needed
7. **Document Everything**: Keep detailed trading journal
8. **Never Risk More Than 1% Per Trade**: Preserve capital

---

## 🔄 Post-Launch Review Schedule

**Week 1**: Daily reviews, manual oversight of all trades  
**Week 2-4**: Every other day reviews, assess consistency  
**Month 2**: Weekly reviews, consider gradual automation increase  
**Month 3**: Full monthly assessment, decide on scaling

---

*Document Version: 1.0*  
*Last Updated: May 11, 2026*  
*Next Review: After first 50 live trades*
