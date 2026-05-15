# Phase 1 Deployment - Quick Reference Card

**Target:** Bybit Demo | **Risk:** NEGLIGIBLE | **Time:** 2-3 minutes

---

## 🚀 Deploy (One Command)

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system && bash deploy_phase1_bybit_demo.sh
```

---

## 🔙 Rollback (One Command)

```bash
bash rollback_phase1.sh  # Uses most recent backup
```

---

## ✅ Pre-Flight Check (30 seconds)

```bash
# 1. Verify code
python3 verify_freqtrade_integration.py

# 2. Check services
systemctl is-active auto-trade-api auto-trade-worker

# 3. Backup .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
```

---

## ⚙️ Configuration (.env additions)

```ini
ENABLE_PERSISTENT_IDEMPOTENCY=true
IDEMPOTENCY_TTL_SECONDS=3600
ENABLE_STATE_RECOVERY=true
CIRCUIT_BREAKER_PRE_EXECUTION_CHECK=true
RECONCILIATION_INTERVAL_SECONDS=120
RECONCILIATION_AUTO_REPAIR_SAFE=true
RECONCILIATION_TELEGRAM_ALERTS=true
RECONCILIATION_PROMETHEUS_METRICS=true
RECONCILIATION_MAX_ORPHANED_AGE_HOURS=24
RECONCILIATION_GHOST_POSITION_ACTION=import_and_alert
```

---

## 🔍 Post-Deploy Verification (2 minutes)

```bash
# Health check
curl -s http://localhost:8000/health | python3 -m json.tool

# Reconciliation status
curl -s http://localhost:8000/api/v1/reconciliation/status | python3 -m json.tool

# Open positions (verify unchanged)
curl -s http://localhost:8000/api/v1/trading/positions | python3 -m json.tool

# View logs
journalctl -u auto-trade-api -f --since "2 minutes ago"
```

---

## 📊 Monitor (First 24 Hours)

### Every 15 Minutes (Hour 1-2)
```bash
journalctl -u auto-trade-api -n 50 --since "15 minutes ago"
```

### Every Hour (Hour 3-6)
```bash
curl http://localhost:8000/api/v1/reconciliation/status
```

### Every 4 Hours (Hour 7-24)
```bash
systemctl status auto-trade-api auto-trade-worker
```

---

## 🎯 Key Metrics (Prometheus)

```promql
reconciliation_mismatches_total{mismatch_type="total"}
reconciliation_repairs_total{repair_type="auto_repair"}
circuit_breaker_state
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**Alert Thresholds:**
- Mismatches >5 in 10min → Investigate
- Circuit breaker = 1 → Trading blocked
- Latency p95 >1s → Performance issue

---

## 📱 Telegram Alerts

**Expected During Startup:**
```
🔧 Trade State Recovery completed
```

**Expected During Operation:**
```
⚠️ Orphaned Order Detected (auto-repaired)
🚨 Ghost Position Detected (imported)
```

**Too Many Alerts?**
```bash
echo "RECONCILIATION_TELEGRAM_ALERTS=false" >> .env
sudo systemctl restart auto-trade-worker
```

---

## 🚨 Emergency Commands

```bash
# Stop all trading
sudo systemctl stop auto-trade-worker

# Quick rollback
bash rollback_phase1.sh

# Check logs
journalctl -u auto-trade-api -n 100 --no-pager

# Restart services
sudo systemctl restart auto-trade-api auto-trade-worker
```

---

## 📚 Full Documentation

- **Deployment Guide:** PHASE1_DEPLOYMENT_GUIDE_BYBIT_DEMO.md
- **Executive Summary:** PHASE1_DEPLOYMENT_EXECUTIVE_SUMMARY.md
- **Technical Details:** IMPLEMENTATION_SUMMARY_FREQTRADE.md
- **Quick Ref (Freqtrade):** FREQTRADE_QUICKREF.md

---

**Print this page and keep handy during deployment!**
