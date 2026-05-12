# Risk Engine & Circuit Breaker - Quick Reference

## 🎯 Quick Commands

### Run Tests
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
PYTHONPATH=. python scripts/test_risk_engine.py
```

### Check Logs
```bash
# Risk engine events
tail -f logs/app.log | grep "Risk Engine"

# Circuit breaker events  
tail -f logs/app.log | grep "Circuit Breaker"

# Trade rejections
tail -f logs/app.log | grep "risk_rejected"
```

### Database Migration
```bash
alembic upgrade head
```

---

## ⚙️ Key Configuration (app/config.py)

### Risk Limits
| Parameter | Default | Description |
|-----------|---------|-------------|
| `RISK_MAX_DAILY_LOSS_PCT` | 0.03 (3%) | Daily loss limit |
| `RISK_MAX_DRAWDOWN_PCT` | 0.15 (15%) | Max account drawdown |
| `RISK_MAX_POSITION_SIZE_PCT` | 0.015 (1.5%) | Per-trade position size |
| `RISK_MAX_LEVERAGE` | 5x | Maximum leverage |
| `RISK_VOLATILITY_THRESHOLD` | 0.8 | ATR chaos threshold |
| `RISK_MAX_SLIPPAGE_PCT` | 0.002 (0.2%) | Max bid-ask spread |
| `RISK_COOLDOWN_PERIOD_SECONDS` | 300 (5 min) | Cooldown after losses |
| `RISK_MAX_CONSECUTIVE_LOSSES` | 3 | Losses before cooldown |

### Circuit Breaker Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | 5 | API failures before trigger |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | 60s | Recovery wait time |
| `CIRCUIT_BREAKER_SLIPPAGE_THRESHOLD` | 0.005 (0.5%) | Slippage limit |
| `CIRCUIT_BREAKER_LATENCY_THRESHOLD_MS` | 5000 (5s) | API latency limit |
| `CIRCUIT_BREAKER_SPREAD_THRESHOLD_PCT` | 0.005 (0.5%) | Spread widening limit |
| `CIRCUIT_BREAKER_SYNC_TOLERANCE_PCT` | 0.01 (1%) | Position sync tolerance |

---

## 🔍 Common Issues & Fixes

### Trades Rejected
**Check:** `grep "Trade rejected by risk engine" logs/app.log -A 3`
**Fix:** Adjust thresholds in `app/config.py`

### Circuit Breaker Open
**Check:** `grep "CIRCUIT BREAKER TRIGGERED" logs/app.log`
**Fix:** 
- API failures → Check exchange connectivity
- High latency → Increase `LATENCY_THRESHOLD_MS`
- Sync mismatch → Run reconciliation

### Cooldown Active
**Check:** Look for "Cooldown period active" in logs
**Fix:** Reduce `RISK_COOLDOWN_PERIOD_SECONDS` or `RISK_MAX_CONSECUTIVE_LOSSES`

---

## 📊 Risk Decision Flow

```
Trade Proposal
    ↓
Circuit Breaker Check ← System healthy?
    ↓ YES
Volatility Check ← Market stable?
    ↓ YES
Slippage Check ← Spread acceptable?
    ↓ YES
Risk Engine Validation
    ├─ Daily loss < 3%? ✓
    ├─ Drawdown < 15%? ✓
    ├─ Position ≤ 1.5%? ✓
    ├─ Leverage ≤ 5x? ✓
    └─ No cooldown? ✓
    ↓ ALL PASS
Trade Validator (existing rules)
    ↓
Execute Trade
```

---

## 🚨 Alert Types

### Risk Alerts (Telegram)
- 📉 Daily loss limit
- 📊 Drawdown warning
- ⏸️ Cooldown activated
- 🌪️ High volatility
- ⚖️ Position size exceeded
- 🔒 Leverage exceeded

### Circuit Breaker Alerts
- 🚨 CRITICAL: OPEN (trading blocked)
- 🔧 WARNING: HALF_OPEN (testing recovery)
- ✅ INFO: CLOSED (recovered)

### Emergency Alerts
- 🚨 EMERGENCY: Positions closed

---

## 💡 Tuning Profiles

### Conservative
```python
RISK_MAX_DAILY_LOSS_PCT = 0.02      # 2%
RISK_MAX_POSITION_SIZE_PCT = 0.01   # 1%
RISK_MAX_LEVERAGE = 3               # 3x
RISK_COOLDOWN_PERIOD_SECONDS = 600  # 10 min
```

### Balanced (Default)
```python
RISK_MAX_DAILY_LOSS_PCT = 0.03      # 3%
RISK_MAX_POSITION_SIZE_PCT = 0.015  # 1.5%
RISK_MAX_LEVERAGE = 5               # 5x
RISK_COOLDOWN_PERIOD_SECONDS = 300  # 5 min
```

### Aggressive
```python
RISK_MAX_DAILY_LOSS_PCT = 0.05      # 5%
RISK_MAX_POSITION_SIZE_PCT = 0.02   # 2%
RISK_MAX_LEVERAGE = 10              # 10x
RISK_COOLDOWN_PERIOD_SECONDS = 120  # 2 min
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `app/risk/risk_engine.py` | Risk management logic |
| `app/infra/circuit_breaker.py` | System health monitoring |
| `app/config.py` | Configuration parameters |
| `scripts/test_risk_engine.py` | Test suite |
| `RISK_ENGINE_IMPLEMENTATION.md` | Full documentation |
| `RISK_ENGINE_DEPLOYMENT_CHECKLIST.md` | Deployment guide |

---

## 🔗 Integration Points

### Trading Service
- Circuit breaker check before each cycle
- Risk validation before execution
- API call tracking for monitoring

### AI Orchestrator
- Optional risk engine injection
- Pre-trade veto capability

### Notifications
- Risk alerts via Telegram
- Circuit breaker state changes
- Emergency closures

---

## ✅ Verification Checklist

After deployment, verify:
- [ ] All tests pass (`test_risk_engine.py`)
- [ ] Database tables created (`risk_metrics`, `circuit_breaker_events`)
- [ ] Risk engine initializes without errors
- [ ] Circuit breaker initializes without errors
- [ ] Telegram notifications working
- [ ] Trading cycles include risk validation
- [ ] Logs show risk checks passing

---

*For detailed documentation, see `RISK_ENGINE_IMPLEMENTATION.md`*
