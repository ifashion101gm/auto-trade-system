# Freqtrade Integration - Quick Reference Card

**One-Page Summary for Fast Access**

---

## 🎯 What Was Added

| Component | File | Purpose |
|-----------|------|---------|
| **Persistent Idempotency** | `retry_manager.py` | Redis-backed duplicate prevention |
| **State Recovery Engine** | `state_recovery.py` | Recover stuck trades after crash |
| **Strategy Interface** | `strategy_interface.py` | Clean signal/execution separation |
| **Circuit Breaker Check** | `execution_service.py` | Pre-execution health gate |

---

## ⚙️ Configuration (.env)

```bash
ENABLE_PERSISTENT_IDEMPOTENCY=true
IDEMPOTENCY_TTL_SECONDS=3600
ENABLE_STATE_RECOVERY=true
CIRCUIT_BREAKER_PRE_EXECUTION_CHECK=true
```

---

## 🚀 Quick Start

### 1. Deploy Changes
```bash
git pull
pip install redis>=4.5.0
# Update .env with config above
sudo systemctl restart auto-trade-system
```

### 2. Verify Installation
```bash
# Run tests
python -m pytest tests/integration/test_freqtrade_patterns.py -v

# Check logs
grep "Persistent Idempotency\|State Recovery\|Circuit Breaker" logs/app.log
```

### 3. Monitor Health
```bash
# Watch for errors
tail -f logs/app.log | grep -i "error\|exception"

# Check idempotency hits
grep "Idempotency hit" logs/app.log

# Verify recovery
grep "Trade.*recovered" logs/app.log
```

---

## 🔍 Key Features

### Persistent Idempotency
```python
# Automatic - no code changes needed
# Prevents duplicate orders even after restart
# Falls back to memory if Redis down
```

### State Recovery
```python
# Runs automatically on startup
# Finds pending trades and verifies on exchange
# Updates database to match reality
```

### Strategy Interface
```python
from app.execution.strategy_interface import IStrategy, TradeSignal

class MyStrategy(IStrategy):
    async def generate_signal(self, market_data):
        # Your logic here
        return TradeSignal(...)  # or None
```

### Circuit Breaker
```python
# Automatic - checks before every trade
# Blocks trades if system unhealthy
# Monitors: API errors, slippage, latency, sync
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/integration/test_freqtrade_patterns.py -v

# Test specific feature
python -m pytest tests/integration/test_freqtrade_patterns.py::test_persistent_idempotency_basic -v
```

---

## 🔄 Rollback (If Needed)

```bash
# Quick rollback via config
sed -i 's/ENABLE_PERSISTENT_IDEMPOTENCY=true/ENABLE_PERSISTENT_IDEMPOTENCY=false/' .env
sed -i 's/ENABLE_STATE_RECOVERY=true/ENABLE_STATE_RECOVERY=false/' .env
sudo systemctl restart auto-trade-system

# Full rollback
git checkout HEAD~1
sudo systemctl restart auto-trade-system
```

---

## 📊 Monitoring Checklist

**First Hour:**
- [ ] No errors in logs
- [ ] Idempotency working (check logs)
- [ ] Trades executing normally
- [ ] No duplicate orders

**First 24 Hours:**
- [ ] State recovery ran successfully (if restarted)
- [ ] Circuit breaker didn't trigger falsely
- [ ] Performance impact <5%
- [ ] Telegram notifications working

**First Week:**
- [ ] Zero duplicate orders
- [ ] All trades executed correctly
- [ ] No state inconsistencies
- [ ] System stable

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| Redis connection failed | `sudo systemctl start redis` |
| State recovery not running | Check `ENABLE_STATE_RECOVERY=true` in .env |
| Circuit breaker blocking trades | Check system health, wait for auto-recovery |
| Performance slow | Disable persistent idempotency temporarily |
| Duplicate orders detected | Check Redis is running and accessible |

---

## 📚 Documentation

- **Full Plan:** `EXECUTION_LAYER_OPTIMIZATION_PLAN.md`
- **Deployment Guide:** `FREQTRADE_INTEGRATION_DEPLOYMENT_GUIDE.md`
- **Implementation Summary:** `IMPLEMENTATION_SUMMARY_FREQTRADE.md`
- **Tests:** `tests/integration/test_freqtrade_patterns.py`

---

## ✅ Success Criteria

- [x] Code complete
- [x] Tests passing
- [x] Docs written
- [ ] Deployed to staging
- [ ] 48h monitoring on demo
- [ ] Zero disruptions
- [ ] Approved for production

---

**Status:** Ready for Deployment  
**Risk:** LOW  
**Impact:** HIGH (Improved resilience)  
**Downtime:** ZERO  

---

*Last Updated: 2026-05-15*
