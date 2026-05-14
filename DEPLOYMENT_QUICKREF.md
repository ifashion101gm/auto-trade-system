# Deployment Quick Reference

## Current Status

Your app is currently running **manually** via uvicorn (PID 1554704).

Systemd services are **NOT installed** yet.

---

## Deployment Options

### Option 1: Keep Running Manually (Current Method)

**To restart current app:**
```bash
# Kill current process
kill 1554704

# Restart
cd /home/admin/.openclaw/workspace/auto-trade-system
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Pros:**
- Simple, no setup required
- Easy to debug (see logs in terminal)

**Cons:**
- Won't auto-restart if it crashes
- Must manually start after server reboot
- No automatic log rotation

---

### Option 2: Install Systemd Services (Recommended for Production)

**Quick Install:**
```bash
sudo ./deploy.sh --install
sudo ./deploy.sh --start
```

**Or step-by-step:**
```bash
# 1. Install service files
sudo cp systemd/auto-trade-api.service /etc/systemd/system/
sudo cp systemd/auto-trade-worker.service /etc/systemd/system/

# 2. Reload systemd
sudo systemctl daemon-reload

# 3. Enable services (auto-start on boot)
sudo systemctl enable auto-trade-api
sudo systemctl enable auto-trade-worker

# 4. Start services
sudo systemctl start auto-trade-api
sudo systemctl start auto-trade-worker
```

**Management Commands:**
```bash
# Check status
sudo systemctl status auto-trade-api
sudo systemctl status auto-trade-worker

# View logs (follow mode)
sudo journalctl -u auto-trade-api -f
sudo journalctl -u auto-trade-worker -f

# Restart
sudo systemctl restart auto-trade-api
sudo systemctl restart auto-trade-worker

# Stop
sudo systemctl stop auto-trade-api
sudo systemctl stop auto-trade-worker

# Disable (prevent auto-start)
sudo systemctl disable auto-trade-api
sudo systemctl disable auto-trade-worker
```

**Pros:**
- Auto-restarts on crash
- Auto-starts on server reboot
- Automatic log rotation
- Better resource management
- Production-ready

**Cons:**
- Requires sudo for management
- Logs in journalctl (not terminal)

---

## Deploy Script Usage

The `deploy.sh` script provides easy management:

```bash
# Interactive menu
./deploy.sh

# Command-line options
./deploy.sh --manual      # Run manually
./deploy.sh --install     # Install systemd services
./deploy.sh --start       # Start services
./deploy.sh --stop        # Stop services
./deploy.sh --restart     # Restart services
./deploy.sh --uninstall   # Remove systemd services
./deploy.sh --status      # Show current status
```

---

## Before Upgrading to Enterprise Main

### Step 1: Set Admin API Key
```bash
# Generate secure key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Add to .env
echo "ADMIN_API_KEY=YOUR_GENERATED_KEY" >> .env
```

### Step 2: Backup Current Main
```bash
cp app/main.py app/main_backup_$(date +%Y%m%d_%H%M%S).py
```

### Step 3: Replace with Enterprise Version
```bash
cp app/main_enterprise.py app/main.py
```

### Step 4: Restart
```bash
# If running manually
kill $(pgrep -f 'uvicorn app.main:app')
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# OR if using systemd
sudo systemctl restart auto-trade-api
```

### Step 5: Verify
```bash
# Check health
curl http://localhost:8000/health | jq

# Check deep health (includes session & news)
curl http://localhost:8000/health/deep | jq

# Test admin route (requires API key)
curl -H "x-api-key: YOUR_KEY" http://localhost:8000/admin/state | jq
```

---

## Troubleshooting

### App Won't Start

**Check logs:**
```bash
# Manual mode: check terminal output

# Systemd mode
sudo journalctl -u auto-trade-api -n 50 --no-pager
```

**Common issues:**
- Port 8000 already in use: `lsof -i :8000`
- Missing dependencies: `.venv/bin/pip install -r requirements.txt`
- Database not running: `sudo systemctl status postgresql`
- Redis not running: `sudo systemctl status redis`

### Can't Access on Port 8000

**Check firewall:**
```bash
sudo ufw status
sudo ufw allow 8000/tcp
```

**Check if listening:**
```bash
ss -tlnp | grep 8000
```

### Service Fails to Start

**Check service file:**
```bash
sudo systemctl cat auto-trade-api
```

**Verify paths exist:**
```bash
ls -la /home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python
ls -la /home/admin/.openclaw/workspace/auto-trade-system/app/main.py
```

**Test command manually:**
```bash
/home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Log Locations

### Manual Mode
- Logs appear in terminal
- Also written to: `logs/app_*.log`

### Systemd Mode
- View with: `sudo journalctl -u auto-trade-api -f`
- Also written to: `logs/api_*.log`
- Worker logs: `logs/worker_*.log`

---

## Recommended Setup for Production

1. **Install systemd services**
   ```bash
   sudo ./deploy.sh --install
   ```

2. **Set ADMIN_API_KEY in .env**
   ```bash
   echo "ADMIN_API_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')" >> .env
   ```

3. **Upgrade to enterprise main**
   ```bash
   cp app/main.py app/main_backup_$(date +%Y%m%d).py
   cp app/main_enterprise.py app/main.py
   sudo ./deploy.sh --restart
   ```

4. **Monitor for 24 hours**
   ```bash
   sudo journalctl -u auto-trade-api -f
   ```

5. **Enable worker service (if using separate process)**
   ```bash
   sudo ./deploy.sh --start  # Starts both API and worker
   ```

---

## Quick Commands Cheat Sheet

```bash
# Check what's running
ps aux | grep uvicorn
./deploy.sh --status

# Restart (manual)
kill $(pgrep -f 'uvicorn app.main:app')
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Restart (systemd)
sudo systemctl restart auto-trade-api

# View logs
tail -f logs/app_*.log          # Manual mode
sudo journalctl -u auto-trade-api -f  # Systemd mode

# Test endpoints
curl http://localhost:8000/health | jq
curl http://localhost:8000/health/deep | jq
```

---

**Last Updated**: 2026-05-14  
**Version**: 3.0.0 Enterprise
