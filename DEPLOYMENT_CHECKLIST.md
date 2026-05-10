# 🚀 Deployment Checklist - Auto Trade System (Optimized)

## Pre-Deployment Verification

### ✅ Environment Setup

```bash
# 1. Verify Python version (3.11+)
python --version

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Check dependencies
pip list | grep -E "fastapi|sqlalchemy|ccxt|openai"

# 4. Verify .env file exists and is configured
cat .env | grep -E "OPENROUTER|BINANCE|TELEGRAM"
```

### ✅ Configuration Check

Run the integration test to verify all configs:

```bash
python scripts/test_complete_integration.py
```

**Expected Output:**
```
✅ OpenRouter API Key: OK
✅ Binance API Key: OK
✅ Telegram Bot Token: OK
✅ Database URL: OK
✅ Execution Mode: OK
🎉 ALL INTEGRATION TESTS PASSED!
```

---

## Staging Deployment

### Step 1: Deploy to Staging Server

```bash
# Copy files to staging
scp -r auto-trade-system/ user@staging-server:/opt/

# SSH to staging server
ssh user@staging-server

# Navigate to app directory
cd /opt/auto-trade-system

# Activate environment
source .venv/bin/activate
```

### Step 2: Run with Testnet

Ensure `.env` has:
```bash
BINANCE_TESTNET=true
EXECUTION_MODE=semi-auto
```

### Step 3: Start Application

```bash
# Start with uvicorn
python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
```

### Step 4: Monitor for 1 Week

Track these metrics daily:

```bash
# Check system status
curl http://localhost:8000/api/status

# View logs
tail -f logs/app.log

# Check database
sqlite3 data/vmassit.db "SELECT COUNT(*) FROM paper_trades;"
```

**Key Metrics to Watch:**
- [ ] Daily LLM cost < $1
- [ ] Tier 3 usage < 15% of total
- [ ] No critical errors in logs
- [ ] Telegram notifications working
- [ ] Database growing normally

---

## Production Deployment

### Step 1: Switch to Mainnet

Update `.env`:
```bash
BINANCE_TESTNET=false
BINANCE_API_KEY=your-mainnet-key
BINANCE_API_SECRET=your-mainnet-secret
EXECUTION_MODE=proposal  # Start conservative
```

### Step 2: Set Up Process Manager

#### Option A: systemd (Recommended)

Create `/etc/systemd/system/auto-trade.service`:

```ini
[Unit]
Description=Auto Trade System
After=network.target

[Service]
Type=simple
User=admin
WorkingDirectory=/opt/auto-trade-system
Environment="PATH=/opt/auto-trade-system/.venv/bin"
ExecStart=/opt/auto-trade-system/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable auto-trade
sudo systemctl start auto-trade
sudo systemctl status auto-trade
```

#### Option B: PM2

```bash
npm install -g pm2

pm2 start "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000" \
    --name auto-trade \
    --interpreter python

pm2 save
pm2 startup
```

### Step 3: Set Up Monitoring

#### Health Check Endpoint

Add to crontab (`crontab -e`):

```bash
# Check health every 5 minutes
*/5 * * * * curl -f http://localhost:8000/health || echo "ALERT: System down!" | mail -s "Trade System Alert" admin@example.com
```

#### Log Rotation

Create `/etc/logrotate.d/auto-trade`:

```
/opt/auto-trade-system/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 admin admin
}
```

### Step 4: Configure Alerts

Set up Telegram alerts for:
- [ ] System downtime
- [ ] High error rates (>5%)
- [ ] Unusual cost spikes
- [ ] Daily P&L summary

---

## Post-Deployment Validation

### Day 1 Checks

```bash
# 1. Verify system is running
systemctl status auto-trade

# 2. Check API endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/status

# 3. Verify database connectivity
sqlite3 data/vmassit.db ".tables"

# 4. Test Telegram notifications
python -c "from app.infra.telegram_notifier import TelegramNotifier; import asyncio; asyncio.run(TelegramNotifier().send_message('System deployed successfully!'))"

# 5. Review logs
tail -100 logs/app.log
```

### Week 1 Review

Check these metrics after 7 days:

```python
# Run analysis script
python -c "
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('data/vmassit.db')
cursor = conn.cursor()

# Total trades
cursor.execute('SELECT COUNT(*) FROM paper_trades')
print(f'Total Trades: {cursor.fetchone()[0]}')

# Win rate
cursor.execute('''
    SELECT 
        COUNT(CASE WHEN pnl > 0 THEN 1 END) * 100.0 / COUNT(*) as win_rate
    FROM paper_trades
''')
print(f'Win Rate: {cursor.fetchone()[0]:.2f}%')

# Total P&L
cursor.execute('SELECT SUM(pnl) FROM paper_trades')
print(f'Total P&L: ${cursor.fetchone()[0]:.2f}')

conn.close()
"
```

**Success Criteria:**
- [ ] At least 10 trades executed
- [ ] Win rate > 45%
- [ ] No system crashes
- [ ] Cost < $7 for the week
- [ ] All Telegram alerts working

---

## Scaling Considerations

### If Load Increases

1. **Add Redis Cache**
   ```bash
   pip install redis
   # Update app/cache/three_tier_cache.py to use Redis
   ```

2. **Horizontal Scaling**
   ```bash
   # Use load balancer with multiple instances
   # Share database via PostgreSQL instead of SQLite
   DATABASE_URL=postgresql://user:pass@db-host:5432/trading
   ```

3. **Async Task Queue**
   ```bash
   pip install dramatiq redis
   # Move batch learning to background jobs
   ```

### If Costs Increase

1. **Review Tier Distribution**
   ```python
   commander = AgentCommander()
   stats = commander.get_system_status()['router_stats']
   print(stats)
   ```
   
   Adjust thresholds if Tier 3 > 15%

2. **Tighten Event Triggers**
   ```python
   # In EventBasedNewsSentiment
   self.price_move_threshold = 0.07  # Increase from 5% to 7%
   self.social_volume_threshold = 4.0  # Increase from 3x to 4x
   ```

3. **Reduce Batch Frequency**
   ```python
   # Change from daily to every 3 days
   # Or increase minimum trades before analysis
   ```

---

## Backup & Recovery

### Daily Backups

Already configured via `systemd/vmassit-backup.timer`

Verify it's running:
```bash
systemctl list-timers | grep vmassit
```

### Manual Backup

```bash
# Backup database
cp data/vmassit.db backups/vmassit_$(date +%Y%m%d).db

# Backup configuration
cp .env backups/env_$(date +%Y%m%d)

# Compress and store
tar czf backup_$(date +%Y%m%d).tar.gz backups/
```

### Restore from Backup

```bash
# Stop service
sudo systemctl stop auto-trade

# Restore database
cp backups/vmassit_20260511.db data/vmassit.db

# Restore config
cp backups/env_20260511 .env

# Start service
sudo systemctl start auto-trade
```

---

## Troubleshooting Guide

### System Won't Start

```bash
# Check logs
journalctl -u auto-trade -n 50

# Common issues:
# 1. Port already in use
sudo lsof -i :8000

# 2. Missing dependencies
source .venv/bin/activate
pip install -r requirements.txt

# 3. Permission issues
chmod 644 data/vmassit.db
chown admin:admin data/vmassit.db
```

### High Error Rate

```bash
# Check error logs
grep "ERROR" logs/app.log | tail -20

# Common causes:
# 1. API rate limits - Reduce frequency
# 2. Invalid credentials - Verify .env
# 3. Network issues - Check connectivity
```

### Unexpected Costs

```bash
# Review router stats
python -c "
from app.ai.agent_commander import AgentCommander
import asyncio

async def check():
    c = AgentCommander()
    print(c.get_system_status()['router_stats'])

asyncio.run(check())
"

# If Tier 3 too high, adjust uncertainty thresholds
```

### Database Issues

```bash
# Check database integrity
sqlite3 data/vmassit.db "PRAGMA integrity_check;"

# Vacuum to reclaim space
sqlite3 data/vmassit.db "VACUUM;"

# Check size
ls -lh data/vmassit.db
```

---

## Performance Optimization

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_timestamp ON paper_trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_decision_journal_user ON decision_journal(user_id);

-- Analyze query performance
EXPLAIN QUERY PLAN SELECT * FROM paper_trades WHERE symbol = 'BTC/USDT';
```

### Cache Optimization

```python
# In app/config.py
CACHE_TTL_MARKET_DATA = 30  # seconds
CACHE_TTL_AI_ANALYSIS = 300  # 5 minutes
CACHE_MAX_SIZE = 1000  # entries
```

### Memory Management

```bash
# Monitor memory usage
ps aux | grep uvicorn

# If using too much memory, add limits
# In systemd service file:
MemoryLimit=512M
```

---

## Security Checklist

- [ ] API keys stored in `.env` (not in code)
- [ ] `.env` added to `.gitignore`
- [ ] Database file permissions restricted (644)
- [ ] Firewall configured (only allow necessary ports)
- [ ] SSL/TLS enabled for API endpoints
- [ ] Regular security updates applied
- [ ] Backup encryption enabled
- [ ] Access logs monitored

---

## Maintenance Schedule

### Daily
- [ ] Check system health
- [ ] Review error logs
- [ ] Verify Telegram alerts
- [ ] Monitor costs

### Weekly
- [ ] Review trading performance
- [ ] Check database size
- [ ] Update dependencies (if needed)
- [ ] Review tier distribution

### Monthly
- [ ] Full system backup
- [ ] Security audit
- [ ] Performance review
- [ ] Strategy optimization review

### Quarterly
- [ ] Major version updates
- [ ] Architecture review
- [ ] Cost-benefit analysis
- [ ] Disaster recovery test

---

## Success Metrics Dashboard

Create a simple dashboard:

```python
# scripts/dashboard.py
import sqlite3
from datetime import datetime, timedelta

def generate_report():
    conn = sqlite3.connect('data/vmassit.db')
    cursor = conn.cursor()
    
    # Last 7 days
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    print("="*60)
    print("WEEKLY PERFORMANCE REPORT")
    print("="*60)
    
    # Trades
    cursor.execute('''
        SELECT COUNT(*) FROM paper_trades WHERE timestamp > ?
    ''', (week_ago,))
    print(f"Trades This Week: {cursor.fetchone()[0]}")
    
    # Win Rate
    cursor.execute('''
        SELECT 
            COUNT(CASE WHEN pnl > 0 THEN 1 END) * 100.0 / COUNT(*)
        FROM paper_trades 
        WHERE timestamp > ?
    ''', (week_ago,))
    print(f"Win Rate: {cursor.fetchone()[0]:.2f}%")
    
    # P&L
    cursor.execute('''
        SELECT SUM(pnl), AVG(pnl) 
        FROM paper_trades 
        WHERE timestamp > ?
    ''', (week_ago,))
    row = cursor.fetchone()
    print(f"Total P&L: ${row[0]:.2f}")
    print(f"Avg P&L per Trade: ${row[1]:.2f}")
    
    # Best/Worst
    cursor.execute('''
        SELECT symbol, MAX(pnl) FROM paper_trades WHERE timestamp > ?
    ''', (week_ago,))
    print(f"Best Trade: {cursor.fetchone()}")
    
    cursor.execute('''
        SELECT symbol, MIN(pnl) FROM paper_trades WHERE timestamp > ?
    ''', (week_ago,))
    print(f"Worst Trade: {cursor.fetchone()}")
    
    conn.close()

if __name__ == "__main__":
    generate_report()
```

Run weekly:
```bash
python scripts/dashboard.py
```

---

## Final Checklist Before Go-Live

- [ ] All validation tests passing
- [ ] Staging tested for 1+ week
- [ ] Monitoring and alerts configured
- [ ] Backup system verified
- [ ] Documentation reviewed
- [ ] Team trained on operations
- [ ] Emergency procedures documented
- [ ] Budget approved for ongoing costs
- [ ] Legal/compliance reviewed (if applicable)
- [ ] Rollback plan tested

---

## 🎉 You're Ready!

Once all checkboxes are complete, you're ready for production deployment!

**Remember:**
- Start with `proposal` or `semi-auto` mode
- Monitor closely for first 2 weeks
- Gradually increase automation as confidence grows
- Keep backups current
- Review performance weekly

**Good luck with your optimized trading system!** 🚀

---

*Last Updated: 2026-05-11*  
*Version: 2.0.0 (Optimized)*  
*Status: Production Ready* ✅
