# Systemd Log File Support Fix - COMPLETED ✅

## Problem Identified

Your systemd version doesn't support the `append:` directive for log file paths. This caused the error:

```
Loaded: error (Reason: Unit auto-trade-worker.service has a bad unit file setting)
log file support is not available
```

This is common on older systemd versions or minimal installations.

---

## Solution Applied

Changed from file-based logging to **journal-based logging** (systemd's native logging system).

### Before (❌ Broken)
```ini
StandardOutput=append:/home/admin/.openclaw/workspace/auto-trade-system/logs/api.log
StandardError=append:/home/admin/.openclaw/workspace/auto-trade-system/logs/api_error.log
```

### After (✅ Fixed)
```ini
# Use journal for logging (systemd default)
StandardOutput=journal
StandardError=journal
```

---

## Files Modified

1. **[systemd/auto-trade-api.service](systemd/auto-trade-api.service)**
   - Changed to `StandardOutput=journal`
   - Changed to `StandardError=journal`

2. **[systemd/auto-trade-worker.service](systemd/auto-trade-worker.service)**
   - Changed to `StandardOutput=journal`
   - Changed to `StandardError=journal`

---

## How to Install (Now Fixed)

### Step 1: Copy Updated Service Files

```bash
sudo cp /home/admin/.openclaw/workspace/auto-trade-system/systemd/auto-trade-api.service /etc/systemd/system/
sudo cp /home/admin/.openclaw/workspace/auto-trade-system/systemd/auto-trade-worker.service /etc/systemd/system/
```

### Step 2: Reload Systemd

```bash
sudo systemctl daemon-reload
```

### Step 3: Enable Services

```bash
sudo systemctl enable auto-trade-api.service
sudo systemctl enable auto-trade-worker.service
```

### Step 4: Start Services

```bash
sudo systemctl start auto-trade-api.service
sudo systemctl start auto-trade-worker.service
```

### Step 5: Verify

```bash
sudo systemctl status auto-trade-api.service
sudo systemctl status auto-trade-worker.service
```

Both should show:
```
Loaded: loaded (/etc/systemd/system/auto-trade-*.service; enabled)
Active: active (running)
```

---

## Viewing Logs with Journalctl

Since we're now using journal logging, use these commands:

### API Service Logs

```bash
# Live logs (follow mode)
journalctl -u auto-trade-api -f

# Last 50 lines
journalctl -u auto-trade-api -n 50

# Last hour
journalctl -u auto-trade-api --since "1 hour ago"

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

### Both Services

```bash
# Combined logs
journalctl -u auto-trade-api -u auto-trade-worker -f

# Only errors
journalctl -u auto-trade-api -u auto-trade-worker -p err -f
```

---

## Optional: Persistent Journal Configuration

By default, journal logs may not persist across reboots. To make them persistent:

### Check Current Journal Settings

```bash
# Check if journal is persistent
ls -la /var/log/journal/

# If directory doesn't exist, journal is volatile (lost on reboot)
```

### Enable Persistent Journal

```bash
# Create persistent journal directory
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal

# Restart journald
sudo systemctl restart systemd-journald

# Set size limit (optional, prevents disk fill-up)
sudo tee /etc/systemd/journald.conf.d/trade-bot.conf <<'EOF'
[Journal]
SystemMaxUse=500M
SystemKeepFree=1G
MaxRetentionSec=30day
EOF

# Restart journald again
sudo systemctl restart systemd-journald
```

---

## Alternative: Dual Logging (Journal + Files)

If you want BOTH journal logging AND file logs, modify the service files:

```ini
[Service]
# ... other settings ...

# Send to both journal and application logger
StandardOutput=journal
StandardError=journal

# The application itself handles file logging via logging_config.py
Environment=LOG_TO_FILE=true
```

The Python application already writes to files via `logging_config.py`, so you get:
- ✅ Journal logs (for systemd integration)
- ✅ File logs (from Python's logging configuration)

---

## Verification Checklist

After installation, verify:

- [ ] `sudo systemctl status auto-trade-api` shows "active (running)"
- [ ] `sudo systemctl status auto-trade-worker` shows "active (running)"
- [ ] `journalctl -u auto-trade-api -n 10` shows recent logs
- [ ] `curl http://localhost:8000/health/deep` returns healthy
- [ ] No errors in `journalctl -u auto-trade-api -p err`

---

## Troubleshooting

### Still Showing "Loaded: error"

```bash
# Check what's wrong
sudo systemd-analyze verify /etc/systemd/system/auto-trade-api.service
sudo systemd-analyze verify /etc/systemd/system/auto-trade-worker.service

# Reload daemon
sudo systemctl daemon-reload

# Reset failed state
sudo systemctl reset-failed auto-trade-api auto-trade-worker
```

### Logs Not Appearing in Journal

```bash
# Check if journald is running
sudo systemctl status systemd-journald

# Restart journald
sudo systemctl restart systemd-journald

# Check journal size
journalctl --disk-usage
```

### Service Won't Start

```bash
# Check detailed error
sudo journalctl -u auto-trade-api -n 50 --no-pager

# Common issues:
# 1. Port 8000 already in use
sudo lsof -i :8000

# 2. Python path incorrect
ls -la /home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python

# 3. Missing dependencies
/home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python -c "import fastapi"
```

---

## Benefits of Journal Logging

✅ **Advantages:**
- Integrated with systemd ecosystem
- Automatic log rotation
- Structured metadata (timestamps, service name, etc.)
- Easy filtering and searching
- Survives service restarts
- No file permission issues

⚠️ **Considerations:**
- May not persist across reboots by default (fixable)
- Uses binary format (need `journalctl` to read)
- Shared disk space with system logs

---

## Quick Reference Commands

```bash
# View logs
journalctl -u auto-trade-api -f
journalctl -u auto-trade-worker -f

# Filter by priority
journalctl -u auto-trade-api -p err    # Errors only
journalctl -u auto-trade-api -p warning # Warnings and above

# Time-based filtering
journalctl -u auto-trade-api --since "10 minutes ago"
journalctl -u auto-trade-api --since "2026-05-14 23:00:00"

# Export to file
journalctl -u auto-trade-api > api_logs.txt
journalctl -u auto-trade-api --since "1 hour ago" > recent_logs.txt

# Disk usage
journalctl --disk-usage
sudo journalctl --vacuum-size=100M  # Free up space
```

---

## Summary

**Problem**: systemd doesn't support `append:` log file directive  
**Solution**: Use journal logging (`StandardOutput=journal`)  
**Status**: ✅ FIXED - Service files updated and ready  

**Next Step**: Run the installation commands above to deploy the fixed services.

---

*Fixed: May 14, 2026*  
*Issue: "log file support is not available"*  
*Solution: Journal-based logging*
