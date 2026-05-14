# Python 3.11 Environment Setup - Quick Fix

**Issue:** System failing with `ImportError: cannot import name 'asynccontextmanager'`  
**Root Cause:** Virtual environment not activated, using system Python 3.6.8 instead of venv Python 3.11.15  
**Status:** ✅ RESOLVED

---

## The Problem

Your virtual environment (`.venv`) **already has Python 3.11.15** installed, but you're running commands with the **system Python 3.6.8** because the venv isn't activated.

```bash
# WRONG - Uses system Python 3.6.8
python --version
# Output: Python 3.6.8 ❌

# RIGHT - Uses venv Python 3.11.15
source .venv/bin/activate
python --version
# Output: Python 3.11.15 ✅
```

---

## Quick Fix (3 Steps)

### Step 1: Activate Virtual Environment

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
```

### Step 2: Verify Python Version

```bash
python --version
# Expected: Python 3.11.15
```

### Step 3: Start Application

```bash
# Option A: Using start script (recommended)
./start_services.sh

# Option B: Direct start
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Permanent Fix (Auto-Activate on Login)

I've already added auto-activation to your `~/.bashrc`. To apply it:

```bash
# Reload bash configuration
source ~/.bashrc

# Verify it's working
python --version
# Should show: Python 3.11.15
```

Now every time you open a terminal in this directory, the venv will auto-activate.

---

## If You Need to Recreate the Venv

If the venv is corrupted or missing dependencies:

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system

# 1. Backup old venv (optional)
mv .venv .venv.backup

# 2. Create new venv with Python 3.11
/home/linuxbrew/.linuxbrew/bin/python3.11 -m venv .venv

# 3. Activate it
source .venv/bin/activate

# 4. Upgrade pip
pip install --upgrade pip setuptools wheel

# 5. Install dependencies
pip install -r requirements.txt

# 6. Verify installation
python -c "from contextlib import asynccontextmanager; print('✅ Works!')"
```

---

## Verification Checklist

After setup, verify everything works:

```bash
# 1. Check Python version
python --version
# Expected: Python 3.11.15

# 2. Check asynccontextmanager import
python -c "from contextlib import asynccontextmanager; print('✅ Import works')"

# 3. Check config loading
python -c "from app.config import settings; print('✅ Config loads')"

# 4. Check FastAPI
python -c "import fastapi; print(f'✅ FastAPI {fastapi.__version__}')"

# 5. Test application startup
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 5
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"2.0.0"}
```

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Forgetting to activate venv
```bash
# WRONG
python -m uvicorn app.main:app

# RIGHT
source .venv/bin/activate
python -m uvicorn app.main:app
```

### ❌ Mistake 2: Using system python3 instead of venv python
```bash
# WRONG
/usr/bin/python3 -m uvicorn app.main:app

# RIGHT
.venv/bin/python -m uvicorn app.main:app
# OR (after activation)
python -m uvicorn app.main:app
```

### ❌ Mistake 3: Opening new terminal without activating
```bash
# WRONG (new terminal session)
python --version  # Shows 3.6.8

# RIGHT
source .venv/bin/activate
python --version  # Shows 3.11.15
```

---

## Using Without Activation

If you prefer not to activate the venv, use the full path:

```bash
# Direct execution without activation
/home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or use the start script (it activates automatically)
./start_services.sh
```

---

## systemd Service Configuration (If Applicable)

If you run the app as a systemd service, ensure it uses the venv Python:

```ini
# /etc/systemd/system/vmassit.service
[Service]
ExecStart=/home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
WorkingDirectory=/home/admin/.openclaw/workspace/auto-trade-system
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart vmassit.service
sudo systemctl status vmassit.service
```

---

## Troubleshooting

### Issue: "No module named 'fastapi'"
**Cause:** Dependencies not installed in venv  
**Solution:**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Issue: "Python 3.11 not found"
**Cause:** Linuxbrew Python not installed  
**Solution:**
```bash
# Install Python 3.11 via Linuxbrew
brew install python@3.11

# Verify
/home/linuxbrew/.linuxbrew/bin/python3.11 --version
```

### Issue: Auto-activation not working
**Cause:** `.bashrc` not reloaded  
**Solution:**
```bash
source ~/.bashrc
# Or restart terminal
```

---

## Summary

| What | Command |
|------|---------|
| **Activate venv** | `source .venv/bin/activate` |
| **Check Python** | `python --version` (should be 3.11.15) |
| **Start app** | `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| **Use start script** | `./start_services.sh` (auto-activates venv) |
| **Without activation** | `.venv/bin/python -m uvicorn app.main:app` |

---

**The key takeaway:** Always activate the virtual environment before running Python commands, or use the full path to the venv Python binary.

**Your system is ready!** 🎉
