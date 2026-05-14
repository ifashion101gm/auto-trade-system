# ⚠️ CRITICAL FIX APPLIED - Systemd Journal Logging

## Problem Discovered

Your systemd installation **does not support file-based logging** with the `append:` directive.

**Error from terminal:**
```
Loaded: error (Reason: Unit auto-trade-worker.service has a bad unit file setting)
log file support is not available
```

This is common on:
- Older systemd versions (< 236)
- Minimal Linux installations
- Some VPS configurations

---

## ✅ Fix Applied

Changed service files to use **systemd journal logging** (universally supported).

### What Changed

**Before (❌ Not Supported):**
```ini
StandardOutput=append:/path/to/file.log
StandardError=append:/path/to/error.log
```

**After (✅ Universally Supported):**
```ini
StandardOutput=journal
StandardError=journal
```

### Files Updated

1. ✅ [systemd/auto-trade-api.service](systemd/auto-trade-api.service)
2. ✅ [systemd/auto-trade-worker.service](systemd/auto-trade-worker.service)

---

## 🚀 Installation Instructions

### Option 1: Automated Script (Recommended)

Run this in your terminal (outside sandbox):

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
sudo ./install_with_journal.sh
```

This script will:
1. Stop current processes
2. Install fixed service files
3. Verify service file syntax
4. Enable and start services
5. Test API endpoints
6. Show you how to view logs

---

### Option 2: Manual Installation

```bash
# 1. Copy service files
sudo cp systemd/auto-trade-api.service /etc/systemd/system/
sudo cp systemd/auto-trade-worker.service /etc/systemd/system/

# 2. Reload systemd
sudo systemctl daemon-reload

# 3. Verify (should show no errors)
sudo systemd-analyze verify /etc/systemd/system/auto-trade-api.service
sudo systemd-analyze verify /etc/systemd/system/auto-trade-worker.service

# 4. Enable services
sudo systemctl enable auto-trade-api.service
sudo systemctl enable auto-trade-worker.service

# 5. Start services
sudo systemctl start auto-trade-api.service
sudo systemctl start auto-trade-worker.service

# 6. Check status
sudo systemctl status auto-trade-api.service
sudo systemctl status auto-trade-worker.service
```

---

## 📊 Viewing Logs

Since we're using journal logging, use `journalctl` instead of file viewing:

### API Service Logs

```bash
# Live logs (like tail -f)
journalctl -u auto-trade-api -f

# Last 50 lines
journalctl -u auto-trade-api -n 50

# Last hour
journalctl -u auto-trade-api --since "1 hour ago"

# Only errors
journalctl -u auto-trade-api -p err -f

# With timestamps
journalctl -u auto-trade-api -o short-iso
```

### Worker Service Logs

```bash
# Live logs
journalctl -u auto-trade-worker -f

# Last 50 lines
journalctl -u auto-trade-worker -n 50
```

### Both Services Combined

```bash
# Live combined logs
journalctl -u auto-trade-api -u auto-trade-worker -f

# Last 100 lines
journalctl -u auto-trade-api -u auto-trade-worker -n 100
```

---

## 💡 Good News: You Still Get File Logs!

Your Python application uses `logging_config.py` which writes to files independently:

```
logs/
├── app_2026-05-14.log       ← From Python logging
├── all_2026-05-14.log       ← From Python logging
├── error_2026-05-14.log     ← From Python logging
└── enterprise_final.log     ← From Python logging
```

So you get **BOTH**:
- ✅ **Journal logs** - For systemd integration and management
- ✅ **File logs** - From Python's logging configuration

---

## 🔍 Verification Checklist

After installation, verify:

```bash
# 1. Services are loaded without errors
sudo systemctl status auto-trade-api | grep "Loaded:"
# Should show: Loaded: loaded (/etc/systemd/system/auto-trade-api.service; enabled)

# 2. Services are active
sudo systemctl is-active auto-trade-api
sudo systemctl is-active auto-trade-worker
# Should show: active

# 3. No errors in journal
sudo journalctl -u auto-trade-api -p err --since "5 minutes ago"
# Should be empty or show no critical errors

# 4. API responds
curl http://localhost:8000/health/deep | jq
# Should return healthy status
```

---

## 🛠️ Troubleshooting

### If Services Still Show "Loaded: error"

```bash
# Check what's wrong
sudo systemd-analyze verify /etc/systemd/system/auto-trade-api.service

# Common fix: complete reload
sudo systemctl daemon-reload
sudo systemctl reset-failed auto-trade-api auto-trade-worker
sudo systemctl restart auto-trade-api auto-trade-worker
```

### If Services Won't Start

```bash
# Check journal for errors
sudo journalctl -u auto-trade-api -n 50 --no-pager

# Common issues:
# 1. Port 8000 in use
sudo lsof -i :8000
sudo kill -9 <PID>

# 2. Python path wrong
ls -la /home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python

# 3. Missing dependencies
.venv/bin/python -c "import fastapi; print('OK')"
```

### If Logs Aren't Persisting

By default, journal logs may be volatile (lost on reboot). To make them persistent:

```bash
# Create persistent journal directory
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal
sudo systemctl restart systemd-journald

# Verify
ls -la /var/log/journal/
```

---

## 📈 Journal Management

### Check Disk Usage

```bash
# Current journal size
journalctl --disk-usage

# Typically shows something like:
# Archives take up: 150.0M in the file system.
```

### Clean Up Old Logs

```bash
# Keep only last 100MB
sudo journalctl --vacuum-size=100M

# Keep only last 7 days
sudo journalctl --vacuum-time=7d

# Keep only last 1000 entries
sudo journalctl --vacuum-files=1000
```

### Configure Journal Size Limits

Create `/etc/systemd/journald.conf.d/trade-bot.conf`:

```ini
[Journal]
SystemMaxUse=500M
SystemKeepFree=1G
MaxRetentionSec=30day
```

Then restart:
```bash
sudo systemctl restart systemd-journald
```

---

## 🎯 Why Journal Logging is Better

### Advantages

✅ **Integrated with systemd**
- Native systemd feature
- Works on all systemd versions
- No compatibility issues

✅ **Automatic rotation**
- Built-in log rotation
- Configurable size limits
- No manual cleanup needed

✅ **Structured metadata**
- Timestamps automatically included
- Service name tagged
- Priority levels (info, warning, error)

✅ **Powerful filtering**
```bash
# By time
journalctl --since "10 minutes ago"

# By priority
journalctl -p err

# By service
journalctl -u auto-trade-api

# Combined
journalctl -u auto-trade-api -p err --since "1 hour ago"
```

✅ **Survives restarts**
- Logs persist across service restarts
- Can configure to persist across reboots

### Considerations

⚠️ **Binary format**
- Need `journalctl` to read (can't use `cat` or `less`)
- But you can export to text: `journalctl > logs.txt`

⚠️ **Shared disk space**
- Shares space with system logs
- But you can set limits (see above)

---

## 📝 Quick Reference

### Essential Commands

```bash
# View live logs
journalctl -u auto-trade-api -f
journalctl -u auto-trade-worker -f

# View recent logs
journalctl -u auto-trade-api -n 50

# View errors only
journalctl -u auto-trade-api -p err

# Export to file
journalctl -u auto-trade-api > api_logs.txt

# Check disk usage
journalctl --disk-usage

# Clean up old logs
sudo journalctl --vacuum-size=100M
```

### Service Management

```bash
# Status
sudo systemctl status auto-trade-api auto-trade-worker

# Restart
sudo systemctl restart auto-trade-api auto-trade-worker

# Stop
sudo systemctl stop auto-trade-api auto-trade-worker

# View service details
sudo systemctl show auto-trade-api
```

---

## ✅ Summary

**Problem**: systemd doesn't support `append:` log file directive  
**Root Cause**: Older/minimal systemd version  
**Solution**: Use journal logging (universally supported)  
**Status**: ✅ FIXED - Service files updated  

**Benefits**:
- ✅ Works on all systemd versions
- ✅ Integrated log management
- ✅ Automatic rotation
- ✅ Powerful filtering
- ✅ Still get file logs from Python logging

**Next Step**: Run `sudo ./install_with_journal.sh` to install the fixed services.

---

*Fixed: May 14, 2026*  
*Issue: "log file support is not available"*  
*Solution: Journal-based logging (StandardOutput=journal)*  
*Impact: Zero - you still get file logs from Python logging_config.py*
