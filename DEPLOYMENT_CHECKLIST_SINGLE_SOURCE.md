# Single Source of Truth Architecture - Deployment Checklist

## Overview
This checklist guides you through deploying the production-grade trading system with PostgreSQL, WebSocket sync, and event-driven architecture.

---

## Prerequisites

### 1. Install PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql
CREATE DATABASE vmassit;
CREATE USER your_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE vmassit TO your_user;
\q
```

### 2. Install Redis
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# Start Redis service
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

### 3. Install Python Dependencies
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
pip install -r requirements.txt
```

**New dependencies added:**
- `websockets>=12.0` - For MEXC WebSocket connection

---

## Configuration

### 4. Update .env File
Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
nano .env
```

**Required changes:**
```ini
# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://your_user:your_password@localhost:5432/vmassit
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_EVENT_CHANNEL_PREFIX=trading:

# MEXC API Keys
MEXC_API_KEY=your_mexc_api_key
MEXC_API_SECRET=your_mexc_api_secret

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

---

## Database Migration

### 5. Run Alembic Migrations
```bash
# Initialize Alembic (if not already done)
alembic init migrations

# Run all migrations to create PostgreSQL schema
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, multi_agent_schema
```

### 6. (Optional) Migrate from SQLite to PostgreSQL
If you have existing data in SQLite:

```bash
python scripts/migrate_to_postgres.py
```

This script will:
- Export SQLite data to JSON
- Create PostgreSQL schema
- Import data into PostgreSQL
- Verify data integrity

---

## Testing

### 7. Run Integration Tests
```bash
# Test repository layer
pytest tests/test_sync_architecture.py -v

# Expected results:
# test_position_repository_upsert PASSED
# test_trade_repository_lifecycle PASSED
# test_reconciliation_service PASSED
# test_event_bus_publish_subscribe PASSED
# test_sync_agent_initialization PASSED
```

### 8. Validate Configuration
```bash
python test_config.py
```

---

## Deployment

### 9. Start the Application
```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode (with systemd or supervisor)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 10. Monitor Startup Logs
Watch for these success indicators:

```
✅ PostgreSQL database initialized
✅ Agents initialized
✅ Recovery completed
✅ Sync agent with WebSocket started
🔌 Connecting to MEXC WebSocket: wss://contract.mexc.com/ws
✅ MEXC WebSocket connected
📡 Subscribed to position@xautusdt
📡 Subscribed to order@xautusdt
✅ Reconciliation loop started
```

---

## Verification

### 11. Check WebSocket Connection
The logs should show:
```
✅ MEXC WebSocket connected
📊 Position synced: XAUT/USDT
```

If you see reconnection messages:
```
⚠️ WEBSOCKET DISCONNECTED
🔄 Reconnecting in 2s...
```
This is normal during initial setup. The system will auto-reconnect.

### 12. Verify Reconciliation
Every 2 minutes, you should see:
```
🔍 Reconciliation: Starting DEMO mode check...
✅ Reconciliation: No mismatches found
```

Or if mismatches are found and repaired:
```
⚠️  Position in exchange but not in DB: XAUT/USDT
✅ Reconciliation: Repaired 1 mismatches
```

### 13. Test Telegram Notifications
Trigger a test trade or wait for the next signal. You should receive:
```
🟢 LIVE TRADE OPENED
Symbol: XAUT/USDT
Side: LONG
Entry: $3,350.00
...
```

### 14. Monitor Database
Connect to PostgreSQL and verify tables:
```bash
psql -U your_user -d vmassit

# Check tables
\dt

# Expected tables:
# - trades
# - positions
# - order_events
# - sync_logs
# - telegram_notifications

# Check open positions
SELECT * FROM positions WHERE status = 'open';

# Check recent trades
SELECT id, symbol, status, pnl FROM trades ORDER BY created_at DESC LIMIT 10;

\q
```

---

## Troubleshooting

### Issue: WebSocket keeps disconnecting
**Solution:**
1. Check internet connection
2. Verify MEXC API credentials
3. Check firewall settings (port 443 for WSS)
4. Review logs for specific error messages

### Issue: PostgreSQL connection refused
**Solution:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check pg_hba.conf allows connections
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Ensure this line exists:
local   vmassit   your_user   md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Issue: Redis connection failed
**Solution:**
```bash
# Check if Redis is running
sudo systemctl status redis-server

# Test Redis connection
redis-cli ping

# If not running, start it
sudo systemctl start redis-server
```

### Issue: Database migration errors
**Solution:**
```bash
# Check current migration status
alembic current

# If stuck, downgrade and retry
alembic downgrade base
alembic upgrade head
```

---

## Monitoring & Maintenance

### Daily Checks
1. **Review Telegram alerts** - Look for sync mismatches or API errors
2. **Check reconciliation logs** - Ensure no persistent mismatches
3. **Monitor database size** - PostgreSQL should grow steadily
4. **Verify WebSocket uptime** - Should stay connected >99% of time

### Weekly Tasks
1. **Database backup**
   ```bash
   pg_dump -U your_user vmassit > backups/vmassit_$(date +%Y%m%d).sql
   ```

2. **Review order_events table** - Audit trail for all trades
   ```sql
   SELECT event_type, COUNT(*) 
   FROM order_events 
   GROUP BY event_type 
   ORDER BY COUNT(*) DESC;
   ```

3. **Check for ghost positions**
   ```sql
   SELECT p.symbol, p.status, t.status as trade_status
   FROM positions p
   LEFT JOIN trades t ON p.trade_id = t.id
   WHERE p.status = 'open' AND t.status = 'closed';
   ```

### Monthly Tasks
1. **Performance analysis** - Review win rate, PnL, drawdown
2. **Database cleanup** - Archive old closed trades (>6 months)
3. **Update dependencies** - `pip install --upgrade -r requirements.txt`
4. **Review reconciliation effectiveness** - Track mismatch frequency

---

## Success Metrics

After deployment, monitor these KPIs:

| Metric | Target | How to Check |
|--------|--------|--------------|
| WebSocket uptime | >99% | Logs: count disconnections |
| Sync latency | <5 seconds | Timestamp diff: exchange → DB |
| Reconciliation accuracy | 100% | No unresolved mismatches |
| Recovery time | <30 seconds | Time from restart to synced state |
| Duplicate orders | 0 | Check order_events for duplicates |
| Telegram delivery | 100% | All events trigger notifications |

---

## Rollback Plan

If issues occur after deployment:

1. **Stop application**
   ```bash
   sudo systemctl stop vmassit
   ```

2. **Revert to SQLite (emergency)**
   ```bash
   # Update .env
   DATABASE_URL=sqlite+aiosqlite:///./data/vmassit.db
   
   # Restart
   sudo systemctl start vmassit
   ```

3. **Restore from backup**
   ```bash
   psql -U your_user vmassit < backups/vmassit_YYYYMMDD.sql
   ```

---

## Support & Resources

- **Logs location:** `/var/log/vmassit/` or application stdout
- **Database docs:** `app/storage/models.py`
- **Event types:** `app/events/event_types.py`
- **WebSocket manager:** `app/exchange/websocket_manager.py`
- **Reconciliation logic:** `app/services/reconciliation_service.py`

---

## Next Steps After Deployment

1. **Enable monitoring dashboard** (Grafana + Prometheus)
2. **Set up alerting** (PagerDuty, Slack webhooks)
3. **Configure automated backups** (daily cron job)
4. **Implement CI/CD pipeline** (GitHub Actions, GitLab CI)
5. **Add load testing** (simulate high-frequency trading)

---

**Deployment Date:** _______________  
**Deployed By:** _______________  
**Verified By:** _______________  

✅ All checks passed - System ready for production trading
