# Python 3.11 Upgrade - Quick Reference Guide

## TL;DR - What Changed?

- **Python Version**: 3.6.8 → 3.11.15 (via Linuxbrew)
- **Location**: `/home/linuxbrew/.linuxbrew/bin/python3.11`
- **Status**: Configuration complete, ready for implementation

---

## For Developers - Update Your Environment

### 1. Recreate Your Virtual Environment

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system

# Remove old venv
rm -rf .venv

# Create new venv with Python 3.11
/home/linuxbrew/.linuxbrew/bin/python3.11 -m venv .venv

# Activate
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Verify
python --version  # Should show: Python 3.11.15
```

### 2. Update IDE Settings

**VSCode**:
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Python: Select Interpreter"
3. Choose: `.venv/bin/python` (should show Python 3.11.15)

**PyCharm**:
1. Go to `File > Settings > Project > Python Interpreter`
2. Click gear icon → `Add`
3. Select `Existing Environment`
4. Browse to: `/home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python`

---

## For Operations - Deployment Steps

### Pre-Deployment Checklist

```bash
# 1. Backup database
./scripts/backup_database.sh

# 2. Backup current venv
cp -r .venv .venv.backup.python36

# 3. Stop application
sudo systemctl stop vmassit.service
```

### Deployment Commands

```bash
# 1. Navigate to project
cd /home/admin/.openclaw/workspace/auto-trade-system

# 2. Recreate venv
rm -rf .venv
/home/linuxbrew/.linuxbrew/bin/python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 4. Verify installation
python -c "import fastapi, sqlalchemy, pydantic, ccxt, asyncpg; print('✅ All packages installed')"

# 5. Test migrations
python migrate.py check

# 6. Start application
sudo systemctl start vmassit.service

# 7. Check status
sudo systemctl status vmassit.service
journalctl -u vmassit.service -f --since "5 minutes ago"
```

### Rollback Commands (If Needed)

```bash
# Stop application
sudo systemctl stop vmassit.service

# Restore old venv
cd /home/admin/.openclaw/workspace/auto-trade-system
rm -rf .venv
mv .venv.backup.python36 .venv

# Reactivate and restart
source .venv/bin/activate
sudo systemctl start vmassit.service

# Verify rollback
python --version  # Should show: Python 3.6.8
```

---

## Verification Tests

### Quick Health Check

```bash
# Activate venv first
source .venv/bin/activate

# Test 1: Python version
python --version
# Expected: Python 3.11.15

# Test 2: Config loading
python -c "from app.config import settings; print('✅ Config OK')"

# Test 3: Database connection
python -c "from app.database.connection import init_db; import asyncio; asyncio.run(init_db()); print('✅ Database OK')"

# Test 4: Application startup
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 5
curl http://localhost:8000/health
# Expected: {"status":"healthy","version":"2.0.0"}
kill %1
```

### Full System Validation

```bash
# Run comprehensive validation scripts
python scripts/validate_complete_system.py
python scripts/test_multi_agent_system.py

# Check logs for errors
grep -i "error\|exception\|traceback" demo_trading_session.log | tail -20
```

---

## Common Issues & Solutions

### Issue: "No module named 'xxx'"

**Cause**: Dependencies not installed in new venv

**Solution**:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Issue: C extension compilation fails

**Cause**: Missing Python 3.11 development headers

**Solution**:
```bash
# Check if headers exist
ls /home/linuxbrew/.linuxbrew/include/python3.11/

# If missing, reinstall Python 3.11 via Linuxbrew
brew reinstall python@3.11
```

### Issue: Import error with old syntax

**Cause**: Legacy Python 3.6 code patterns

**Solution**: Search for deprecated patterns
```bash
grep -r "print " app/ --include="*.py" | grep -v "print("
grep -r "ensure_future\|@coroutine" app/ --include="*.py"
```

### Issue: Performance seems slower

**Cause**: First-time optimization cache miss

**Solution**: Run application for 10-15 minutes to warm up caches. Python 3.11's adaptive interpreter improves over time.

---

## Key Benefits of Python 3.11

1. **Performance**: 10-60% faster execution
2. **Better Error Messages**: More helpful tracebacks
3. **Improved Async**: Faster async/await operations
4. **Type Hints**: Enhanced type checking support
5. **Security**: Latest security patches and updates

---

## Files Modified

- ✅ `requirements.txt` - Added Python version comment
- ✅ `pyproject.toml` - Created with Python 3.11 constraint
- ✅ `.env.example` - Added version requirement note
- ✅ `README.md` - Updated setup instructions and version info
- ✅ `PYTHON_UPGRADE_SUMMARY.md` - Comprehensive upgrade guide (NEW)
- ✅ `PYTHON_3.11_QUICKREF.md` - This file (NEW)

---

## Support Contacts

- **Documentation**: See `PYTHON_UPGRADE_SUMMARY.md` for full details
- **Logs**: `journalctl -u vmassit.service -f`
- **Issues**: Check application logs in `demo_trading_session.log`
- **Plan Details**: `plans/Python_Version_Upgrade_Plan_*.md`

---

**Last Updated**: May 13, 2026  
**Python Version**: 3.11.15  
**Status**: Ready for Implementation ✅
