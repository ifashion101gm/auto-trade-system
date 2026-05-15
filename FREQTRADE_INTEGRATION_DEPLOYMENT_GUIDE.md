# Freqtrade Pattern Integration - Deployment Guide

**Version:** 1.0  
**Date:** 2026-05-15  
**Target:** Bybit Demo Account (Zero Disruption)  
**Risk Level:** LOW (All changes are non-breaking)

---

## Pre-Deployment Checklist

### 1. System Requirements
- [ ] Redis server running (for persistent idempotency)
- [ ] Python 3.11+ installed
- [ ] All dependencies in `requirements.txt` up to date
- [ ] Database backup completed

### 2. Configuration Updates

Add the following to your `.env` file:

```bash
# ============================================================================
# Freqtrade Pattern Integration - Feature Flags
# ============================================================================

# Phase 1: Persistent Idempotency
ENABLE_PERSISTENT_IDEMPOTENCY=true
IDEMPOTENCY_TTL_SECONDS=3600  # 1 hour
REDIS_URL=redis://localhost:6379/0

# Phase 2: State Recovery
ENABLE_STATE_RECOVERY=true
STATE_RECOVERY_ON_STARTUP=true

# Phase 3: Enhanced Circuit Breaker
CIRCUIT_BREAKER_PRE_EXECUTION_CHECK=true

# Phase 4: Strategy Interface (Optional)
ENABLE_STRATEGY_INTERFACE=false  # Set to true when ready

# Notification Enhancements
NOTIFICATION_DEDUP_ENABLED=true
NOTIFICATION_RATE_LIMIT_SECONDS=10
```

### 3. Code Changes Summary

**New Files Created:**
- ✅ `app/execution/state_recovery.py` - Trade state recovery engine
- ✅ `app/execution/strategy_interface.py` - Strategy abstraction layer
- ✅ `tests/integration/test_freqtrade_patterns.py` - Verification tests

**Modified Files:**
- ✅ `app/execution/retry_manager.py` - Added `PersistentIdempotencyManager`
- ✅ `app/execution/execution_service.py` - Integrated circuit breaker check
- ✅ `EXECUTION_LAYER_OPTIMIZATION_PLAN.md` - Comprehensive plan document

**No Breaking Changes:**
- All existing APIs remain unchanged
- New features are opt-in via feature flags
- Legacy code paths preserved as fallbacks

---

## Deployment Steps

### Step 1: Backup Current State

```bash
# Backup database
pg_dump vmassit > backups/pre_freqtrade_integration_$(date +%Y%m%d_%H%M%S).sql

# Backup .env file
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Create git commit point
git add .
git commit -m "Pre-Freqtrade integration backup"
```

### Step 2: Install Dependencies

```bash
# Ensure redis-py is installed (if not already)
pip install redis>=4.5.0

# Verify installation
python -c "import redis.asyncio; print('Redis async client OK')"
```

### Step 3: Update Configuration

Edit `.env` file and add the configuration from Section 2 above.

### Step 4: Run Verification Tests

```bash
# Run integration tests
cd /home/admin/.openclaw/workspace/auto-trade-system
python -m pytest tests/integration/test_freqtrade_patterns.py -v

# Expected output: All tests should pass
```

### Step 5: Deploy to Staging First (If Available)

If you have a staging environment:
1. Deploy changes to staging
2. Monitor for 1 hour
3. Verify no errors in logs
4. Check that demo trading continues normally

### Step 6: Deploy to Bybit Demo Account

```bash
# Restart the application with new code
# Method depends on your deployment setup:

# Option A: If using systemd
sudo systemctl restart auto-trade-system

# Option B: If running manually
pkill -f "python.*main.py"
nohup python app/main.py > logs/app.log 2>&1 &

# Option C: If using Docker
docker-compose restart
```

### Step 7: Post-Deployment Verification

#### Immediate Checks (First 5 Minutes)

```bash
# 1. Check application logs for errors
tail -f logs/app.log | grep -i "error\|exception\|failed"

# 2. Verify new components initialized
grep -i "persistent idempotency\|state recovery\|circuit breaker" logs/app.log

# 3. Check Redis connectivity
redis-cli ping  # Should return "PONG"

# 4. Verify no active trades were disrupted
# Check Bybit Demo account UI or API
```

#### Short-Term Monitoring (First Hour)

```bash
# Monitor for any unusual behavior
tail -f logs/app.log | grep -E "WARNING|ERROR|CRITICAL"

# Check trade execution times (should be <5% slower)
grep "ExecutionService succeeded" logs/app.log

# Verify circuit breaker status
curl http://localhost:8000/api/health/circuit-breaker  # If endpoint exists
```

#### Long-Term Monitoring (First 24 Hours)

- [ ] No duplicate orders detected
- [ ] All trades execute successfully
- [ ] No unexpected rejections
- [ ] Telegram notifications working
- [ ] Reconciliation reports clean

---

## Rollback Plan

If issues are detected, rollback immediately:

### Quick Rollback (< 5 minutes)

```bash
# 1. Disable new features via .env
sed -i 's/ENABLE_PERSISTENT_IDEMPOTENCY=true/ENABLE_PERSISTENT_IDEMPOTENCY=false/' .env
sed -i 's/ENABLE_STATE_RECOVERY=true/ENABLE_STATE_RECOVERY=false/' .env
sed -i 's/CIRCUIT_BREAKER_PRE_EXECUTION_CHECK=true/CIRCUIT_BREAKER_PRE_EXECUTION_CHECK=false/' .env

# 2. Restart application
sudo systemctl restart auto-trade-system

# 3. Verify system returns to normal
tail -f logs/app.log
```

### Full Rollback (If needed)

```bash
# 1. Restore previous code version
git checkout HEAD~1

# 2. Restore database if needed
psql vmassit < backups/pre_freqtrade_integration_TIMESTAMP.sql

# 3. Restore .env
cp .env.backup.TIMESTAMP .env

# 4. Restart application
sudo systemctl restart auto-trade-system
```

---

## Verification Procedures

### Test 1: Idempotency Protection

```python
# Submit same order twice (should only execute once)
# This test can be run via API or script

import asyncio
from app.execution.execution_service import ExecutionService, ExecutionRequest

async def test_idempotency():
    service = ExecutionService(exchange_name="bybit", use_testnet=True)
    
    request = ExecutionRequest(
        symbol='XAUUSDT',
        side='buy',
        entry_price=2000.0,
        quantity=0.01,
        leverage=1,
        user_id='test_user'
    )
    
    # First execution
    result1 = await service.execute_trade(request)
    print(f"First execution: {result1.order_id}")
    
    # Second execution with same parameters (should be deduplicated)
    result2 = await service.execute_trade(request)
    print(f"Second execution: {result2.order_id}")
    
    # Verify same order ID
    assert result1.order_id == result2.order_id
    print("✅ Idempotency test passed")

asyncio.run(test_idempotency())
```

### Test 2: State Recovery

```bash
# Simulate crash scenario:
# 1. Create a pending trade (manually or via API)
# 2. Stop the application before it completes
# 3. Restart application
# 4. Check logs for recovery messages

grep "Trade state recovery" logs/app.log
grep "recovered to OPEN" logs/app.log
```

### Test 3: Circuit Breaker Integration

```bash
# Monitor circuit breaker status
tail -f logs/app.log | grep -i "circuit breaker"

# Should see initialization message:
# "✅ Circuit Breaker integrated into ExecutionService"

# If circuit opens, you'll see:
# "🚫 Trade blocked by circuit breaker: ..."
```

---

## Monitoring Dashboard

### Key Metrics to Watch

1. **Duplicate Prevention Rate**
   - Target: 100% (zero duplicates)
   - Check: Count of idempotency hits in logs

2. **State Recovery Success Rate**
   - Target: 100% (all pending trades recovered)
   - Check: Recovery engine logs

3. **Circuit Breaker Triggers**
   - Target: 0 (unless actual system issues)
   - Check: Circuit breaker alert logs

4. **Execution Latency**
   - Target: <5% increase vs baseline
   - Check: Execution time metrics

5. **Error Rate**
   - Target: No increase vs baseline
   - Check: Error count in logs

### Log Patterns to Monitor

```bash
# Successful idempotency
grep "Idempotency hit" logs/app.log

# State recovery actions
grep "Trade.*recovered" logs/app.log

# Circuit breaker events
grep "Circuit breaker" logs/app.log

# Execution failures (should NOT increase)
grep "ExecutionService failed" logs/app.log
```

---

## Troubleshooting

### Issue 1: Redis Connection Failed

**Symptom:** Logs show "Redis idempotency check failed"

**Solution:**
```bash
# Check Redis is running
systemctl status redis

# Start Redis if stopped
sudo systemctl start redis

# Verify connectivity
redis-cli ping
```

### Issue 2: State Recovery Not Running

**Symptom:** No recovery messages in logs after restart

**Solution:**
```bash
# Check feature flag
grep ENABLE_STATE_RECOVERY .env

# Should be: ENABLE_STATE_RECOVERY=true

# Check startup logs
grep "Trade State Recovery Engine" logs/app.log
```

### Issue 3: Circuit Breaker Blocking Trades

**Symptom:** Trades rejected with "Circuit breaker OPEN"

**Solution:**
```bash
# Check circuit breaker health
curl http://localhost:8000/api/health/circuit-breaker

# If false positive, check system metrics:
# - API failure rate
# - Slippage levels
# - Position sync status

# To reset (if safe):
# Wait for automatic recovery timeout (60s default)
# Or fix underlying issue (API errors, etc.)
```

### Issue 4: Performance Degradation

**Symptom:** Execution latency increased >10%

**Solution:**
```bash
# Check Redis performance
redis-cli --latency

# If Redis slow, consider:
# 1. Increasing Redis memory
# 2. Reducing TTL values
# 3. Disabling persistent idempotency temporarily

# Temporary disable:
sed -i 's/ENABLE_PERSISTENT_IDEMPOTENCY=true/ENABLE_PERSISTENT_IDEMPOTENCY=false/' .env
sudo systemctl restart auto-trade-system
```

---

## Success Criteria

The deployment is considered successful when:

- [x] All verification tests pass
- [ ] No duplicate orders in 24 hours
- [ ] Zero disruption to Bybit demo trading
- [ ] State recovery works correctly (if tested)
- [ ] Circuit breaker doesn't trigger falsely
- [ ] Execution latency increase <5%
- [ ] No new error patterns in logs
- [ ] Telegram notifications still working

---

## Next Steps After Successful Deployment

1. **Monitor for 48 hours** - Ensure stability
2. **Run full E2E test suite** - Verify all flows
3. **Document lessons learned** - Update this guide
4. **Proceed to Phase 2** - Enhanced cooldowns
5. **Consider production rollout** - If demo stable

---

## Support & Contacts

- **Technical Lead:** [Your Name]
- **Emergency Contact:** [Phone/Email]
- **Documentation:** See `EXECUTION_LAYER_OPTIMIZATION_PLAN.md`
- **Test Suite:** `tests/integration/test_freqtrade_patterns.py`

---

**Last Updated:** 2026-05-15  
**Status:** Ready for Deployment  
**Approved By:** [Pending Approval]
