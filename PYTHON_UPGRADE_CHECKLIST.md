# Python 3.11 Upgrade - Implementation Checklist

**Date**: May 13, 2026  
**Status**: ✅ Configuration Complete - Ready for Manual Implementation  
**Python Version**: 3.6.8 → 3.11.15

---

## ✅ Completed (Automated by AI)

### Configuration Files Updated
- [x] `requirements.txt` - Added Python 3.11+ requirement comment
- [x] `pyproject.toml` - Created with Python version constraint (>=3.11,<3.13)
- [x] `.env.example` - Added Python version requirement note
- [x] `README.md` - Updated with Python 3.11 setup instructions
- [x] `PYTHON_UPGRADE_SUMMARY.md` - Comprehensive upgrade guide created
- [x] `PYTHON_3.11_QUICKREF.md` - Quick reference guide created

### Code Compatibility Verified
- [x] Scanned for deprecated patterns (`ensure_future`, `@coroutine`, `yield from`) - None found
- [x] Checked for Python 3.6 workarounds (`from __future__`, `sys.version_info`) - None found
- [x] Verified `app/main.py` compatibility - Uses modern async patterns
- [x] Verified `app/config.py` compatibility - Pydantic-settings 2.12.0 compatible
- [x] Verified Alembic migrations - All use standard SQLAlchemy patterns
- [x] Confirmed Python 3.11.15 availability at `/home/linuxbrew/.linuxbrew/bin/python3.11`

---

## ⚠️ Pending (Manual Implementation Required)

### Step 1: Pre-Implementation Backup
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system

# Backup database (CRITICAL - do not skip)
./scripts/backup_database.sh

# Backup current virtual environment
cp -r .venv .venv.backup.python36

# Verify backups exist
ls -lh backup_*.sql
ls -ld .venv.backup.python36
```

**Expected Output**:
- Database backup file in project root or backup directory
- `.venv.backup.python36/` directory created

---

### Step 2: Recreate Virtual Environment

```bash
# Remove old virtual environment
rm -rf .venv

# Create new virtual environment with Python 3.11
/home/linuxbrew/.linuxbrew/bin/python3.11 -m venv .venv

# Activate new environment
source .venv/bin/activate

# Verify Python version
python --version
```

**Expected Output**:
```
Python 3.11.15
```

**Verification**:
```bash
which python
# Expected: /home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python

which pip
# Expected: /home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/pip
```

---

### Step 3: Install Dependencies

```bash
# Upgrade pip and build tools
pip install --upgrade pip setuptools wheel

# Install all dependencies
pip install -r requirements.txt
```

**Expected Output**: No errors during installation

**Verify Critical Packages**:
```bash
python -c "import fastapi; print(f'✅ FastAPI {fastapi.__version__}')"
python -c "import sqlalchemy; print(f'✅ SQLAlchemy {sqlalchemy.__version__}')"
python -c "import pydantic; print(f'✅ Pydantic {pydantic.__version__}')"
python -c "import ccxt; print(f'✅ CCXT {ccxt.__version__}')"
python -c "import asyncpg; print(f'✅ asyncpg {asyncpg.__version__}')"
python -c "import redis; print(f'✅ Redis {redis.__version__}')"
```

**All should show version numbers without errors.**

---

### Step 4: Validate Database Migrations

```bash
# Check migration status
python migrate.py check

# Verify current revision
python migrate.py current

# List available migrations
python migrate.py heads
```

**Expected Output**:
- `check`: Should complete without errors
- `current`: Shows current database revision (e.g., `ef11f40ce208`)
- `heads`: Shows latest available migration

---

### Step 5: Test Application Startup

```bash
# Test configuration loading
python -c "from app.config import settings; print('✅ Config loaded successfully')"

# Test database connection
python -c "from app.database.connection import init_db; import asyncio; asyncio.run(init_db()); print('✅ Database connection successful')"

# Start application in test mode (background)
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
APP_PID=$!

# Wait for startup
sleep 5

# Test health endpoint
curl http://localhost:8000/health

# Stop test server
kill $APP_PID
```

**Expected Output from curl**:
```json
{"status":"healthy","version":"2.0.0"}
```

---

### Step 6: Run Validation Tests

```bash
# Run comprehensive validation
python scripts/validate_complete_system.py

# Test multi-agent system
python scripts/test_multi_agent_system.py

# Check for runtime errors in logs
tail -100 demo_trading_session.log | grep -i "error\|exception"
```

**Expected Output**: All tests pass, no critical errors in logs

---

### Step 7: Update Systemd Service (If Applicable)

If running as systemd service:

```bash
# Check if service exists
systemctl list-unit-files | grep vmassit

# If service exists, verify Python path in service file
sudo systemctl cat vmassit.service | grep ExecStart

# Expected ExecStart line should use venv Python:
# ExecStart=/home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# If path is incorrect, edit service file
sudo systemctl edit vmassit.service

# Add or modify:
# [Service]
# ExecStart=/home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Reload systemd
sudo systemctl daemon-reload

# Restart service
sudo systemctl restart vmassit.service

# Check status
sudo systemctl status vmassit.service

# Monitor logs
journalctl -u vmassit.service -f --since "2 minutes ago"
```

---

### Step 8: Post-Deployment Monitoring

Monitor for 24-48 hours after deployment:

```bash
# Check application logs
tail -f demo_trading_session.log

# Monitor systemd service logs
journalctl -u vmassit.service -f

# Check for Python-related errors
grep -i "python\|import\|module" demo_trading_session.log | grep -i error

# Verify WebSocket connections
grep "WebSocket" demo_trading_session.log | tail -20

# Check exchange API calls
grep "MEXC\|Binance\|Bybit" demo_trading_session.log | grep -i "error\|fail" | tail -20

# Monitor Prometheus metrics
curl http://localhost:8000/metrics/prometheus | head -50
```

**Watch For**:
- Import errors
- Module not found errors
- Unexpected exceptions
- Failed API calls
- WebSocket disconnections

---

## 🎯 Success Criteria

Upgrade is successful when ALL of the following are true:

- [ ] Python version shows 3.11.15 in activated venv
- [ ] All dependencies install without compilation errors
- [ ] Database migrations run successfully
- [ ] Application starts without import errors
- [ ] Health endpoint returns `{"status":"healthy"}`
- [ ] WebSocket connections establish successfully
- [ ] Exchange API calls succeed (test with MEXC/Binance/Bybit)
- [ ] AI agents initialize correctly
- [ ] Telegram notifications send properly
- [ ] Prometheus metrics endpoint responds
- [ ] Background tasks run (reconciliation, position sync)
- [ ] No deprecation warnings in logs
- [ ] Trade execution works end-to-end
- [ ] Grafana dashboards display data
- [ ] Loki log aggregation working

---

## 🔄 Rollback Procedure (If Issues Occur)

If any critical issues arise:

```bash
# 1. Stop application
sudo systemctl stop vmassit.service

# 2. Deactivate new venv
deactivate

# 3. Restore old virtual environment
cd /home/admin/.openclaw/workspace/auto-trade-system
rm -rf .venv
mv .venv.backup.python36 .venv

# 4. Reactivate old environment
source .venv/bin/activate

# 5. Verify rollback
python --version
# Expected: Python 3.6.8

# 6. Restart application
sudo systemctl start vmassit.service

# 7. Verify service is running
sudo systemctl status vmassit.service

# 8. Check logs
journalctl -u vmassit.service -f --since "2 minutes ago"
```

---

## 📞 Support Resources

### Documentation
- **Full Guide**: `PYTHON_UPGRADE_SUMMARY.md`
- **Quick Reference**: `PYTHON_3.11_QUICKREF.md`
- **Original Plan**: `plans/Python_Version_Upgrade_Plan_*.md`

### Logs
- **Application Logs**: `demo_trading_session.log`
- **Systemd Logs**: `journalctl -u vmassit.service -f`
- **Docker Logs** (if using): `docker-compose logs -f`

### Diagnostic Scripts
- `scripts/diagnose_connectivity.py` - Test network connectivity
- `scripts/check_open_trades.py` - Verify trade state
- `scripts/production_monitoring_queries.py` - Query event store

### Key Commands
```bash
# Check Python version
python --version

# List installed packages
pip list

# Check specific package
pip show fastapi

# Test imports
python -c "import fastapi, sqlalchemy, pydantic, ccxt, asyncpg"

# View recent errors
grep -i "error\|exception" demo_trading_session.log | tail -50
```

---

## 📊 Estimated Timeline

- **Backup**: 5 minutes
- **Recreate venv**: 2 minutes
- **Install dependencies**: 10-15 minutes (depending on network speed)
- **Validation tests**: 10 minutes
- **Service update**: 5 minutes
- **Initial monitoring**: 30 minutes
- **Extended monitoring**: 24-48 hours

**Total Active Time**: ~30-45 minutes  
**Total Monitoring Time**: 24-48 hours

---

## ✅ Final Sign-Off

After completing all steps and 24-48 hour monitoring period:

**Upgrade Completed By**: _________________  
**Date**: _________________  
**Time Started**: _________________  
**Time Completed**: _________________  

**Issues Encountered**:  
_______________________________________________________  
_______________________________________________________  

**Resolution**:  
_______________________________________________________  
_______________________________________________________  

**Performance Observations**:  
_______________________________________________________  
_______________________________________________________  

**Approved By**: _________________  
**Date**: _________________  

---

**Document Version**: 1.0  
**Last Updated**: May 13, 2026  
**Next Review**: After 30 days of production operation
