# Phase 1 Deployment Guide - Bybit Demo Environment

**Date:** 2026-05-15  
**Version:** 1.0  
**Target:** Bybit Demo Trading Account (api-demo.bybit.com)  
**Risk Level:** NEGLIGIBLE (Non-breaking, configuration-driven changes)  
**Estimated Downtime:** <30 seconds (graceful restart)  

---

## 📋 Overview

This guide provides step-by-step instructions for safely deploying **Phase 1 Issues A & B** to your active Bybit Demo trading environment:

- **Issue A**: Execution Layer Optimization with Freqtrade patterns
  - Persistent Idempotency Manager (Redis-backed duplicate prevention)
  - Trade State Recovery Engine (crash recovery)
  - Strategy Interface (clean signal/execution separation)
  - Circuit Breaker Integration (pre-execution health checks)

- **Issue B**: Reconciliation Engine Enhancements
  - Configurable scheduling intervals
  - Prometheus metrics for mismatch detection
  - Telegram alerts for critical state divergences
  - Age-based orphaned order detection
  - Configurable ghost position handling

**All changes are backward compatible and controlled by configuration flags.**

---

## ✅ Pre-Deployment Verification

### Step 1: Verify Code Integrity

Run the verification script to ensure all new modules can be imported correctly:

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system

# Activate virtual environment
source .venv/bin/activate

# Run verification script
python verify_freqtrade_integration.py
```

**Expected Output:**
```
================================================================================
Verifying Freqtrade Pattern Integration
================================================================================

✅ PersistentIdempotencyManager imported successfully
✅ TradeStateRecovery imported successfully
✅ Strategy interface imported successfully
✅ ExecutionService imported successfully
✅ Circuit breaker integration verified in ExecutionService
✅ Configuration loaded successfully

================================================================================
✅ All verifications PASSED

Summary:
  • Persistent Idempotency Manager: Ready
  • Trade State Recovery Engine: Ready
  • Strategy Interface: Ready
  • Circuit Breaker Integration: Ready
```

**If any checks fail:**
- Do NOT proceed with deployment
- Check error messages for missing dependencies
- Review file permissions on new modules
- Contact support if issues persist

---

### Step 2: Check Active Trading Status

Verify current trading state to ensure no disruption:

```bash
# Check if services are running
sudo systemctl status auto-trade-api
sudo systemctl status auto-trade-worker

# Check for open positions via API
curl -s http://localhost:8000/api/v1/trading/positions | python3 -m json.tool

# Check reconciliation engine status (if already running)
curl -s http://localhost:8000/api/v1/reconciliation/status | python3 -m json.tool
```

**Record Current State:**
- Number of open positions: `___`
- Last trade timestamp: `___`
- Reconciliation engine running: `Yes/No`
- Any pending orders: `___`

**⚠️ WARNING:** If you have pending orders in transitional states (ORDER_SUBMITTING, PENDING_CONFIRMATION), note them carefully. The State Recovery Engine will verify these on restart.

---

### Step 3: Backup Configuration Files

Create backups before making changes:

```bash
# Timestamp for backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup .env file
cp .env .env.backup.${TIMESTAMP}

# Backup config.py (for reference)
cp app/config.py app/config.py.backup.${TIMESTAMP}

# Verify backups exist
ls -lh .env.backup.* app/config.py.backup.*
```

**Backup Location:** `/home/admin/.openclaw/workspace/auto-trade-system/`

---

## ⚙️ Configuration Updates

### Step 4: Update .env File

Add the following configuration variables to your `.env` file. These enable the new features while maintaining backward compatibility.

```bash
# Open .env for editing
nano .env
```

**Add these sections at the end of the file:**

```ini
# =============================================================================
# Phase 1 Issue A: Freqtrade Integration (Execution Layer Optimization)
# =============================================================================

# Persistent Idempotency (Redis-backed duplicate order prevention)
ENABLE_PERSISTENT_IDEMPOTENCY=true
IDEMPOTENCY_TTL_SECONDS=3600  # Cache TTL: 1 hour

# Trade State Recovery (crash recovery for stuck trades)
ENABLE_STATE_RECOVERY=true

# Circuit Breaker (pre-execution health checks)
CIRCUIT_BREAKER_PRE_EXECUTION_CHECK=true

# =============================================================================
# Phase 1 Issue B: Reconciliation Engine Enhancements
# =============================================================================

# Scheduling Configuration
RECONCILIATION_INTERVAL_SECONDS=120  # Run every 2 minutes

# Auto-Repair Configuration
RECONCILIATION_AUTO_REPAIR_SAFE=true  # Auto-repair safe mismatches

# Notification Configuration
RECONCILIATION_TELEGRAM_ALERTS=true  # Enable Telegram alerts for critical mismatches
RECONCILIATION_PROMETHEUS_METRICS=true  # Publish metrics to Prometheus

# Orphaned Order Detection
RECONCILIATION_MAX_ORPHANED_AGE_HOURS=24  # Only flag orders older than 24h

# Ghost Position Handling
# Options: import_and_alert, alert_only, ignore
RECONCILIATION_GHOST_POSITION_ACTION=import_and_alert
```

**Save and exit:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

### Step 5: Verify Configuration Syntax

Test that the configuration loads correctly:

```bash
# Test configuration loading
python3 -c "from app.config import settings; print('✅ Configuration loaded successfully'); print(f'Reconciliation Interval: {settings.RECONCILIATION_INTERVAL_SECONDS}s')"
```

**Expected Output:**
```
✅ Configuration loaded successfully
Reconciliation Interval: 120s
```

**If this fails:**
- Check `.env` syntax (no spaces around `=`)
- Ensure all values are properly quoted if they contain special characters
- Review error message for specific variable causing issue

---

## 🔄 Service Restart Procedure

### Step 6: Graceful Service Restart

The restart sequence ensures zero disruption to open positions:

```bash
# Step 6a: Stop worker first (stops new trade proposals)
echo "🛑 Stopping worker service..."
sudo systemctl stop auto-trade-worker

# Wait for worker to finish current tasks
sleep 5

# Step 6b: Stop API service (stops accepting new requests)
echo "🛑 Stopping API service..."
sudo systemctl stop auto-trade-api

# Wait for graceful shutdown
sleep 3

# Step 6c: Verify both services stopped
echo "✅ Verifying services stopped..."
sudo systemctl is-active auto-trade-api auto-trade-worker

# Expected output: inactive (dead) for both

# Step 6d: Start API service first
echo "🚀 Starting API service..."
sudo systemctl start auto-trade-api

# Wait for API to initialize
sleep 5

# Step 6e: Start worker service
echo "🚀 Starting worker service..."
sudo systemctl start auto-trade-worker

# Wait for worker to initialize
sleep 5

# Step 6f: Verify both services running
echo "✅ Verifying services running..."
sudo systemctl is-active auto-trade-api auto-trade-worker

# Expected output: active (running) for both
```

---

### Step 7: Monitor Startup Logs

Watch the logs to confirm successful initialization:

```bash
# Follow API logs
journalctl -u auto-trade-api -f --since "2 minutes ago"

# In another terminal, follow worker logs
journalctl -u auto-trade-worker -f --since "2 minutes ago"
```

**Look for these success indicators:**

```
✅ Trade State Recovery Engine initialized
✅ Strategy Registry initialized
✅ Circuit Breaker integrated into ExecutionService
✅ Reconciliation Engine initialized (BYBIT)
   Interval: 120s
   Auto-repair: ENABLED
   Telegram alerts: ENABLED
   Prometheus metrics: ENABLED
   Ghost position action: import_and_alert
🔄 Starting trade state recovery...
✅ No pending trades found - system state is clean
```

**If you see errors:**
- Note the error message
- Check if Redis is running: `sudo systemctl status redis`
- Check if PostgreSQL is running: `sudo systemctl status postgresql`
- Review full logs: `journalctl -u auto-trade-api -n 100`

---

## 🔍 Post-Deployment Monitoring

### Step 8: Immediate Health Checks (First 5 Minutes)

Run these checks immediately after restart:

```bash
# Check 1: API health endpoint
curl -s http://localhost:8000/health | python3 -m json.tool

# Check 2: Reconciliation engine status
curl -s http://localhost:8000/api/v1/reconciliation/status | python3 -m json.tool

# Check 3: Verify open positions unchanged
curl -s http://localhost:8000/api/v1/trading/positions | python3 -m json.tool

# Check 4: System circuit breaker status
curl -s http://localhost:8000/api/v1/circuit-breaker/status | python3 -m json.tool
```

**Expected Results:**
- ✅ API health: `{"status": "healthy"}`
- ✅ Reconciliation: `{"is_running": true, "last_run": "...", ...}`
- ✅ Positions: Same count as pre-deployment
- ✅ Circuit breaker: `{"state": "closed", "can_trade": true}`

---

### Step 9: Key Prometheus Metrics to Monitor

Access Prometheus dashboard (typically at `http://localhost:9090`) and monitor these metrics:

#### Critical Metrics (Check Every 5 Minutes Initially)

```promql
# Total reconciliation mismatches detected
reconciliation_mismatches_total{mismatch_type="total"}

# Mismatches by type
reconciliation_mismatches_total{mismatch_type="orphaned"}
reconciliation_mismatches_total{mismatch_type="ghost"}
reconciliation_mismatches_total{mismatch_type="status_diff"}

# Auto-repairs performed
reconciliation_repairs_total{repair_type="auto_repair"}

# Circuit breaker state (0=closed/healthy, 1=open/blocked)
circuit_breaker_state

# API request latency (should be <500ms p95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**Alert Thresholds:**
- ⚠️ `reconciliation_mismatches_total > 5` in 10 minutes → Investigate
- ⚠️ `circuit_breaker_state == 1` → Trading blocked, check API health
- ⚠️ `http_request_duration_seconds{quantile="0.95"} > 1.0` → Performance degradation

---

### Step 10: Telegram Alerts to Expect

You should receive these Telegram notifications (if enabled):

#### During Startup (Expected)
```
🔧 [SYSTEM] Trade State Recovery completed
   Checked: 0 trades
   Recovered: 0
   Failed: 0
```

#### During Normal Operation (Periodic)
Every 2 minutes (based on `RECONCILIATION_INTERVAL_SECONDS`), if mismatches are found:

```
⚠️ [RECONCILIATION] Orphaned Order Detected
   Trade ID: XXXX
   Symbol: XAUUSDT
   Action: Auto-repaired (marked as failed)
```

```
🚨 [RECONCILIATION] Ghost Position Detected
   Symbol: XAUUSDT
   Action: Imported into database
   Requires Review: Yes
```

**Note:** Alert deduplication prevents spam. Same alert type won't repeat within cooldown period.

---

### Step 11: Dashboard Verification

If you have the web dashboard running, verify:

1. **Trading Status Page:**
   - Shows "System Healthy" indicator
   - Displays correct number of open positions
   - Last reconciliation run time visible

2. **Reconciliation Panel:**
   - Shows interval: `120s`
   - Auto-repair: `Enabled`
   - Next run countdown timer

3. **Metrics Panel:**
   - Prometheus graphs rendering
   - Circuit breaker status visible
   - Recent mismatch history

---

## 📊 24-Hour Monitoring Checklist

### Hour 1-2: Intensive Monitoring

- [ ] Check logs every 15 minutes: `journalctl -u auto-trade-api -n 50 --since "15 minutes ago"`
- [ ] Verify reconciliation runs every 2 minutes
- [ ] Confirm no unexpected Telegram alerts
- [ ] Check Prometheus metrics stable
- [ ] Verify open positions unchanged

### Hour 3-6: Regular Monitoring

- [ ] Check logs every hour
- [ ] Review reconciliation stats: `curl http://localhost:8000/api/v1/reconciliation/status`
- [ ] Monitor API latency (<500ms p95)
- [ ] Verify circuit breaker remains closed

### Hour 7-24: Standard Monitoring

- [ ] Check logs every 4 hours
- [ ] Review daily reconciliation summary
- [ ] Verify no performance degradation
- [ ] Check memory usage stable (<2GB per systemd limit)

---

## 🚨 Rollback Instructions

If any issues are detected during deployment, follow these steps immediately:

### Quick Rollback (<2 Minutes)

```bash
# Step 1: Restore .env backup
TIMESTAMP=$(ls -t .env.backup.* | head -1)
echo "Restoring from: $TIMESTAMP"
cp "$TIMESTAMP" .env

# Step 2: Restart services with old configuration
sudo systemctl restart auto-trade-api auto-trade-worker

# Step 3: Verify rollback
sleep 10
sudo systemctl status auto-trade-api auto-trade-worker
curl -s http://localhost:8000/health | python3 -m json.tool
```

### Full Rollback (If Code Issues Detected)

```bash
# Step 1: Stop services
sudo systemctl stop auto-trade-api auto-trade-worker

# Step 2: Restore .env
TIMESTAMP=$(ls -t .env.backup.* | head -1)
cp "$TIMESTAMP" .env

# Step 3: Restore config.py (if modified)
TIMESTAMP=$(ls -t app/config.py.backup.* | head -1)
cp "$TIMESTAMP" app/config.py

# Step 4: Git revert new files (if needed)
git checkout HEAD -- app/execution/state_recovery.py
git checkout HEAD -- app/execution/strategy_interface.py
git checkout HEAD -- app/execution/retry_manager.py
git checkout HEAD -- app/execution/execution_service.py
git checkout HEAD -- app/execution/reconciliation_engine.py

# Step 5: Restart services
sudo systemctl start auto-trade-api auto-trade-worker

# Step 6: Verify system operational
sleep 10
curl -s http://localhost:8000/health | python3 -m json.tool
```

### Rollback Decision Matrix

| Issue Type | Severity | Action |
|------------|----------|--------|
| Services won't start | CRITICAL | Full rollback immediately |
| Open positions changed | CRITICAL | Full rollback + investigate |
| High API latency (>2s) | HIGH | Quick rollback, then investigate |
| Excessive Telegram alerts | MEDIUM | Disable alerts: `RECONCILIATION_TELEGRAM_ALERTS=false` |
| Reconciliation errors | LOW | Keep running, investigate logs |
| Minor log warnings | INFO | No action needed |

---

## 🎯 Success Criteria

Deployment is considered successful when:

### Immediate (First Hour)
- ✅ All services running without errors
- ✅ Reconciliation engine executing every 120 seconds
- ✅ No unexpected position changes
- ✅ Circuit breaker remains closed
- ✅ API latency <500ms p95

### Short-Term (24 Hours)
- ✅ Zero duplicate orders placed
- ✅ State recovery completes cleanly on any restart
- ✅ Reconciliation detects and repairs mismatches automatically
- ✅ Telegram alerts working but not excessive (<10/day)
- ✅ Prometheus metrics collecting correctly
- ✅ Memory usage stable (<2GB)

### Long-Term (7 Days)
- ✅ No phantom trades or ghost positions
- ✅ Database-exchange consistency maintained
- ✅ Performance impact <5% vs baseline
- ✅ All crash recovery scenarios tested successfully
- ✅ Strategy interface ready for new strategy development

---

## 📞 Support & Troubleshooting

### Common Issues

**Issue 1: Services won't start after deployment**
```bash
# Check logs
journalctl -u auto-trade-api -n 100 --no-pager

# Common causes:
# - Redis not running: sudo systemctl start redis
# - PostgreSQL not running: sudo systemctl start postgresql
# - Syntax error in .env: Review recent changes
```

**Issue 2: Reconciliation engine not running**
```bash
# Check status
curl http://localhost:8000/api/v1/reconciliation/status

# Check logs
journalctl -u auto-trade-worker -n 50 | grep -i reconcil

# Verify configuration
python3 -c "from app.config import settings; print(f'Interval: {settings.RECONCILIATION_INTERVAL_SECONDS}')"
```

**Issue 3: Too many Telegram alerts**
```bash
# Temporarily disable alerts
echo "RECONCILIATION_TELEGRAM_ALERTS=false" >> .env
sudo systemctl restart auto-trade-worker

# Or increase orphaned age threshold
echo "RECONCILIATION_MAX_ORPHANED_AGE_HOURS=48" >> .env
sudo systemctl restart auto-trade-worker
```

**Issue 4: State recovery marking valid trades as failed**
```bash
# Check recovery logs
journalctl -u auto-trade-api | grep -i "RECOVERY"

# Review affected trades
curl http://localhost:8000/api/v1/trading/positions | python3 -m json.tool

# Manual fix if needed (contact support)
```

### Emergency Contacts

- **System Administrator:** [Your contact info]
- **Trading Operations:** [Your contact info]
- **Technical Support:** [Your contact info]

---

## 📝 Deployment Sign-Off

**Pre-Deployment Checklist:**
- [ ] Verification script passed
- [ ] Current state documented
- [ ] Backups created
- [ ] Configuration updated
- [ ] Team notified

**Post-Deployment Checklist:**
- [ ] Services running
- [ ] Health checks passing
- [ ] Reconciliation engine operational
- [ ] Prometheus metrics collecting
- [ ] Telegram alerts configured
- [ ] 24-hour monitoring plan in place

**Deployment Completed By:** _______________  
**Date/Time:** _______________  
**Next Review:** 24 hours after deployment

---

## 📚 Related Documentation

- [EXECUTION_LAYER_OPTIMIZATION_PLAN.md](EXECUTION_LAYER_OPTIMIZATION_PLAN.md) - Detailed technical plan
- [FREQTRADE_INTEGRATION_DEPLOYMENT_GUIDE.md](FREQTRADE_INTEGRATION_DEPLOYMENT_GUIDE.md) - General deployment guide
- [PHASE1_ISSUE_B_IMPLEMENTATION.md](PHASE1_ISSUE_B_IMPLEMENTATION.md) - Reconciliation engine details
- [PHASE1_STATUS_REPORT.md](PHASE1_STATUS_REPORT.md) - Overall Phase 1 status
- [FREQTRADE_QUICKREF.md](FREQTRADE_QUICKREF.md) - Quick reference card

---

**Last Updated:** 2026-05-15  
**Document Version:** 1.0  
**Status:** Ready for Deployment
