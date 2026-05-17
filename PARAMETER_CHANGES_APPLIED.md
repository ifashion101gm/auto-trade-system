# Conservative Parameter Changes - Applied 2026-05-17

**Date**: 2026-05-17 22:32 UTC  
**Reason**: Performance analysis revealed weak short position performance (27% win rate vs 70% for longs)  
**Goal**: Reduce risk and improve trade quality before live trading  

---

## 📊 Changes Applied

### 1. Risk Management Parameters

| Parameter | Old Value | New Value | Change | Rationale |
|-----------|-----------|-----------|--------|-----------|
| **GOLD_MAX_LEVERAGE** | 3x | **2x** | -33% | Reduce liquidation risk, especially for underperforming shorts |
| **GOLD_RISK_PER_TRADE** | 0.5% | **0.3%** | -40% | Smaller position sizes protect capital during learning phase |
| **GOLD_MIN_CONFIDENCE** | 0.75 | **0.80** | +6.7% | Filter out weaker signals, only take high-quality trades |
| **AUTO_EXECUTE_THRESHOLD_USD** | $100 | **$50** | -50% | Require manual approval for larger positions |

### 2. Expected Impact

**Trade Frequency**: 
- Before: ~2-3 trades per day (estimated)
- After: ~1-2 trades per day (higher quality filter)
- **Reduction**: ~30-40% fewer trades

**Win Rate Projection**:
- Before: 47.6% overall (70% long, 27% short)
- After: **55-60%** expected (filtering weak shorts)

**Risk Per Trade**:
- Before: 0.5% of account × 3x leverage = 1.5% effective exposure
- After: 0.3% of account × 2x leverage = 0.6% effective exposure
- **Risk Reduction**: 60% lower per-trade risk

**Capital Protection**:
- Maximum loss per trade reduced from 1.5% to 0.6%
- Can withstand 16+ consecutive losses before 10% drawdown (vs 6+ before)
- Much safer for initial live trading phase

---

## 🔧 Configuration Changes

### File Modified: `.env`

```diff
# Risk Management for Gold (Gold Bot V2 Elite Strategy)
- GOLD_MAX_LEVERAGE=3
- GOLD_RISK_PER_TRADE=0.005
- GOLD_MIN_CONFIDENCE=0.75
+ # OPTIMIZED: Conservative settings based on performance analysis
+ # - Increased confidence threshold to filter weaker signals
+ # - Reduced leverage and risk per trade for capital protection
+ # - BUY trades: 70% win rate, SELL trades: 27% win rate
+ GOLD_MAX_LEVERAGE=2                # Reduced from 3 to 2 (safer)
+ GOLD_RISK_PER_TRADE=0.003          # Reduced from 0.5% to 0.3% per trade
+ GOLD_MIN_CONFIDENCE=0.80           # Increased from 0.75 to 0.80 (higher quality)

# Auto-Execute Threshold (USD)
- AUTO_EXECUTE_THRESHOLD_USD=100.0
+ # OPTIMIZED: Reduced from $100 to $50 for tighter control
+ AUTO_EXECUTE_THRESHOLD_USD=50.0
```

### Backup Created
```bash
.env.conservative.20260517_223259
```

---

## ✅ Verification Steps

### 1. Service Restart Required

The application reads configuration at startup, so a restart is needed:

```bash
sudo systemctl restart auto-trade-api
```

### 2. Verify New Settings Active

After restart, check that parameters loaded correctly:

```bash
# Check service status
sudo systemctl status auto-trade-api --no-pager | head -15

# Verify health endpoint responds
curl -s http://localhost:8000/health/deep | python3 -m json.tool

# Check logs for any configuration errors
tail -50 logs/uvicorn.log | grep -i "config\|error\|warning"
```

### 3. Test Paper Trading with New Params

Run a few paper trades to verify new parameters work:

```bash
# Execute test trade
.venv/bin/python scripts/execute_paper_trade.py

# Check trade details in database
sqlite3 data/vmassit.db "SELECT id, side, entry_price, qty, leverage FROM paper_trades ORDER BY id DESC LIMIT 1;"
```

Expected: Leverage should be 2x, quantity should reflect 0.3% risk

---

## 📈 Monitoring Plan

### Next 24 Hours

**Monitor these metrics**:
1. **Trade frequency**: Should decrease (fewer but higher quality trades)
2. **Win rate**: Should improve toward 55%+ target
3. **Position sizes**: Should be smaller (0.3% risk vs 0.5%)
4. **System stability**: No crashes or errors after restart

**Check every 4 hours**:
```bash
# Quick health check
curl -s http://localhost:8000/health | python3 -m json.tool

# Recent trades
sqlite3 data/vmassit.db "SELECT id, side, profit, ts_open FROM paper_trades WHERE ts_open > datetime('now', '-4 hours') ORDER BY id DESC;"

# Error log
tail -20 logs/uvicorn-error.log
```

### Success Criteria (24-Hour Test)

- [ ] System restarted without errors
- [ ] At least 3-5 trades executed (lower frequency expected)
- [ ] Win rate ≥ 55% on new trades
- [ ] No unexpected behavior or crashes
- [ ] Position sizes reduced appropriately
- [ ] Telegram notifications still working

If all criteria met → **Proceed to Stage 1 Live Testing**  
If issues found → **Troubleshoot and adjust**

---

## 🔄 Rollback Plan

If new parameters cause problems, rollback is easy:

```bash
# Stop service
sudo systemctl stop auto-trade-api

# Restore previous configuration
cp .env.backup.20260515_032926 .env

# Restart service
sudo systemctl start auto-trade-api

# Verify rollback
curl -s http://localhost:8000/health | python3 -m json.tool
```

---

## 📝 Additional Recommendations

### Optional Enhancements (Future)

1. **Asymmetric Confidence Thresholds**
   ```python
   # In strategy code (if supported)
   MIN_CONFIDENCE_LONG = 0.75   # Keep lower for strong longs
   MIN_CONFIDENCE_SHORT = 0.85  # Higher for weak shorts
   ```

2. **Short Position Limits**
   ```python
   # Limit shorts to 30% of total trades
   if side == 'sell' and short_count / total_count > 0.3:
       skip_trade()
   ```

3. **Trend Filter**
   ```python
   # Only take shorts in downtrends
   if side == 'sell' and price > MA_50:
       skip_trade()  # Don't short in uptrend
   ```

These can be implemented after validating the conservative parameters work well.

---

## 🎯 Next Steps Timeline

| Time | Action | Success Metric |
|------|--------|----------------|
| **Now** | Apply parameters & restart | Service healthy |
| **+1 hour** | Verify first trades execute | Trades use new params |
| **+4 hours** | Check initial results | No errors, trades executing |
| **+12 hours** | Analyze win rate | ≥50% on new trades |
| **+24 hours** | Full review | ≥55% win rate, stable |
| **+25 hours** | Decision point | Go/No-Go for live testing |

---

## ✅ Summary

**What Changed**:
- ✅ Leverage reduced: 3x → 2x
- ✅ Risk per trade reduced: 0.5% → 0.3%
- ✅ Confidence threshold increased: 0.75 → 0.80
- ✅ Auto-execute threshold lowered: $100 → $50

**Why**:
- Protect capital during initial live trading
- Filter out weak short signals (27% win rate)
- Improve overall win rate to 55%+
- Reduce risk exposure by 60%

**Expected Outcome**:
- Fewer trades but higher quality
- Better win rate (55-60% target)
- Lower drawdowns
- Safer path to production

**Status**: ⏳ **Pending service restart**

---

**Applied By**: AI Assistant  
**Reviewed By**: [Pending human review]  
**Next Review**: After 24-hour validation period
