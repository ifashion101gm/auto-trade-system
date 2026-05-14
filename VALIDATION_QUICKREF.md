# Paper Trading Validation - Quick Reference Card

## 🎯 Current Status (as of 2026-05-14 06:00 UTC)

| Component | Status | Details |
|-----------|--------|---------|
| **Application** | ✅ RUNNING | PID: 1270062, Uptime: 53+ min |
| **Health API** | ✅ HEALTHY | http://localhost:8000/health |
| **Position Sync** | ✅ OPERATIONAL | Every 5 seconds, "All consistent" |
| **Telegram Bot** | ✅ WORKING | Bot: Aung.pro, Channel: AG trade report |
| **Execution Mode** | 📝 PAPER | Safe mode active |
| **Errors Since Restart** | ✅ ZERO | Clean since 05:07 UTC |
| **Validation Progress** | ⏳ 6min / 24h | ~23h 54min remaining |

---

## 🚀 Quick Commands

### Instant Status Check
```bash
./scripts/validation_dashboard.sh
```

### Detailed Validation Status
```bash
./scripts/check_validation_status.sh
```

### Telegram Health Check
```bash
./scripts/check_telegram_health.sh
```

### Real-Time Log Monitoring
```bash
# All logs with errors and position sync
tail -f logs/all_2026-05-14.log | grep -E '(ERROR|Position sync)'

# Position sync only
tail -f logs/all_2026-05-14.log | grep "Position sync"

# Errors only
tail -f logs/error_2026-05-14.log
```

### Application Control
```bash
# Check if running
ps aux | grep "uvicorn app.main:app"

# Stop application
pkill -f "uvicorn app.main:app"

# Start application
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/trading_app.log 2>&1 &
```

---

## 📅 Validation Timeline

- **Started**: 2026-05-14 05:07 UTC
- **Current**: 2026-05-14 06:00 UTC (6 minutes elapsed)
- **24h Target**: 2026-05-15 05:07 UTC (~23h 54min remaining)
- **48h Goal**: 2026-05-16 05:07 UTC

---

## ✅ Success Criteria

### Minimum (24 Hours)
- [x] Zero critical errors (async_generator, AttributeError)
- [x] Position sync operational
- [x] Health endpoint responding
- [x] Telegram notifications working
- [ ] 24+ hours continuous uptime ⏳
- [ ] Stable WebSocket connection
- [ ] No reconciliation mismatches

### Extended (48 Hours - Recommended)
- [ ] 48+ hours continuous uptime
- [ ] Consistent "All consistent" sync messages
- [ ] Zero unplanned restarts
- [ ] No performance degradation

---

## 🔧 Fixes Applied

1. **Async Generator Misuse** → Fixed in `position_sync.py` and `main.py`
2. **BybitConnector Methods** → Corrected to `fetch_open_positions` and `get_positions`
3. **Execution Mode** → Changed to `paper` for safety

---

## 🚨 Emergency Protocol

If critical errors detected:

1. **Stop**: `pkill -f "uvicorn app.main:app"`
2. **Check**: `tail -100 logs/error_$(date +%Y-%m-%d).log`
3. **Fix**: Resolve identified issue
4. **Restart**: Start application again
5. **Reset**: Delete `/tmp/validation_start_time` and restart monitoring

---

## 📞 Monitoring Scripts

| Script | Purpose | Frequency |
|--------|---------|-----------|
| `monitor_paper_validation.sh` | Continuous auto-monitor | Every 5 min (background) |
| `validation_dashboard.sh` | Quick status overview | Every 4-6 hours |
| `check_validation_status.sh` | Detailed diagnostics | As needed |
| `check_telegram_health.sh` | Telegram system check | As needed |

---

## 📊 Key Files

- **Logs**: `logs/all_2026-05-14.log`, `logs/error_2026-05-14.log`
- **Config**: `.env` (EXECUTION_MODE=paper)
- **Documentation**: 
  - `PAPER_TRADING_VALIDATION_PLAN.md` - Full procedure
  - `VALIDATION_STATUS_REPORT.md` - Current status
  - `VALIDATION_QUICKREF.md` - This file

---

## 🎯 After 24 Hours

1. Review entire validation period logs
2. Confirm zero critical errors
3. Update `.env`: `EXECUTION_MODE=fully-auto`
4. Restart application
5. Monitor first hour closely
6. Execute demo trade cycle ($100 objective)

---

*Last updated: 2026-05-14 06:00 UTC*
