# Bybit Skill Integration - Phase 3 Plan: Testing & Deployment

**Date**: May 13, 2026  
**Status**: PLANNING  
**Source**: Official Bybit Trading Skill v1.3.0  
**Estimated Effort**: 4-6 hours

---

## Executive Summary

Phase 3 focuses on validating all Phase 1 & 2 improvements through comprehensive testing, performance validation, and production deployment preparation. This phase ensures the system is production-ready and meets all official Bybit skill requirements.

---

## Phase 3 Objectives

### 1. Integration Testing on Bybit Testnet
Validate all implemented features work correctly with real API calls in a safe environment.

### 2. Performance Validation Under Load
Ensure retry logic and error handling don't introduce unacceptable latency or resource usage.

### 3. Production Deployment Preparation
Create deployment checklists, rollback procedures, and monitoring configurations.

### 4. Monitoring & Alerting Setup
Configure alerts for critical errors, retry exhaustion, and security violations.

---

## Task Breakdown

### Task 3.1: Integration Testing on Bybit Testnet (2-3 hours)

#### 3.1.1 Credential Masking Validation
**Objective**: Verify no credentials leak in logs during actual API operations.

**Test Steps**:
```bash
# 1. Start application with testnet credentials
export BYBIT_API_KEY=testnet_key_here
export BYBIT_API_SECRET=testnet_secret_here
export BYBIT_MODE=testnet

# 2. Execute various operations
python scripts/test_bybit_integration.py --test masking

# 3. Review logs for credential exposure
grep -i "api.key\|secret" logs/bybit_test.log | grep -v "\.\.\."
```

**Expected Results**:
- ✅ All API keys show masked format: `test_...2345`
- ✅ All secrets show masked format: `***...y_xyz`
- ✅ Zero instances of full credentials in logs

**Success Criteria**: No credential leaks in 100+ log lines reviewed.

---

#### 3.1.2 Position Mode Validation Testing
**Objective**: Verify position mode is checked before every order placement.

**Test Steps**:
```bash
# 1. Set account to hedge mode via Bybit dashboard
# 2. Place market order
python scripts/test_bybit_integration.py --test position-mode

# 3. Verify logs show position mode check
grep "Position mode for" logs/bybit_test.log

# 4. Verify order includes correct positionIdx
grep "positionIdx=" logs/bybit_test.log
```

**Expected Results**:
- ✅ Position mode queried before each order
- ✅ Correct positionIdx used (0 for one-way, 1/2 for hedge)
- ✅ No position conflicts or rejections

**Success Criteria**: 10 consecutive orders placed successfully in hedge mode.

---

#### 3.1.3 Large Order Risk Validation Testing
**Objective**: Verify large order warnings trigger correctly and block mainnet high-risk orders.

**Test Steps**:
```bash
# 1. Test with small order (<$10k)
python scripts/test_bybit_integration.py --test risk-small

# 2. Test with medium order (>$10k, <20% balance)
python scripts/test_bybit_integration.py --test risk-medium

# 3. Test with large order (>20% balance) on testnet
python scripts/test_bybit_integration.py --test risk-large-testnet

# 4. Simulate large order on mainnet (dry-run mode)
python scripts/test_bybit_integration.py --test risk-large-mainnet-dryrun
```

**Expected Results**:
- ✅ Small orders: No warnings, proceed normally
- ✅ Medium orders: Warning logged, proceed with confirmation
- ✅ Large orders on testnet: Warning logged, proceed with confirmation
- ✅ Large orders on mainnet: BLOCKED until manual confirmation

**Success Criteria**: Risk thresholds enforced correctly for all scenarios.

---

#### 3.1.4 Retry Logic Testing
**Objective**: Verify graceful degradation works under simulated failures.

**Test Steps**:
```bash
# 1. Test retry on transient errors
python scripts/test_bybit_integration.py --test retry-transient

# 2. Test immediate failure on non-retryable errors
python scripts/test_bybit_integration.py --test retry-permanent

# 3. Test exponential backoff timing
python scripts/test_bybit_integration.py --test retry-backoff-timing

# 4. Test max retries exhaustion
python scripts/test_bybit_integration.py --test retry-exhaustion
```

**Expected Results**:
- ✅ Transient errors retried up to 3 times with backoff
- ✅ Non-retryable errors fail immediately (no wasted retries)
- ✅ Backoff delays follow exponential pattern (1s, 2s, 4s + jitter)
- ✅ Clear error message after retry exhaustion

**Success Criteria**: Retry behavior matches official Bybit skill specifications.

---

#### 3.1.5 Enhanced Error Message Testing
**Objective**: Verify error messages provide actionable troubleshooting steps.

**Test Steps**:
```bash
# 1. Trigger timestamp error (set wrong system clock temporarily)
python scripts/test_bybit_integration.py --test error-timestamp

# 2. Trigger auth error (use invalid API key)
python scripts/test_bybit_integration.py --test error-auth

# 3. Trigger rate limit error (send rapid requests)
python scripts/test_bybit_integration.py --test error-rate-limit

# 4. Review error messages for actionability
cat logs/bybit_errors.log | grep -A 10 "IMMEDIATE ACTION\|TROUBLESHOOTING"
```

**Expected Results**:
- ✅ Timestamp error includes NTP sync commands
- ✅ Auth error includes key verification steps
- ✅ Rate limit error mentions automatic retry
- ✅ All errors provide specific next steps

**Success Criteria**: Users can resolve common issues without consulting external docs.

---

### Task 3.2: Performance Validation (1 hour)

#### 3.2.1 Latency Impact Assessment
**Objective**: Measure performance overhead from new features.

**Metrics to Collect**:
```python
# Benchmark script
import time
import asyncio

async def benchmark_order_placement():
    # Measure baseline (without retry wrapper)
    start = time.time()
    await client.create_market_order("BTCUSDT", "buy", 0.001)
    baseline_time = time.time() - start
    
    # Measure with retry wrapper
    start = time.time()
    await client.fetch_with_retry(
        operation=lambda: client.create_market_order("BTCUSDT", "buy", 0.001),
        operation_name="benchmark"
    )
    wrapped_time = time.time() - start
    
    print(f"Baseline: {baseline_time*1000:.2f}ms")
    print(f"With retry: {wrapped_time*1000:.2f}ms")
    print(f"Overhead: {(wrapped_time - baseline_time)*1000:.2f}ms")
```

**Acceptable Thresholds**:
- Normal operation overhead: < 5ms
- Retry scenario (1 retry): < 2 seconds total
- Retry scenario (3 retries): < 10 seconds total

---

#### 3.2.2 Resource Usage Monitoring
**Objective**: Ensure retry logic doesn't cause memory leaks or CPU spikes.

**Monitoring Commands**:
```bash
# Monitor memory usage during sustained operations
watch -n 5 'ps aux | grep python | grep -v grep'

# Monitor CPU usage
top -p $(pgrep -f "uvicorn app.main")

# Check for memory leaks over 1-hour period
python scripts/monitor_resource_usage.py --duration 3600
```

**Acceptable Thresholds**:
- Memory growth: < 50MB over 1 hour
- CPU usage: < 10% during normal operation
- No file descriptor leaks

---

### Task 3.3: Production Deployment Preparation (1-2 hours)

#### 3.3.1 Deployment Checklist Creation
**File**: `scripts/deploy_bybit_skill_integration.sh`

```bash
#!/bin/bash
# Pre-deployment checks
echo "🔍 Running pre-deployment checks..."

# 1. Verify all tests pass
python scripts/test_bybit_phase1_security.py || exit 1
python scripts/test_bybit_phase2_reliability.py || exit 1

# 2. Check configuration
echo "✅ Verifying .env configuration..."
grep -q "BYBIT_API_KEY" .env || { echo "❌ Missing BYBIT_API_KEY"; exit 1; }
grep -q "BYBIT_API_SECRET" .env || { echo "❌ Missing BYBIT_API_SECRET"; exit 1; }

# 3. Backup current version
echo "📦 Creating backup..."
cp app/infra/bybit_client.py app/infra/bybit_client.py.backup.$(date +%Y%m%d_%H%M%S)

# 4. Deploy new version
echo "🚀 Deploying Phase 1 & 2 improvements..."
git pull origin main

# 5. Restart services
echo "🔄 Restarting services..."
systemctl restart auto-trade-system

# 6. Verify health
echo "✅ Checking system health..."
sleep 10
curl http://localhost:8000/health || { echo "❌ Health check failed"; exit 1; }

echo "✅ Deployment complete!"
```

---

#### 3.3.2 Rollback Procedure
**File**: `scripts/rollback_bybit_integration.sh`

```bash
#!/bin/bash
# Emergency rollback procedure

echo "⚠️  Initiating emergency rollback..."

# 1. Stop services
systemctl stop auto-trade-system

# 2. Restore backup
LATEST_BACKUP=$(ls -t app/infra/bybit_client.py.backup.* | head -1)
if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup found!"
    exit 1
fi

echo "📦 Restoring from: $LATEST_BACKUP"
cp "$LATEST_BACKUP" app/infra/bybit_client.py

# 3. Restart services
systemctl start auto-trade-system

# 4. Verify rollback
sleep 10
curl http://localhost:8000/health || { echo "❌ Rollback verification failed"; exit 1; }

echo "✅ Rollback complete!"
```

---

#### 3.3.3 Configuration Validation
**File**: `scripts/validate_bybit_config_phase3.py`

```python
"""Validate Bybit configuration for Phase 3 deployment."""

import os
from dotenv import load_dotenv

load_dotenv()

def validate_config():
    errors = []
    
    # Required variables
    required_vars = [
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "BYBIT_MODE",
        "BYBIT_RECV_WINDOW",
        "BYBIT_RATE_LIMIT_CALLS_PER_SECOND"
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required variable: {var}")
    
    # Validate mode
    mode = os.getenv("BYBIT_MODE", "").lower()
    if mode not in ["demo", "testnet", "mainnet"]:
        errors.append(f"Invalid BYBIT_MODE: {mode} (must be demo/testnet/mainnet)")
    
    # Validate recv_window
    try:
        recv_window = int(os.getenv("BYBIT_RECV_WINDOW", "5000"))
        if recv_window < 1000 or recv_window > 30000:
            errors.append(f"BYBIT_RECV_WINDOW out of range: {recv_window} (1000-30000ms)")
    except ValueError:
        errors.append("BYBIT_RECV_WINDOW must be an integer")
    
    # Validate rate limit
    try:
        rate_limit = float(os.getenv("BYBIT_RATE_LIMIT_CALLS_PER_SECOND", "10"))
        if rate_limit < 1 or rate_limit > 120:
            errors.append(f"Rate limit out of range: {rate_limit} (1-120 req/sec)")
    except ValueError:
        errors.append("BYBIT_RATE_LIMIT_CALLS_PER_SECOND must be a number")
    
    # Security checks
    api_key = os.getenv("BYBIT_API_KEY", "")
    if len(api_key) < 10:
        errors.append("BYBIT_API_KEY appears too short (possible test key)")
    
    api_secret = os.getenv("BYBIT_API_SECRET", "")
    if len(api_secret) < 20:
        errors.append("BYBIT_API_SECRET appears too short (possible test key)")
    
    return errors

if __name__ == "__main__":
    errors = validate_config()
    if errors:
        print("❌ Configuration validation failed:")
        for error in errors:
            print(f"   - {error}")
        exit(1)
    else:
        print("✅ Configuration validation passed!")
        exit(0)
```

---

### Task 3.4: Monitoring & Alerting Setup (1 hour)

#### 3.4.1 Prometheus Metrics
**File**: `app/monitoring/bybit_metrics.py`

```python
"""Prometheus metrics for Bybit integration."""

from prometheus_client import Counter, Histogram, Gauge

# Retry metrics
retry_attempts = Counter(
    'bybit_retry_attempts_total',
    'Total retry attempts by operation type',
    ['operation', 'result']  # result: success, exhausted
)

retry_duration = Histogram(
    'bybit_retry_duration_seconds',
    'Time spent retrying operations',
    ['operation'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Error metrics
error_count = Counter(
    'bybit_errors_total',
    'Total errors by type',
    ['error_code', 'is_transient']
)

# Security metrics
credential_mask_failures = Counter(
    'bybit_credential_mask_failures_total',
    'Times credential masking failed (potential leak)'
)

# Risk validation metrics
large_order_warnings = Counter(
    'bybit_large_order_warnings_total',
    'Large order warnings triggered',
    ['order_type']  # medium, large, blocked
)

# Position mode metrics
position_mode_checks = Counter(
    'bybit_position_mode_checks_total',
    'Position mode checks performed',
    ['mode']  # one_way, hedge
)
```

---

#### 3.4.2 Alert Rules
**File**: `monitoring/prometheus-bybit-alerts.yml`

```yaml
groups:
  - name: bybit_integration_alerts
    rules:
      # High retry rate
      - alert: BybitHighRetryRate
        expr: rate(bybit_retry_attempts_total{result="exhausted"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High Bybit API retry exhaustion rate"
          description: "{{ $value }} retries exhausted per second"

      # Credential mask failure (CRITICAL)
      - alert: BybitCredentialMaskFailure
        expr: increase(bybit_credential_mask_failures_total[1m]) > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Bybit credential masking failure detected"
          description: "Potential credential leak in logs!"

      # Authentication failures
      - alert: BybitAuthFailures
        expr: increase(bybit_errors_total{error_code="10003"}[10m]) > 5
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Multiple Bybit authentication failures"
          description: "{{ $value }} auth failures in 10 minutes"

      # Rate limit exceeded frequently
      - alert: BybitFrequentRateLimits
        expr: increase(bybit_errors_total{error_code="10006"}[15m]) > 10
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Frequent Bybit rate limit errors"
          description: "{{ $value }} rate limit errors in 15 minutes"

      # Large orders blocked
      - alert: BybitLargeOrdersBlocked
        expr: increase(bybit_large_order_warnings_total{order_type="blocked"}[1h]) > 0
        for: 1h
        labels:
          severity: info
        annotations:
          summary: "Large Bybit orders blocked"
          description: "{{ $value }} orders blocked due to risk limits"
```

---

#### 3.4.3 Grafana Dashboard
**File**: `monitoring/grafana/dashboards/bybit-integration.json`

Dashboard panels:
1. **API Call Success Rate** (last 1h, 6h, 24h)
2. **Retry Attempt Distribution** (by operation type)
3. **Error Rate by Type** (transient vs permanent)
4. **Average Response Time** (with/without retries)
5. **Large Order Warnings** (timeline)
6. **Position Mode Distribution** (one-way vs hedge)
7. **Credential Masking Status** (success/failure count)

---

## Acceptance Criteria

### Must Pass (Go/No-Go Decision)
- [ ] All integration tests pass on testnet (Task 3.1)
- [ ] Performance overhead < 5ms per operation (Task 3.2.1)
- [ ] No memory leaks over 1-hour stress test (Task 3.2.2)
- [ ] Configuration validation passes (Task 3.3.3)
- [ ] Zero credential leaks in 1000+ log lines (Task 3.1.1)

### Should Pass (Warnings if Failed)
- [ ] Retry success rate > 90% for transient errors
- [ ] Error messages rated "actionable" by 3+ testers
- [ ] Prometheus metrics collecting data correctly
- [ ] Grafana dashboard displays all panels

### Nice to Have (Future Enhancements)
- [ ] Automated canary deployment configured
- [ ] A/B testing framework for retry parameters
- [ ] Machine learning-based retry optimization

---

## Timeline

| Day | Tasks | Duration |
|-----|-------|----------|
| Day 1 | Task 3.1: Integration Testing | 2-3 hours |
| Day 1 | Task 3.2: Performance Validation | 1 hour |
| Day 2 | Task 3.3: Deployment Preparation | 1-2 hours |
| Day 2 | Task 3.4: Monitoring Setup | 1 hour |
| **Total** | **All Phase 3 Tasks** | **5-7 hours** |

---

## Risk Assessment

### High Risk
- **Mainnet deployment with untested code**: Mitigated by thorough testnet validation
- **Credential exposure in production logs**: Mitigated by automated log scanning

### Medium Risk
- **Performance degradation under load**: Mitigated by performance benchmarks
- **Retry storms causing API bans**: Mitigated by exponential backoff with jitter

### Low Risk
- **Configuration errors**: Mitigated by validation script
- **Monitoring gaps**: Mitigated by comprehensive alert rules

---

## Next Steps After Phase 3

1. **Deploy to Production**: Execute deployment checklist
2. **Monitor for 48 Hours**: Watch for unexpected errors or performance issues
3. **Collect Feedback**: Survey users on error message clarity
4. **Document Lessons Learned**: Update integration plan with findings
5. **Plan Phase 4**: Consider advanced features (circuit breaker, adaptive backoff)

---

## References

- Phase 1 Report: `BYBIT_SKILL_PHASE1_REPORT.md`
- Phase 2 Report: `BYBIT_SKILL_PHASE2_REPORT.md`
- Integration Plan: `BYBIT_SKILL_INTEGRATION_PLAN.md`
- Quick Reference: `BYBIT_SKILL_QUICKREF.md`
- Official Bybit Skill: https://github.com/bybit-exchange/skills

---

**Approval Required**: Before proceeding with Phase 3, confirm:
- [ ] Testnet API keys configured in `.env`
- [ ] Sufficient testnet USDT balance for order testing
- [ ] Monitoring stack (Prometheus/Grafana) accessible
- [ ] Rollback procedure tested and documented
