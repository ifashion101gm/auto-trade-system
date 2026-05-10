# 📋 Quick Reference Card - Auto Trade System

## Daily Operations

### Start System
```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Check Status
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/status
```

### View Logs
```bash
tail -f logs/app.log
```

### Run Tests
```bash
python scripts/test_complete_integration.py
```

---

## Key Commands

### Database
```bash
# View tables
sqlite3 data/vmassit.db ".tables"

# Recent trades
sqlite3 data/vmassit.db "SELECT * FROM paper_trades ORDER BY timestamp DESC LIMIT 5;"

# Backup
cp data/vmassit.db backups/vmassit_$(date +%Y%m%d).db
```

### Process Management
```bash
# systemd
sudo systemctl status auto-trade
sudo systemctl restart auto-trade
sudo journalctl -u auto-trade -f

# PM2
pm2 status
pm2 restart auto-trade
pm2 logs auto-trade
```

### Performance Check
```bash
# Weekly report
python scripts/dashboard.py

# Router stats
python -c "from app.ai.agent_commander import AgentCommander; import asyncio; c=AgentCommander(); print(asyncio.run(c.get_system_status())['router_stats'])"
```

---

## Configuration Quick Edit

### Change Execution Mode
```bash
# Edit .env
EXECUTION_MODE=proposal      # Manual approval required
EXECUTION_MODE=semi-auto     # Confirm before execute
EXECUTION_MODE=fully-auto    # Automatic execution
```

### Switch Testnet/Mainnet
```bash
# Edit .env
BINANCE_TESTNET=true   # Safe testing
BINANCE_TESTNET=false  # Live trading
```

### Adjust Risk Parameters
```python
# In app/ai/optimized_agents.py
class DeterministicRiskManager:
    max_risk_per_trade = 0.02      # 2% per trade
    max_daily_drawdown = 0.05      # 5% daily limit
    max_loss_streak = 3            # Pause after 3 losses
```

---

## Troubleshooting Quick Fixes

### System Not Starting
```bash
# Check port
sudo lsof -i :8000

# Kill if stuck
pkill -f uvicorn

# Restart
sudo systemctl restart auto-trade
```

### High Costs
```bash
# Check tier distribution
python -c "
from app.ai.optimized_agents import OptimizedAgentRouter
r = OptimizedAgentRouter()
print(r.get_usage_stats())
"

# If Tier 3 > 15%, adjust thresholds in optimized_agents.py
```

### API Errors
```bash
# Verify credentials
cat .env | grep OPENROUTER
cat .env | grep BINANCE

# Test connectivity
python -c "import ccxt; print(ccxt.binance().fetch_ticker('BTC/USDT'))"
```

### Database Locked
```bash
# Remove lock files
rm data/vmassit.db-shm data/vmassit.db-wal

# Vacuum
sqlite3 data/vmassit.db "VACUUM;"
```

---

## Monitoring Alerts Setup

### Telegram Alert Thresholds
```python
# In app/infra/telegram_notifier.py
ALERT_THRESHOLDS = {
    'error_rate': 5.0,        # 5% error rate
    'daily_cost': 2.0,        # $2 per day
    'drawdown': 5.0,          # 5% drawdown
    'tier3_usage': 15.0       # 15% Tier 3 usage
}
```

### Cron Jobs
```bash
# Health check every 5 minutes
*/5 * * * * curl -f http://localhost:8000/health || mail -s "ALERT" admin@example.com

# Daily backup at midnight
0 0 * * * /opt/auto-trade-system/scripts/backup_database.sh

# Weekly report on Monday
0 9 * * 1 python /opt/auto-trade-system/scripts/dashboard.py >> /var/log/trading-report.log
```

---

## Common Scenarios

### Scenario 1: First Time Deployment
```bash
1. Copy files to server
2. Install dependencies: pip install -r requirements.txt
3. Configure .env with your API keys
4. Run tests: python scripts/test_complete_integration.py
5. Start with testnet: BINANCE_TESTNET=true
6. Monitor for 1 week
7. Switch to mainnet when confident
```

### Scenario 2: Cost Spike Detected
```bash
1. Check router stats
2. Review recent events that triggered Tier 3
3. Adjust uncertainty thresholds if needed
4. Tighten event triggers (increase thresholds)
5. Monitor next 24 hours
```

### Scenario 3: Poor Performance
```bash
1. Review win rate: python scripts/dashboard.py
2. Check strategy distribution in database
3. Analyze losing trades for patterns
4. Consider adjusting strategy weights
5. Run weekly optimization manually
```

### Scenario 4: System Crash
```bash
1. Check logs: journalctl -u auto-trade -n 100
2. Identify root cause
3. Fix issue (config, code, or infrastructure)
4. Restore from backup if needed
5. Restart service
6. Verify functionality
```

---

## Essential Files

| File | Purpose | When to Edit |
|------|---------|--------------|
| `.env` | Configuration | Initial setup, credential changes |
| `app/config.py` | Settings schema | Adding new config options |
| `app/ai/optimized_agents.py` | Core logic | Adjusting thresholds, strategies |
| `app/infra/telegram_notifier.py` | Alerts | Customizing notifications |
| `scripts/dashboard.py` | Reporting | Adding new metrics |

---

## Safety Checks Before Trading

```bash
# 1. Verify testnet mode (if testing)
grep BINANCE_TESTNET .env

# 2. Check risk limits
python -c "from app.ai.optimized_agents import DeterministicRiskManager; r=DeterministicRiskManager(); print(f'Max Risk: {r.max_risk_per_trade*100}%')"

# 3. Confirm execution mode
grep EXECUTION_MODE .env

# 4. Test Telegram alerts
python -c "from app.infra.telegram_notifier import TelegramNotifier; import asyncio; asyncio.run(TelegramNotifier().send_message('Test alert'))"

# 5. Verify database
sqlite3 data/vmassit.db "PRAGMA integrity_check;"
```

---

## Quick Stats Commands

```bash
# Total trades today
sqlite3 data/vmassit.db "SELECT COUNT(*) FROM paper_trades WHERE date(timestamp) = date('now');"

# Today's P&L
sqlite3 data/vmassit.db "SELECT SUM(pnl) FROM paper_trades WHERE date(timestamp) = date('now');"

# Win rate this week
sqlite3 data/vmassit.db "SELECT COUNT(CASE WHEN pnl > 0 THEN 1 END) * 100.0 / COUNT(*) FROM paper_trades WHERE timestamp > datetime('now', '-7 days');"

# Most traded symbol
sqlite3 data/vmassit.db "SELECT symbol, COUNT(*) as cnt FROM paper_trades GROUP BY symbol ORDER BY cnt DESC LIMIT 1;"

# Average trade size
sqlite3 data/vmassit.db "SELECT AVG(ABS(pnl)) FROM paper_trades;"
```

---

## Emergency Procedures

### Stop All Trading Immediately
```bash
# Method 1: Change execution mode
echo "EXECUTION_MODE=proposal" >> .env
sudo systemctl restart auto-trade

# Method 2: Stop service
sudo systemctl stop auto-trade

# Method 3: Kill process
pkill -f uvicorn
```

### Revert to Previous Version
```bash
# If using git
git stash                    # Save current changes
git checkout previous-tag    # Revert to stable version
sudo systemctl restart auto-trade
```

### Emergency Backup
```bash
# Quick backup
tar czf emergency_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    data/vmassit.db \
    .env \
    logs/
```

---

## Contact & Support

- **Documentation:** See `README_OPTIMIZED.md`
- **Architecture:** See `OPTIMIZED_AGENT_ARCHITECTURE.md`
- **Integration:** See `OPTIMIZATION_INTEGRATION_GUIDE.md`
- **Deployment:** See `DEPLOYMENT_CHECKLIST.md`

---

## Remember

✅ **Start conservative** - Use proposal mode first  
✅ **Monitor daily** - Check logs and metrics  
✅ **Backup regularly** - Never skip backups  
✅ **Test thoroughly** - Always test on testnet first  
✅ **Stay informed** - Review performance weekly  

---

*Keep this card handy for quick reference!* 📌
