# Bybit Demo Trading - Quick Reference Guide

## 🎯 Objective
Achieve **$100 cumulative profit** on Bybit Demo Trading using Gold (XAU/USDT:USDT) perpetual swaps.

---

## ✅ Current Status (as of 2026-05-13)

| Metric | Value |
|--------|-------|
| Starting Balance | $49,997.72 (actual demo balance verified via API) |
| Current Balance | $49,997.72 |
| Target Profit Goal | $100.00 (0.2% return) |
| Cumulative Profit | $0.00 |
| Progress to Goal | 0% |
| Active Exchange | Bybit Demo |
| MEXC Status | ❌ Disabled |

---

## 🚀 Quick Commands

### 1. Check Account Balance & Progress
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python scripts/check_bybit_demo_balance.py
```

### 2. Execute Validation Cycle
```bash
python scripts/cleanup_and_restart_bybit_demo_cycle.py
```

### 3. Monitor System Logs
```bash
# View recent validation cycle log
tail -f bybit_validation_cycle.log

# Check application logs (if running)
tail -f app.log
```

### 4. Verify Configuration
```bash
# Check active exchange
grep ACTIVE_EXCHANGE app/config.py

# Verify Bybit demo settings
grep BYBIT_USE_DEMO_DOMAIN .env
grep BYBIT_DEMO_API_KEY .env
```

### 5. Confirm No MEXC Activity
```bash
ps aux | grep -E "(mexc|MEXC)" | grep -v grep
# Should return: (no output)
```

---

## 📊 Understanding Results

### Trade Executed ✅
```
✅ New Trade Executed
Regime: TRENDING
Strategy: London Breakout
Confidence: 78.50%
Side: LONG
Entry Price: $4,695.20
Stop Loss: $4,680.00
Take Profit: $4,725.00
Leverage: 3x
Status: EXECUTED ✅
```
**Action**: Monitor Telegram for close notification. Track P&L in database.

### Trade Rejected ⚠️
```
⚠️ Trade rejected by quality filter
Quality Score: 65/100
Reason: Quality score below threshold
This is normal - system protecting capital from low-quality trades
```
**Action**: This is GOOD. System prevented a risky trade. Run another cycle later.

### Cycle Failed ❌
```
❌ Validation Cycle Failed
Error: [error message]
```
**Action**: Check error details. Verify API connectivity. Retry after fixing issue.

---

## 🎯 Path to $100 Goal

### Expected Performance
- **Starting balance**: $49,997.72 (actual Bybit Demo account)
- **Risk per trade**: 0.5% ($249.99 on $49,997.72 balance)
- **Target profit per trade**: 0.75% - 1.5% ($375 - $750)
- **Win rate target**: 60%+
- **Target profit**: $100 (0.2% return on starting balance)
- **Estimated trades needed**: 1-5 trades (depending on position size)

### Milestones
```
$0    → Start (0% of $100 goal)
$25   → 25% complete (~1-2 trades)
$50   → 50% complete (~2-3 trades)
$75   → 75% complete (~3-4 trades)
$100  → GOAL ACHIEVED! (~4-5 trades)
```

**Note**: With $49,997.72 starting balance, each trade at 0.5% risk = $249.99 position size.
A single winning trade at 2R could potentially achieve the entire $100 goal.

### Timeline Estimate
- **Conservative**: 1 trade every 2 hours = 8-10 trades/day
- **At 8 trades/day**: 1-2 days to reach goal (with proper position sizing)
- **Realistic**: 3-7 days accounting for quality filter rejections and market conditions
- **Note**: Only need $100 profit from $49,997.72 (0.2% return), not 100% return

---

## 🔍 Monitoring Checklist

### Daily Checks
- [ ] Run `check_bybit_demo_balance.py` to track progress
- [ ] Review Telegram notifications for trade updates
- [ ] Verify no MEXC errors in logs
- [ ] Check system health (PostgreSQL, Redis running)

### Weekly Reviews
- [ ] Calculate win rate and profit factor
- [ ] Review max drawdown (should be < 15%)
- [ ] Analyze rejection patterns (quality scores)
- [ ] Adjust strategy if needed (consult AI agent logs)

### Before Each Cycle
- [ ] Verify `ACTIVE_EXCHANGE = "bybit"` in config
- [ ] Confirm `BYBIT_USE_DEMO_DOMAIN = true` in .env
- [ ] Check no open positions remain
- [ ] Ensure Telegram bot is responsive

---

## ⚙️ Configuration Reference

### Critical Settings (`app/config.py`)
```python
ACTIVE_EXCHANGE = "bybit"              # Must be 'bybit'
EXECUTION_MODE = "fully-auto"          # Automated trading
GOLD_SYMBOL_BYBIT = "XAU/USDT:USDT"   # Gold perpetual swap
GOLD_RISK_PER_TRADE = 0.005            # 0.5% risk per trade
GOLD_MAX_LEVERAGE = 3                  # Max 3x leverage
```

### Environment Variables (`.env`)
```bash
BYBIT_DEMO_API_KEY="your_demo_key"
BYBIT_DEMO_API_SECRET="your_demo_secret"
BYBIT_USE_DEMO_DOMAIN=true             # Use api-demo.bybit.com
```

### Risk Limits
- **Daily Loss Limit**: 3.0% ($3.00 on $100)
- **Max Drawdown**: 15.0% ($15.00)
- **Max Position Size**: 1.5% ($1.50)
- **Quality Threshold**: 70/100 (minimum score for execution)

---

## 🛠️ Troubleshooting

### Problem: "WEBSOCKET CIRCUIT BREAKER ACTIVATED"
**Cause**: MEXC WebSocket still trying to connect  
**Solution**: 
```bash
# Verify configuration
grep ACTIVE_EXCHANGE app/config.py  # Should show 'bybit'

# Clear cache
find . -type d -name __pycache__ -exec rm -rf {} +

# Restart application
./start_services.sh
```

### Problem: Trades Always Rejected
**Cause**: Market conditions don't meet quality thresholds  
**Solution**:
- This is normal during low volatility periods
- Wait for better market conditions (London/New York session overlap)
- Do NOT lower quality threshold (protects capital)

### Problem: Bybit Connection Failed
**Cause**: API credentials or network issue  
**Solution**:
```bash
# Test connectivity
python scripts/test_bybit_demo_api_quick.py

# Verify credentials
grep BYBIT_DEMO_API_KEY .env

# Check network
curl -I https://api-demo.bybit.com
```

### Problem: Database Connection Error
**Cause**: PostgreSQL not running  
**Solution**:
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Start if stopped
sudo systemctl start postgresql

# Verify connection
psql -U trading -d vmassit -c "SELECT 1;"
```

### Problem: Telegram Notifications Not Working
**Cause**: Bot token or chat ID misconfigured  
**Solution**:
```bash
# Check .env settings
grep TELEGRAM_BOT_TOKEN .env
grep TELEGRAM_CHAT_ID .env

# Test notifier
python test_notifier_singleton.py
```

---

## 📈 Performance Metrics to Track

### Key Indicators
1. **Win Rate**: % of profitable trades (target: > 55%)
2. **Profit Factor**: Gross profit / Gross loss (target: > 1.5)
3. **Average Win**: Mean profit on winning trades
4. **Average Loss**: Mean loss on losing trades
5. **Max Drawdown**: Largest peak-to-trough decline (limit: < 15%)
6. **Sharpe Ratio**: Risk-adjusted returns (target: > 1.0)
7. **Quality Score Average**: Mean AI confidence (target: > 75)

### Red Flags 🚩
- Win rate < 45% over 20+ trades
- Max drawdown > 15%
- 3+ consecutive losses
- Quality scores consistently < 65
- Circuit breaker activation

If you see red flags:
1. Pause trading cycles
2. Review recent trades in database
3. Analyze market regime changes
4. Consider adjusting strategy parameters
5. Consult AI agent analysis logs

---

## 🔄 Typical Workflow

### Morning Session (London Open ~8:00 UTC)
```bash
# 1. Check overnight status
python scripts/check_bybit_demo_balance.py

# 2. Execute validation cycle
python scripts/cleanup_and_restart_bybit_demo_cycle.py

# 3. Monitor Telegram for execution report
```

### Afternoon Session (New York Open ~13:00 UTC)
```bash
# Repeat morning workflow
# Best liquidity for Gold trading
```

### Evening Review (~20:00 UTC)
```bash
# Final check of the day
python scripts/check_bybit_demo_balance.py

# Review all trades executed today
# Update progress tracking spreadsheet (optional)
```

---

## 📝 Important Notes

### ✅ Do's
- ✅ Run cycles during high-liquidity sessions (London/NY overlap)
- ✅ Monitor Telegram notifications closely
- ✅ Track cumulative profit toward $100 goal
- ✅ Let quality filter reject low-score trades (protects capital)
- ✅ Be patient - quality over quantity
- ✅ Review performance metrics weekly

### ❌ Don'ts
- ❌ Don't lower quality threshold below 70
- ❌ Don't increase leverage above 3x
- ❌ Don't risk more than 0.5% per trade initially
- ❌ Don't chase losses with aggressive trading
- ❌ Don't ignore circuit breaker warnings
- ❌ Don't reactivate MEXC services

---

## 🎓 Learning Resources

### Project Documentation
- `MEXC_TO_BYBIT_MIGRATION.md` - Migration details
- `BYBIT_VALIDATION_CYCLE_REPORT_2026-05-13.md` - Latest execution report
- `README.md` - System overview
- `QUICK_REFERENCE.md` - General quick reference

### Scripts Reference
- `scripts/check_bybit_demo_balance.py` - Balance checker
- `scripts/cleanup_and_restart_bybit_demo_cycle.py` - Cycle executor
- `scripts/test_bybit_demo_api_quick.py` - API connectivity test
- `scripts/diagnose_websocket.py` - WebSocket diagnostics (MEXC - disabled)

### External Resources
- Bybit Demo Trading: https://www.bybit.com/en/trade/demo
- Bybit API Docs: https://bybit-exchange.github.io/docs/
- Gold Market Hours: London (8:00-17:00 UTC), NY (13:00-22:00 UTC)

---

## 📞 Support & Escalation

### Self-Help
1. Check this quick reference guide
2. Review detailed execution report
3. Examine logs in `bybit_validation_cycle.log`
4. Query database directly for trade details

### Common Issues
Most issues are resolved by:
- Verifying configuration settings
- Clearing Python cache
- Restarting services
- Checking API connectivity

### When to Seek Help
- Persistent connection failures (> 3 attempts)
- Unexpected database errors
- Circuit breaker activations
- Consistent trade rejections (> 10 cycles)

---

**Last Updated**: 2026-05-13 23:30 UTC  
**System Version**: 2.0.0  
**Active Exchange**: Bybit Demo Trading  
**Goal**: $100 Cumulative Profit
