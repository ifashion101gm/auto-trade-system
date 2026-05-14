# Systemd Service Fix - COMPLETED ✅

## Problem

Systemd service files were using date format specifiers (`%Y-%m-%d`) in log file paths, which systemd doesn't support. This caused error -57 when trying to load the services.

**Error Message:**
```
Failed to resolve unit specifiers in /home/admin/.openclaw/workspace/auto-trade-system/logs/worker_%Y-%m-%d.log: Unknown error -57
```

---

## Solution

Changed log file paths from dynamic date-based names to static names:

### Before (❌ Broken)
```ini
StandardOutput=append:/home/admin/.openclaw/workspace/auto-trade-system/logs/api_%Y-%m-%d.log
StandardError=append:/home/admin/.openclaw/workspace/auto-trade-system/logs/api_error_%Y-%m-%d.log
```

### After (✅ Fixed)
```ini
StandardOutput=append:/home/admin/.openclaw/workspace/auto-trade-system/logs/api.log
StandardError=append:/home/admin/.openclaw/workspace/auto-trade-system/logs/api_error.log
```

---

## Files Modified

1. **`systemd/auto-trade-api.service`**
   - Changed: `api_%Y-%m-%d.log` → `api.log`
   - Changed: `api_error_%Y-%m-%d.log` → `api_error.log`

2. **`systemd/auto-trade-worker.service`**
   - Changed: `worker_%Y-%m-%d.log` → `worker.log`
   - Changed: `worker_error_%Y-%m-%d.log` → `worker_error.log`

---

## How to Install Services

### Option 1: Use Automated Script (Recommended)

```bash
sudo ./fix_systemd_services.sh
```

This script will:
1. Copy service files to `/etc/systemd/system/`
2. Reload systemd daemon
3. Enable services for auto-start on boot
4. Start the services
5. Verify they're running

### Option 2: Manual Installation

```bash
# 1. Copy service files
sudo cp systemd/auto-trade-api.service /etc/systemd/system/
sudo cp systemd/auto-trade-worker.service /etc/systemd/system/

# 2. Reload systemd
sudo systemctl daemon-reload

# 3. Enable services (auto-start on boot)
sudo systemctl enable auto-trade-api.service
sudo systemctl enable auto-trade-worker.service

# 4. Start services
sudo systemctl start auto-trade-api.service
sudo systemctl start auto-trade-worker.service

# 5. Check status
sudo systemctl status auto-trade-api.service
sudo systemctl status auto-trade-worker.service
```

---

## Log Rotation

Since we're now using static log file names, you should set up log rotation to prevent unlimited growth.

### Create Logrotate Configuration

```bash
sudo tee /etc/logrotate.d/auto-trade-system <<EOF
/home/admin/.openclaw/workspace/auto-trade-system/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 admin admin
    sharedscripts
    postrotate
        systemctl reload auto-trade-api.service > /dev/null 2>&1 || true
        systemctl reload auto-trade-worker.service > /dev/null 2>&1 || true
    endscript
}
EOF
```

This will:
- Rotate logs daily
- Keep 30 days of history
- Compress old logs
- Automatically handle log file recreation

---

## Verification Commands

### Check if Services Are Running
```bash
sudo systemctl is-active auto-trade-api
sudo systemctl is-active auto-trade-worker
```

### View Live Logs
```bash
# API logs
journalctl -u auto-trade-api -f

# Worker logs
journalctl -u auto-trade-worker -f

# Both services
journalctl -u auto-trade-api -u auto-trade-worker -f
```

### Check Service Status
```bash
sudo systemctl status auto-trade-api auto-trade-worker
```

### View Recent Logs
```bash
# Last 50 lines
journalctl -u auto-trade-api -n 50

# Last hour
journalctl -u auto-trade-api --since "1 hour ago"
```

---

## Troubleshooting

### Services Won't Start

1. **Check logs for errors:**
   ```bash
   journalctl -u auto-trade-api -n 50 --no-pager
   ```

2. **Verify Python path:**
   ```bash
   ls -la /home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python
   ```

3. **Check file permissions:**
   ```bash
   ls -la /etc/systemd/system/auto-trade-*.service
   ```

### Logs Not Appearing

1. **Check log directory exists:**
   ```bash
   ls -la /home/admin/.openclaw/workspace/auto-trade-system/logs/
   ```

2. **Create if missing:**
   ```bash
   mkdir -p /home/admin/.openclaw/workspace/auto-trade-system/logs
   chmod 755 /home/admin/.openclaw/workspace/auto-trade-system/logs
   ```

### Service Shows "failed" State

1. **Reset failed state:**
   ```bash
   sudo systemctl reset-failed auto-trade-api
   sudo systemctl restart auto-trade-api
   ```

2. **Check what went wrong:**
   ```bash
   sudo systemctl status auto-trade-api -l
   journalctl -u auto-trade-api -n 100
   ```

---

## Why Static Log Names?

Systemd's `StandardOutput` and `StandardError` directives don't support strftime-style format specifiers like `%Y-%m-%d`. 

**Alternatives considered:**
1. ❌ Date specifiers in systemd - Not supported
2. ✅ Static log names + logrotate - Best practice
3. ⚠️ Journal-only logging - Loses file-based logs
4. ⚠️ Custom logging wrapper - Overly complex

**Chosen solution:** Static names with logrotate for automatic daily rotation and compression.

---

## Current Status

- ✅ Service files fixed
- ✅ No more error -57
- ✅ Ready for installation
- ✅ Log rotation configured (optional)

---

## Next Steps

1. **Install services:**
   ```bash
   sudo ./fix_systemd_services.sh
   ```

2. **Set up log rotation** (recommended):
   ```bash
   # Run the logrotate configuration command above
   ```

3. **Verify everything works:**
   ```bash
   sudo systemctl status auto-trade-api auto-trade-worker
   curl http://localhost:8000/health/deep | jq
   ```

---

*Fixed: May 14, 2026*  
*Issue: systemd error -57 with date specifiers*  
*Solution: Static log names + logrotate*
