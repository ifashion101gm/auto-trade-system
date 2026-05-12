# MEXC Order Handling - Quick Reference Guide

## 🚀 Quick Start

### Before Trading (Required)
```bash
# 1. Run validation tests
python scripts/test_mexc_order_handling.py

# 2. Check logs for errors
tail -f /var/log/vmassit/app.log | grep -E "(ERROR|CRITICAL)"
```

### Test Small Trade
```bash
# Testnet (safe)
python scripts/execute_gold_trade.py --testnet --amount 0.001

# Live (use with caution)
python scripts/execute_gold_trade.py --live --amount 0.001
```

## 📋 Key Components

### 1. MexcExecutor (`app/exchange/mexc_executor.py`)
**Purpose**: MEXC-specific order handling with position-side awareness

**Methods**:
```python
# Open positions
await executor.open_long(symbol, amount, leverage)
await executor.open_short(symbol, amount, leverage)

# Close positions (uses reduce-only automatically)
await executor.close_long(symbol, amount=None)
await executor.close_short(symbol, amount=None)

# Get data
positions = await executor.get_open_positions()
balance = await executor.get_balance()
ticker = await executor.get_ticker(symbol)
```

**Symbol Mapping** (automatic):
- `GOLD(XAUT)/USDT` → `GOLD_USDT`
- `BTCUSDT` → `BTC_USDT`
- `ETHUSDT` → `ETH_USDT`

### 2. PositionSyncService (`app/services/position_sync.py`)
**Purpose**: Continuous sync between exchange and database (every 5s)

**Detects & Repairs**:
- Ghost positions (in DB but not on exchange)
- Orphaned positions (on exchange but not in DB)
- Data mismatches (size/price differences)
- Trade-position inconsistencies

**Monitoring**:
```python
status = await sync_service.get_sync_status()
# Returns: {'status': 'healthy', 'exchange_positions': 2, ...}
```

### 3. Updated Exchanges
- `app/exchange/mexc_live.py` - Now uses MexcExecutor
- `app/exchange/mexc_demo.py` - Supports testnet + local simulation

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Required
MEXC_API_KEY=your_key
MEXC_API_SECRET=your_secret

# Optional (for paper trading)
MEXC_PAPER_API_KEY=demo_key
MEXC_PAPER_API_SECRET=demo_secret

# Settings
ACTIVE_EXCHANGE=mexc
GOLD_SYMBOL_MEXC=GOLD(XAUT)/USDT  # Auto-normalized
LIVE_TRADING_MAX_LEVERAGE=3
```

### Position Sync Interval
Default: 5 seconds  
Change in `app/services/position_sync.py`:
```python
self._sync_interval = 5  # Change this value
```

## 🐛 Troubleshooting

### Common Errors

#### "Invalid symbol" Error
**Cause**: Symbol format mismatch  
**Fix**: Already handled by `MexcExecutor._normalize_symbol()`  
**Check**: Logs should show normalized symbol

#### "Insufficient balance" Error
**Cause**: Leverage too high or position size too large  
**Fix**: Reduce leverage or position size  
**Check**: `LIVE_TRADING_MAX_LEVERAGE` in config

#### Position Won't Close
**Cause**: Not using reduce-only flag  
**Fix**: Already fixed - all closes use reduce-only  
**Check**: Logs should show "reduce-only" message

#### Duplicate Positions
**Cause**: Hedge mode not detected  
**Fix**: Already fixed - auto-detects position mode  
**Check**: Logs should show "Detected HEDGE/ONE_WAY mode"

#### Database Out of Sync
**Cause**: Sync service not running  
**Fix**: Ensure `PositionSyncService` is started in main.py  
**Check**: Logs should show "Position sync started"

### Log Patterns to Watch

✅ **Success**:
```
✅ LONG opened: order_123456
✅ Position sync: All consistent
🟢 Opening LONG: 0.1 GOLD_USDT @3x
```

⚠️ **Warnings**:
```
⚠️  Retry attempt 2/3
⚠️  Could not set leverage: ...
⚠️  Repairing ghost position: GOLD_USDT
```

❌ **Errors**:
```
❌ Failed to place reduce-only order: ...
❌ Circuit breaker OPEN
❌ No open position found for GOLD_USDT
```

## 📊 Monitoring

### Health Check Endpoint
```bash
curl http://localhost:8000/api/health
```

### Key Metrics
- **Order Success Rate**: >95%
- **Sync Accuracy**: 100% (auto-repaired)
- **API Latency**: <500ms average
- **Position Drift**: 0 (should match exactly)

### Telegram Alerts
System sends alerts for:
- Critical sync mismatches
- Orphaned trades
- Order failures after retries
- Circuit breaker activations

## 🔄 Deployment Checklist

### Pre-Deployment
- [ ] Run `test_mexc_order_handling.py` - all tests pass
- [ ] Backup database: `./scripts/backup_database.sh`
- [ ] Review `.env` configuration
- [ ] Check API key permissions (Futures Trading enabled)

### Deployment
- [ ] Stop services: `sudo systemctl stop vmassit`
- [ ] Deploy code: `git pull` or `rsync`
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Start services: `sudo systemctl start vmassit`

### Post-Deployment
- [ ] Check logs: `tail -f /var/log/vmassit/app.log`
- [ ] Verify sync service started
- [ ] Monitor for first 10 minutes
- [ ] Test small trade (0.001 GOLD)

### Rollback Plan
If issues occur:
```bash
sudo systemctl stop vmassit
git checkout HEAD~1
./scripts/restore_database.sh backup.sql
sudo systemctl start vmassit
```

## 🎯 Testing Strategy

### Phase 1: Testnet Validation
1. Run automated tests
2. Execute small market order (0.001 GOLD)
3. Verify position appears on MEXC dashboard
4. Test position closure
5. Verify database sync

### Phase 2: Live Trading (Small)
1. Start with minimum position (0.001 GOLD)
2. Monitor for 5 minutes
3. Verify P&L updates correctly
4. Test manual closure via dashboard
5. Test automated closure (SL/TP)

### Phase 3: Scale Up
1. Increase position size gradually
2. Monitor success rate
3. Track slippage and fees
4. Adjust leverage if needed

## 📞 Support

### Check Logs First
```bash
# Application logs
tail -f /var/log/vmassit/app.log

# Filter errors
grep "ERROR" /var/log/vmassit/app.log | tail -20

# Filter sync issues
grep "SYNC" /var/log/vmassit/app.log | tail -20
```

### Common Commands
```bash
# Check running services
sudo systemctl status vmassit

# Restart services
sudo systemctl restart vmassit

# View recent logs
journalctl -u vmassit -n 50 --no-pager

# Check database
psql -U user -d vmassit -c "SELECT * FROM trades ORDER BY created_at DESC LIMIT 5;"
```

## 🔐 Security Notes

### API Key Permissions
Required permissions:
- ✅ Futures Trading
- ✅ Read Account
- ✅ Order Access

**DO NOT enable**:
- ❌ Withdrawal
- ❌ Transfer

### Environment Separation
- Testnet: Use demo keys
- Live: Use production keys
- Never mix environments

### Backup Strategy
- Daily database backups (automated)
- Keep last 7 days of backups
- Store backups off-site

## 📈 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Order Success Rate | >98% | TBD |
| Sync Accuracy | 100% | TBD |
| API Latency | <500ms | TBD |
| Uptime | >99.9% | TBD |

## 🚨 Emergency Procedures

### If Orders Fail Repeatedly
1. Stop trading immediately
2. Check MEXC status page
3. Verify API key permissions
4. Review error logs
5. Contact support if needed

### If Database Corrupted
1. Stop services
2. Restore from backup
3. Run reconciliation
4. Verify positions match exchange
5. Restart services

### If Position Stuck
1. Try closing via MEXC dashboard
2. Wait for sync to detect change
3. If still stuck, manually update DB
4. Document incident for review

---

**Last Updated**: 2026-05-12  
**Version**: 1.0  
**Status**: Production Ready ✅
