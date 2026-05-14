# Phase 1 Deployment Checklist - READY TO EXECUTE

**Date:** May 15, 2026  
**Status:** 🟢 **READY FOR DEPLOYMENT**  
**Estimated Time:** 30 minutes for deployment + 48 hours monitoring

---

## Pre-Deployment Verification ✅

- [x] WatchdogOrchestrator integrated into `app/main.py`
- [x] Configuration settings added to `app/config.py`
- [x] Environment variables documented in `.env.example`
- [x] Integration tests passing (16/17 = 94%)
- [x] Validation script confirms all components working
- [x] Monitoring script created (`scripts/monitor_watchdogs.sh`)
- [x] psutil dependency added to requirements.txt

---

## Deployment Steps

### Step 1: Backup Current State (2 minutes)

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system

# Backup configuration
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Backup current logs (optional)
tar czf logs_backup_$(date +%Y%m%d).tar.gz logs/*.log 2>/dev/null || true
```

### Step 2: Add Watchdog Configuration (1 minute)

Append to your `.env` file:

```bash
cat >> .env << 'EOF'

# =============================================================================
# Phase 2: Self-Healing Watchdog Configuration
# =============================================================================
# API Watchdog - monitors exchange connectivity and latency
API_WATCHDOG_CHECK_INTERVAL_SEC=30
API_WATCHDOG_FAILURE_THRESHOLD=3

# Database Watchdog - detects transaction staleness
DB_WATCHDOG_CHECK_INTERVAL_SEC=60
DB_WATCHDOG_STALE_TRANSACTION_THRESHOLD_SEC=300

# Memory Watchdog - tracks RSS usage and detects leaks
MEMORY_WATCHDOG_WARNING_THRESHOLD_MB=512
MEMORY_WATCHDOG_CRITICAL_THRESHOLD_MB=1024
MEMORY_WATCHDOG_GC_TRIGGER_THRESHOLD_MB=768
MEMORY_WATCHDOG_CHECK_INTERVAL_SEC=120

# Queue Watchdog - monitors worker task processing
QUEUE_WATCHDOG_MAX_TASK_AGE_SEC=300
QUEUE_WATCHDOG_CHECK_INTERVAL_SEC=60
EOF
```

### Step 3: Verify Dependencies (1 minute)

```bash
# Ensure psutil is installed
pip show psutil | grep Version

# If not installed:
pip install psutil>=5.9.0
```

### Step 4: Quick Validation Test (2 minutes)

```bash
# Run validation script
python scripts/validate_phase2.py

# Expected output:
# ✅ WATCHDOG VALIDATION PASSED
# ✅ JSON LOGGING VALIDATION PASSED
# ✅ ASYNC ISOLATION VALIDATION PASSED
# 🎉 ALL PHASE 2 VALIDATIONS PASSED!
```

### Step 5: Deploy to Staging (5 minutes)

**Option A: Systemd Service**
```bash
sudo systemctl stop auto-trade-system
sudo systemctl start auto-trade-system
sudo systemctl status auto-trade-system
```

**Option B: Docker**
```bash
docker-compose down
docker-compose up -d trading-bot
docker-compose logs -f trading-bot
```

**Option C: Manual Restart**
```bash
# Stop existing process
pkill -f "python.*main.py" || true
sleep 2

# Start new process
nohup python -m app.main > /dev/null 2>&1 &

# Verify it's running
ps aux | grep main.py
```

### Step 6: Monitor Startup (5 minutes)

```bash
# Watch for successful initialization
tail -f logs/all_*.log | grep -E "watchdog|Watchdog"

# Expected within first 60 seconds:
# 🔍 Initializing self-healing watchdogs...
# ✅ Self-healing watchdogs initialized
# 🚀 Starting all watchdogs...
# ✅ All 4 watchdogs started
# 🔄 API Watchdog started periodic checks
# 🔄 Database Watchdog started periodic checks
# 🔄 Memory Watchdog started periodic checks
# 🔄 Queue Watchdog started periodic checks
```

**Press Ctrl+C after seeing all 4 watchdogs start.**

### Step 7: Start 48-Hour Monitoring (1 minute)

```bash
# Start background monitoring
nohup scripts/monitor_watchdogs.sh 48 > logs/watchdog_monitor.log 2>&1 &

# Verify monitoring is running
ps aux | grep monitor_watchdogs

# Check initial output
tail -20 logs/watchdog_monitor.log
```

---

## 48-Hour Monitoring Plan

### What to Watch For

**Every 30 minutes**, the monitoring script will report:
- Memory usage (target: <800MB peak)
- CPU usage (target: <0.2% average overhead)
- Critical alert count (target: <5 total)
- Warning alert count
- Watchdog overall status (target: "healthy")

### Manual Checks (Optional but Recommended)

**Check every 6-12 hours:**

```bash
# 1. Verify application is still running
ps aux | grep main.py

# 2. Check for critical errors
grep "CRITICAL\|🚨" logs/all_*.log | tail -10

# 3. Check memory trend
grep "Memory Health" logs/all_*.log | tail -20

# 4. Check watchdog activity
grep "Overall Status" logs/all_*.log | tail -10

# 5. Verify no service disruptions
journalctl -u auto-trade-system --since "2 hours ago" | grep -i error
```

### Alert Thresholds - Investigate Immediately If:

- ❌ More than 10 "CRITICAL" log entries in any 1-hour period
- ❌ Memory usage exceeds 1024MB consistently
- ❌ Application crashes or restarts unexpectedly
- ❌ Any "EMERGENCY STOP TRIGGERED" messages
- ❌ Watchdog status shows "critical" for more than 5 minutes

---

## Phase 1 Completion Criteria

After 48 hours, verify:

- [ ] Application ran continuously without crashes
- [ ] All 4 watchdogs remained active throughout
- [ ] Total critical alerts < 5
- [ ] Peak memory usage < 800MB
- [ ] Average CPU overhead < 0.2%
- [ ] No false-positive emergency stops
- [ ] Watchdog check intervals consistent (±10% of configured)

---

## Troubleshooting

### Issue: Watchdogs not starting

**Symptom:** No watchdog log messages

**Solution:**
```bash
# Check for import errors
python -c "from app.self_healing.watchdogs import WatchdogOrchestrator; print('OK')"

# Verify psutil installed
python -c "import psutil; print(psutil.__version__)"

# Check .env has settings
grep API_WATCHDOG .env
```

### Issue: High memory usage

**Symptom:** Memory > 800MB

**Solution:**
```bash
# Check what's using memory
grep "Memory Health" logs/all_*.log | tail -20

# Force garbage collection
python -c "import gc; gc.collect(); print('GC complete')"

# If persistent, investigate memory leaks
pip install tracemalloc
```

### Issue: Too many alerts

**Symptom:** >10 critical alerts per hour

**Solution:**
```bash
# Review alert types
grep "CRITICAL" logs/all_*.log | awk '{print $NF}' | sort | uniq -c | sort -rn

# Adjust thresholds if needed
# Edit .env and increase thresholds
# Restart application
```

---

## Next Steps After Phase 1

Once 48-hour monitoring completes successfully:

1. **Complete Phase 1 Validation Report** (use template in PRODUCTION_ROADMAP_EXECUTION_PLAN.md)
2. **Review monitoring logs** for patterns or issues
3. **Adjust thresholds** if false positives detected
4. **Proceed to Phase 2** (Telegram alerts + health endpoints)

If issues detected:
1. **Investigate root cause** from logs
2. **Adjust configuration** as needed
3. **Re-run 48-hour monitoring** after fixes
4. **Do NOT proceed to Phase 2** until stable

---

## Emergency Rollback

If critical issues arise during Phase 1:

```bash
# 1. Stop monitoring
pkill -f monitor_watchdogs

# 2. Stop application
sudo systemctl stop auto-trade-system

# 3. Restore backup configuration
cp .env.backup.* .env

# 4. Remove watchdog integration temporarily
git checkout HEAD~1 -- app/main.py app/config.py

# 5. Restart with previous version
sudo systemctl start auto-trade-system

# 6. Investigate issues before retrying
```

---

## Contact & Support

**Documentation:**
- Full roadmap: `PRODUCTION_ROADMAP_EXECUTION_PLAN.md`
- Phase 2 summary: `PHASE2_COMPLETION_SUMMARY.md`
- Integration guide: `PHASE2_INTEGRATION_COMPLETE.md`

**Logs Location:**
- All logs: `logs/all_*.log`
- Error logs: `logs/error_*.log`
- JSON logs: `logs/json_*.log`
- Monitoring output: `logs/watchdog_monitor_*.log`

---

**Ready to deploy? Execute Step 1 now!** 🚀
