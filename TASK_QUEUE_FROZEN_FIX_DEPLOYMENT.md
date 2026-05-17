# Task Queue Frozen Fix - Deployment Guide

## Quick Start

### 1. Verify Changes Are in Place

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system

# Check that all files have been modified
grep -l "record_task_processed" app/worker_gold_bot.py app/execution/trading_service.py app/main.py
```

Expected output: All three files should be listed.

### 2. Restart the Application

**Option A: Using systemd (Recommended)**

```bash
# Restart the main application
sudo systemctl restart auto-trade-system

# Check status
sudo systemctl status auto-trade-system

# View logs
sudo journalctl -u auto-trade-system -f
```

**Option B: Manual Restart**

```bash
# Stop current processes
pkill -f "uvicorn app.main"
pkill -f "worker_gold_bot"

# Wait for clean shutdown
sleep 3

# Start main application
cd /home/admin/.openclaw/workspace/auto-trade-system
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/uvicorn.log 2>&1 &

# Start worker (if using separate worker process)
nohup .venv/bin/python -m app.worker_gold_bot > logs/worker.log 2>&1 &
```

### 3. Verify Deployment

Check initialization logs:

```bash
# Look for QueueWatchdog initialization messages
tail -100 logs/uvicorn.log | grep -i "queue.*watchdog"
tail -100 logs/worker.log | grep -i "queue.*watchdog"
```

Expected log messages:
```
✅ Queue Watchdog initialized
✅ Global QueueWatchdog initialized for background workers
✅ Queue watchdog integrated for task processing tracking
```

### 4. Monitor for False Alerts

**Before Fix:**
- ❌ Telegram alerts every 5 minutes: "Task Queue Frozen"
- ❌ Frozen checks counter incrementing (76, 91, etc.)

**After Fix:**
- ✅ No false "frozen" alerts during normal operation
- ✅ Alerts only trigger if system actually freezes

### 5. Health Check Endpoint

Verify queue health via API:

```bash
curl http://localhost:8000/health/deep | jq '.watchdogs.queue'
```

Expected response when healthy:
```json
{
  "status": "healthy",
  "seconds_since_last_task": < 300,
  "last_task_processed": "2026-05-17T..."
}
```

## Troubleshooting

### Issue: Still Getting Frozen Alerts

**Check 1: Is the application running?**
```bash
ps aux | grep -E "(uvicorn|worker_gold_bot)" | grep -v grep
```

**Check 2: Are background loops executing?**
```bash
tail -50 logs/worker.log | grep -i "scanning\|heartbeat\|reconciliation"
```

**Check 3: Check QueueWatchdog state**
```python
# Run this in Python console
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')
from app.main import state

if state.queue_watchdog:
    print(f"Last task processed: {state.queue_watchdog.last_task_processed_time}")
    print(f"Current time: {datetime.utcnow()}")
```

### Issue: Application Won't Start

**Check logs for errors:**
```bash
tail -100 logs/uvicorn.log
tail -100 logs/worker.log
```

**Common issues:**
- Import errors: Make sure all dependencies are installed
- Syntax errors: Run `python -m py_compile app/main.py` to check
- Port conflicts: Ensure port 8000 is not in use

### Issue: Import Errors

If you see `ImportError: cannot import name 'QueueWatchdog'`:

```bash
# Verify the file exists
ls -la app/self_healing/watchdogs.py

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Test import directly
python -c "from app.self_healing.watchdogs import QueueWatchdog; print('OK')"
```

## Rollback Plan

If you need to rollback the changes:

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system

# If using git
git checkout HEAD -- app/worker_gold_bot.py app/execution/trading_service.py app/main.py

# Restart application
sudo systemctl restart auto-trade-system
```

## Monitoring Checklist

After deployment, monitor for 24 hours:

- [ ] No false "Task Queue Frozen" Telegram alerts
- [ ] Application logs show regular task processing
- [ ] Health endpoint shows queue status as "healthy"
- [ ] Background workers are running (check process list)
- [ ] Trading cycles execute normally (if during trading hours)

## Expected Behavior

### Normal Operation

With the fix in place, you should see:

1. **Regular Log Messages:**
   ```
   Scanning for gold reversal signals...
   Heartbeat: uptime=1234s, trading=True, tasks=5
   Session update: trading=True, session=LONDON
   ```

2. **No False Alerts:**
   - Telegram should NOT receive "Task Queue Frozen" alerts during normal operation
   - Alerts will ONLY trigger if the system genuinely stops processing tasks for >5 minutes

3. **Health Endpoint:**
   ```json
   {
     "overall_status": "healthy",
     "watchdogs": {
       "queue": {
         "status": "healthy",
         "seconds_since_last_task": 15.23,
         "frozen_worker_alerts": 0
       }
     }
   }
   ```

### Actual Freeze Detection

If the system truly freezes (e.g., crashes, hangs), the alert WILL still trigger:

```
🚨 TASK QUEUE APPEARS FROZEN: No tasks processed in 305s (threshold: 300s)
🚨 QUEUE FROZEN: No tasks processed in 1 consecutive checks
```

This is the CORRECT behavior - we want alerts for real problems, not false positives.

## Configuration Tuning

If you want to adjust the sensitivity:

Edit `.env` file:

```bash
# How often to check queue health (default: 60 seconds)
QUEUE_WATCHDOG_CHECK_INTERVAL_SEC=60

# Alert threshold (default: 300 seconds = 5 minutes)
# Increase if you get false alerts during slow periods
QUEUE_WATCHDOG_MAX_TASK_AGE_SEC=300

# Maximum queue depth before alerting (future feature)
QUEUE_WATCHDOG_MAX_QUEUE_DEPTH=100
```

After changing `.env`, restart the application.

## Support

If you encounter issues:

1. Check logs: `tail -f logs/uvicorn.log logs/worker.log`
2. Review documentation: `TASK_QUEUE_FROZEN_FIX.md`
3. Run verification script: `python scripts/verify_queue_watchdog_fix.py`
4. Check health endpoint: `curl http://localhost:8000/health/deep`

---

**Deployment Date:** May 17, 2026  
**Fix Version:** 1.0  
**Status:** Ready for Production
