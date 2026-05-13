# Paper Trading Validation Cycle - 24-48 Hour Plan

## 📋 Overview

This document outlines the validation cycle to verify system stability before transitioning from `paper` mode to `fully-auto` mode for the $100 Bybit Demo trading objective.

**Start Time**: 2026-05-14 05:07 UTC  
**Target Duration**: 24-48 hours  
**Current Mode**: `paper` (safe mode)  
**Target Mode**: `fully-auto` (after validation)

---

## ✅ Fixes Applied (Pre-Validation)

### 1. Async Generator Misuse Fixed
- **File**: `app/sync/position_sync.py`, `app/main.py`
- **Issue**: Using `async with get_session()` instead of `async for db_session in get_session()`
- **Status**: ✅ RESOLVED

### 2. BybitConnector Method Name Fixed
- **File**: `app/exchange/bybit_connector.py` line 388
- **Issue**: Calling `self.client.fetch_positions` instead of `self.client.fetch_open_positions`
- **Status**: ✅ RESOLVED

### 3. Position Sync Method Calls Fixed
- **File**: `app/sync/position_sync.py` lines 162, 487
- **Issue**: Calling `get_open_positions()` instead of `get_positions()`
- **Status**: ✅ RESOLVED

### 4. Safety Lock Applied
- **File**: `.env`
- **Change**: `EXECUTION_MODE=paper` (prevents live trading during validation)
- **Status**: ✅ ACTIVE

---

## 🎯 Validation Objectives

### Primary Goals
1. **Zero Critical Errors**: No `position_sync` errors, async generator issues, or AttributeError exceptions
2. **Stable Position Sync**: Continuous successful synchronization every 5 seconds
3. **Bybit Connectivity**: Stable WebSocket connection to Bybit Demo API
4. **Database Consistency**: No reconciliation mismatches between DB and exchange

### Success Criteria
- ✅ Application uptime ≥ 24 hours without restart
- ✅ Position sync running successfully (logs show "All consistent")
- ✅ Zero new critical errors in logs after fixes applied
- ✅ Health endpoint responding: `{"status":"healthy","version":"2.0.0"}`
- ✅ WebSocket connected to Bybit Demo (`api-demo.bybit.com`)

---

## 📊 Monitoring Tools

### 1. Quick Status Check
```bash
./scripts/check_validation_status.sh
```
Run this anytime for instant status report.

### 2. Continuous Monitor (Background)
```bash
nohup ./scripts/monitor_paper_validation.sh > /tmp/validation_monitor.log 2>&1 &
```
Runs automated checks every 5 minutes for 24 hours.

### 3. Manual Log Checks
```bash
# Recent position sync activity
tail -50 logs/all_$(date +%Y-%m-%d).log | grep "Position sync"

# Error check
tail -100 logs/error_$(date +%Y-%m-%d).log | grep -E "(position_sync|async_generator)"

# Application logs
tail -100 /tmp/trading_app.log | grep -E "(ERROR|INFO.*started)"
```

---

## ⏱️ Validation Timeline

### Phase 1: Initial Stability (Hours 0-2)
- [x] System startup successful
- [x] All fixes applied
- [x] Position sync operational
- [ ] Monitor for any immediate errors
- [ ] Verify WebSocket reconnection handling

### Phase 2: Extended Monitoring (Hours 2-24)
- [ ] Continuous position sync without errors
- [ ] No database connection issues
- [ ] Stable Bybit API connectivity
- [ ] No memory leaks or resource exhaustion
- [ ] Reconciliation loop running every 2 minutes

### Phase 3: Final Verification (Hour 24)
- [ ] Run comprehensive status check
- [ ] Review all logs for edge cases
- [ ] Verify zero critical errors
- [ ] Confirm position sync health
- [ ] Prepare transition to fully-auto

### Phase 4: Optional Extended Validation (Hours 24-48)
- [ ] Continue monitoring if desired
- [ ] Test under different market conditions
- [ ] Verify behavior during volatility

---

## 🔄 Transition Plan: Paper → Fully-Auto

### Pre-Transition Checklist
Before switching to `fully-auto`, verify:
- [ ] Validation cycle completed (≥24 hours)
- [ ] Zero critical errors in last 24 hours
- [ ] Position sync showing "All consistent" regularly
- [ ] Bybit WebSocket stable
- [ ] Database healthy
- [ ] Health endpoint responding

### Transition Steps

#### Step 1: Stop Application
```bash
pkill -f "uvicorn app.main:app"
sleep 2
```

#### Step 2: Update Configuration
Edit `.env` file:
```bash
# Change this line:
EXECUTION_MODE=paper

# To this:
EXECUTION_MODE=fully-auto
```

Or use command:
```bash
sed -i 's/^EXECUTION_MODE=paper$/EXECUTION_MODE=fully-auto/' .env
```

#### Step 3: Verify Configuration
```bash
grep "^EXECUTION_MODE=" .env
# Should output: EXECUTION_MODE=fully-auto
```

#### Step 4: Restart Application
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/trading_app.log 2>&1 &
echo "Application restarted with PID: $!"
```

#### Step 5: Verify Startup
Wait 30 seconds, then check:
```bash
curl http://localhost:8000/health
tail -50 /tmp/trading_app.log | grep -E "(started|ERROR)"
```

#### Step 6: Monitor First Hour
Critical monitoring period - watch for:
- Position sync errors
- Trade execution issues
- Risk management triggers
- Telegram notifications

---

## 🚨 Emergency Procedures

### If Critical Errors Detected During Validation

1. **Stop Monitoring**
   ```bash
   pkill -f "monitor_paper_validation"
   ```

2. **Check Error Details**
   ```bash
   tail -200 logs/error_$(date +%Y-%m-%d).log
   tail -200 /tmp/trading_app.log | grep ERROR
   ```

3. **Restart if Needed**
   ```bash
   pkill -f "uvicorn app.main:app"
   sleep 2
   # Then restart using start_services.sh or manual commands
   ```

4. **Extend Validation**
   - Reset 24-hour timer after fix
   - Document the issue and resolution
   - Continue monitoring

### If System Crashes

1. Check logs for root cause
2. Fix underlying issue
3. Restart application
4. **Reset validation timer** - must run 24 hours continuously

---

## 📈 Expected Behavior During Validation

### Normal Logs (Good Signs)
```
✅ Position sync: All consistent
🔄 Running position sync cycle...
Exchange positions: 0 (set())
Database positions: 0 (set())
✅ Bybit DEMO connected with WebSocket streams
🔄 State synced: 0 positions, 0 open orders
```

### Warning Signs (Investigate)
```
❌ Position sync error: ...
⚠️  Database connection issue during sync
Failed to fetch exchange positions: ...
WebSocket disconnected
```

### Critical Errors (Stop & Fix)
```
AttributeError: 'BybitConnector' object has no attribute ...
async_generator object does not support the asynchronous context manager protocol
Connection refused (Errno 111)
```

---

## 📝 Validation Log Template

Use this template to log observations:

```
Date: 2026-05-14
Time: HH:MM UTC
Uptime: X hours Y minutes

Status:
- Application: ✅ Running / ❌ Down
- Health Endpoint: ✅ Healthy / ❌ Unhealthy
- Position Sync: ✅ Operational / ❌ Errors
- Bybit WS: ✅ Connected / ❌ Disconnected
- Errors Last Hour: 0 / X count

Observations:
[Any notable events, warnings, or issues]

Action Required:
[Yes/No - if yes, describe]
```

---

## 🎉 Post-Validation: $100 Objective Execution

Once validated and switched to `fully-auto`:

### System Will Automatically:
1. Monitor Bybit Demo account (starting balance: ~$100 USDT)
2. Execute Gold futures trades based on AI signals
3. Track positions with 5-second sync intervals
4. Enforce risk limits (max leverage 3x, 0.5% risk per trade)
5. Send Telegram notifications for all trades

### Success Metrics:
- **Goal**: Grow demo account by $100 profit
- **Risk**: Max 0.5% per trade, 3x leverage max
- **Symbol**: XAU/USDT:USDT (Gold perpetual swap)
- **Mode**: Fully automatic execution

### Monitoring:
- Dashboard: http://localhost:8000/docs
- Metrics: http://localhost:8000/metrics/prometheus
- Telegram: Real-time trade notifications
- Logs: `/home/admin/.openclaw/workspace/auto-trade-system/logs/`

---

## 📞 Support & Troubleshooting

### Common Issues

**Q: Position sync shows errors after restart**  
A: Wait 2-3 minutes for full initialization. If persists, check Bybit API credentials.

**Q: WebSocket keeps disconnecting**  
A: Check network connectivity. System auto-reconnects with exponential backoff.

**Q: Database connection refused**  
A: Ensure PostgreSQL Docker container is running: `docker compose ps`

**Q: How to check current execution mode?**  
A: Run `./scripts/check_validation_status.sh` or `grep EXECUTION_MODE .env`

### Contact & Resources
- Project Docs: `/home/admin/.openclaw/workspace/auto-trade-system/README.md`
- Bybit Skills: Review official Bybit integration patterns
- Logs Directory: `logs/` (all_*.log, error_*.log, trades_*.log)

---

## ✅ Validation Completion Certificate

When validation completes successfully, fill this out:

```
VALIDATION CYCLE COMPLETE
=========================
Start Time: 2026-05-14 05:07 UTC
End Time: [Fill in]
Duration: [Fill in] hours

Results:
- Total Uptime: [Fill in]
- Critical Errors: [Should be 0]
- Position Sync Success Rate: [Should be ~100%]
- Bybit Connectivity: [Stable/Unstable]

Decision:
☐ APPROVED for fully-auto transition
☐ REJECTED - Issues found, extend validation

Approved By: _________________
Date: _________________
```

---

**Last Updated**: 2026-05-14 05:30 UTC  
**Status**: VALIDATION IN PROGRESS  
**Next Check**: Run `./scripts/check_validation_status.sh` anytime
