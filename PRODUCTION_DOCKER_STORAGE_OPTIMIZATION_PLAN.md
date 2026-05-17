# 🚀 Production Docker Storage & Optimization Plan

**Version:** 1.0  
**Last Updated:** May 17, 2026  
**Status:** Production-Ready  
**Target Environment:** Auto Trade System (Bybit/MEXC)

---

## 📋 Executive Summary

This document defines the production-ready Docker storage architecture, operational hygiene standards, and optimization strategies for the Auto Trade System. The plan ensures:

- ✅ **Data Persistence** - Separate mount points for databases, logs, and monitoring
- ✅ **Disk Space Management** - Automated log rotation and cleanup policies
- ✅ **Performance Optimization** - PostgreSQL tuning and resource limits
- ✅ **Operational Safety** - Monitoring, alerting, and backup procedures
- ✅ **Zero-Downtime Maintenance** - Clean separation of code and data

---

## 1. 🗂️ Recommended Storage Layout

### Host Directory Structure

Use dedicated mount points to separate application binaries from runtime data:

```
/opt/
├── apps/                          # Application code & deployment artifacts
│   └── auto-trade-system/         # Git repository root
│       ├── app/                   # Python application code
│       ├── docker-compose.yml     # Docker orchestration
│       └── .env.prod              # Production environment variables

/data/                             # All persistent data (separate disk recommended)
├── postgres/                      # PostgreSQL database files
├── redis/                         # Redis persistence (RDB/AOF)
├── prometheus/                    # Prometheus TSDB storage
├── grafana/                       # Grafana dashboards & plugins
├── loki/                          # Loki log storage
├── logs/                          # Application logs (text + JSON)
│   ├── all_*.log                  # Combined structured logs
│   ├── json_*.log                 # JSON-formatted logs
│   └── deployment_monitor.log     # Deployment monitoring logs
├── app/                           # App runtime data & caches
│   ├── vmassit.db                 # SQLite database (if used)
│   └── .risk_state.json           # Risk engine state
├── backups/                       # Database & archive backups
│   └── vmassit_db_*.db.gz         # Compressed database backups
└── metrics/                       # Long-term metrics exports/snapshots
```

### ⚠️ Critical Rules

1. **NEVER store service data under root filesystem `/`** - Use `/data` or dedicated disk
2. **Separate disks for databases** - PostgreSQL and Redis should have dedicated SSDs if possible
3. **Backup directory on separate volume** - Prevents backup corruption during disk failures
4. **Logs on fast storage** - Ensures minimal I/O impact on trading performance

---

## 2. 🐳 Docker Compose Storage Configuration

### Current Implementation

The `docker-compose.yml` now uses **bind mounts** with environment variable defaults:

```yaml
services:
  postgres:
    volumes:
      - ${POSTGRES_DATA_DIR:-/data/postgres}:/var/lib/postgresql/data
  
  redis:
    volumes:
      - ${REDIS_DATA_DIR:-/data/redis}:/data
  
  prometheus:
    volumes:
      - ${PROMETHEUS_DATA_DIR:-/data/prometheus}:/prometheus
  
  grafana:
    volumes:
      - ${GRAFANA_DATA_DIR:-/data/grafana}:/var/lib/grafana
  
  loki:
    volumes:
      - ${LOKI_DATA_DIR:-/data/loki}:/loki
  
  trading-bot:
    volumes:
      - ${APP_LOG_DIR:-/data/logs}:/app/logs
      - ${APP_DATA_DIR:-/data/app}:/app/data
  
  trading-worker:
    volumes:
      - ${APP_LOG_DIR:-/data/logs}:/app/logs
      - ${APP_DATA_DIR:-/data/app}:/app/data
```

### Benefits

- ✅ **Clean separation** - Database, logs, monitoring, and app state isolated
- ✅ **Easy migration** - Move `/data` to new disk without changing configs
- ✅ **Backup simplicity** - Single directory contains all persistent data
- ✅ **Permission control** - Different ownership per service

---

## 3. 📝 Docker Log Size Limits

### Per-Service Logging Configuration

All services in `docker-compose.yml` now include logging limits:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "100m"    # Max 100MB per log file
    max-file: "3"       # Keep only 3 rotated files (300MB total)
```

### Impact

- **Prevents disk exhaustion** - Container logs capped at ~300MB per service
- **Automatic rotation** - Old logs compressed and removed automatically
- **No manual intervention** - Docker handles rotation transparently

### Affected Services

- `trading-bot` (API server)
- `trading-worker` (background tasks)
- `postgres` (database logs)
- `redis` (cache logs)
- `prometheus`, `grafana`, `loki` (monitoring stack)

---

## 4. 🔧 Environment Variables

### `.env.prod` Configuration

Create `.env.prod` from `.env.example` with production-specific values:

```bash
cp .env.example .env.prod
```

### Required Storage Variables

```env
# =============================================================================
# PRODUCTION STORAGE PATHS
# =============================================================================

# Base data directory (all persistent data lives here)
HOST_DATA_DIR=/data

# Database storage
POSTGRES_DATA_DIR=${HOST_DATA_DIR}/postgres
REDIS_DATA_DIR=${HOST_DATA_DIR}/redis

# Monitoring stack storage
PROMETHEUS_DATA_DIR=${HOST_DATA_DIR}/prometheus
GRAFANA_DATA_DIR=${HOST_DATA_DIR}/grafana
LOKI_DATA_DIR=${HOST_DATA_DIR}/loki

# Application storage
APP_LOG_DIR=${HOST_DATA_DIR}/logs
APP_DATA_DIR=${HOST_DATA_DIR}/app

# Backup storage (consider separate disk for backups)
BACKUP_DIR=${HOST_DATA_DIR}/backups

# =============================================================================
# PRODUCTION SECURITY SETTINGS
# =============================================================================

# Force strong passwords (never use defaults!)
DB_PASSWORD=<STRONG_PASSWORD_HERE>
GRAFANA_PASSWORD=<STRONG_PASSWORD_HERE>

# Exchange API keys (use demo keys for validation first)
BYBIT_API_KEY=<YOUR_BYBIT_API_KEY>
BYBIT_API_SECRET=<YOUR_BYBIT_API_SECRET>
BYBIT_TESTNET=true  # Set to false ONLY after 48h validation

# Telegram notifications
TELEGRAM_BOT_TOKEN=<YOUR_TELEGRAM_BOT_TOKEN>
TELEGRAM_CHAT_ID=<YOUR_TELEGRAM_CHAT_ID>

# =============================================================================
# EXECUTION MODE (CRITICAL FOR SAFETY)
# =============================================================================

# Start with 'paper' mode, then 'semi-auto', finally 'fully-auto'
EXECUTION_MODE=paper

# Trading symbols
ENABLED_TRADING_SYMBOLS=XAUUSDT

# Self-healing thresholds
MAX_EXECUTION_RETRIES=3
MAX_SLIPPAGE_PCT=0.5
MAX_API_LATENCY_MS=5000
MAX_DRAWDOWN_PCT=5.0
```

### Security Notes

⚠️ **NEVER commit `.env.prod` to version control**  
⚠️ **Use `.gitignore` to exclude all `.env*` files except `.env.example`**  
⚠️ **Rotate API keys immediately if accidentally committed**

---

## 5. 🧹 Docker Cleanup Automation

### Scheduled Cleanup Cron Jobs

Add to system crontab (`sudo crontab -e`):

```cron
# Daily cleanup at 3:00 AM
0 3 * * * /usr/bin/docker system prune -af --volumes >> /var/log/docker-cleanup.log 2>&1
0 3 * * * /usr/bin/docker builder prune -af >> /var/log/docker-cleanup.log 2>&1

# Weekly deep cleanup (Sunday 4:00 AM)
0 4 * * 0 /usr/bin/docker image prune -af --filter "until=168h" >> /var/log/docker-cleanup.log 2>&1
```

### What Gets Cleaned

- **Stopped containers** - Removes exited containers
- **Unused networks** - Cleans orphaned Docker networks
- **Dangling images** - Removes untagged images
- **Build cache** - Frees space from intermediate build layers
- **Unused volumes** - Removes anonymous volumes (use `--volumes` flag carefully)

### Monitoring Cleanup

Check cleanup effectiveness:

```bash
# Check Docker disk usage
docker system df

# View cleanup logs
tail -f /var/log/docker-cleanup.log

# Manual cleanup (if needed)
docker system prune -af
```

---

## 6. ⚙️ Docker Daemon Logging Configuration

### Host-Level Log Management

Configure `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "features": {
    "buildkit": true
  }
}
```

### Apply Changes

```bash
# Restart Docker daemon
sudo systemctl restart docker

# Verify configuration
docker info | grep -A 5 "Logging Driver"
```

### Why This Matters

- **Prevents host disk exhaustion** - Even if container logging fails
- **Consistent behavior** - All containers inherit these limits
- **Fallback protection** - Works even if docker-compose logging is misconfigured

---

## 7. 🗄️ PostgreSQL Optimization

### Production Tuning Parameters

Add to `postgresql.conf` or set via environment variables in `docker-compose.yml`:

```yaml
services:
  postgres:
    environment:
      POSTGRES_MAX_CONNECTIONS: "100"
      POSTGRES_SHARED_BUFFERS: "256MB"
      POSTGRES_EFFECTIVE_CACHE_SIZE: "768MB"
      POSTGRES_WORK_MEM: "4MB"
      POSTGRES_MAINTENANCE_WORK_MEM: "64MB"
    
    command:
      - "postgres"
      - "-c"
      - "wal_keep_size=128MB"
      - "-c"
      - "checkpoint_timeout=15min"
      - "-c"
      - "max_wal_size=1GB"
      - "-c"
      - "min_wal_size=80MB"
      - "-c"
      - "autovacuum=on"
      - "-c"
      - "autovacuum_max_workers=3"
      - "-c"
      - "autovacuum_naptime=60s"
```

### Key Optimizations

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `wal_keep_size` | 128MB | Prevents WAL file accumulation |
| `checkpoint_timeout` | 15min | Reduces checkpoint frequency |
| `max_wal_size` | 1GB | Caps WAL growth before forced checkpoint |
| `min_wal_size` | 80MB | Maintains minimum WAL for performance |
| `autovacuum` | on | Automatic table maintenance |
| `shared_buffers` | 256MB | PostgreSQL memory cache (25% of RAM) |
| `effective_cache_size` | 768MB | Query planner hint (75% of RAM) |

### Data Archival Strategy

For long-running systems, archive old trades:

```sql
-- Archive trades older than 90 days
CREATE TABLE paper_trades_archive AS
SELECT * FROM paper_trades
WHERE ts_close < NOW() - INTERVAL '90 days';

-- Delete archived trades
DELETE FROM paper_trades
WHERE ts_close < NOW() - INTERVAL '90 days';

-- Compress and export
COPY paper_trades_archive TO '/data/backups/archived_trades.csv' CSV HEADER;
```

Schedule monthly archival via cron:

```cron
0 2 1 * * psql -U trading -d vmassit -f /opt/apps/auto-trade-system/scripts/archive_old_trades.sql
```

---

## 8. 🔄 Log Rotation & Compression

### Host-Level Log Rotation

If logs are written outside containers (e.g., systemd services), configure `logrotate`:

Create `/etc/logrotate.d/auto-trade-system`:

```conf
/data/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    copytruncate
    dateext
    dateformat -%Y%m%d
    create 0644 admin admin
}
```

### How It Works

- **daily** - Rotate logs every day at midnight
- **rotate 14** - Keep 14 days of logs
- **compress** - Gzip old log files (`.log.1.gz`)
- **delaycompress** - Don't compress most recent rotated log
- **copytruncate** - Copy then truncate (no service restart needed)
- **dateext** - Use dates in filenames instead of numbers

### Verify Rotation

```bash
# Test rotation (dry run)
sudo logrotate -d /etc/logrotate.d/auto-trade-system

# Force rotation (for testing)
sudo logrotate -f /etc/logrotate.d/auto-trade-system

# Check rotated logs
ls -lh /data/logs/*.gz
```

---

## 9. 📊 Monitoring & Alerting

### Existing Stack

Your system already includes:
- ✅ **Prometheus** - Metrics collection
- ✅ **Grafana** - Visualization & dashboards
- ✅ **Loki** - Log aggregation
- ✅ **Promtail** - Log shipping to Loki

### Add Host-Level Monitoring

Create custom Prometheus exporters or use Node Exporter:

#### Install Node Exporter

```bash
docker run -d \
  --name=node-exporter \
  --net="host" \
  --pid="host" \
  -v "/:/host:ro,rslave" \
  prom/node-exporter:latest \
  --path.rootfs=/host
```

#### Add to `prometheus.yml`

```yaml
scrape_configs:
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
```

### Critical Alerts to Configure

In Grafana, set up alerts for:

| Metric | Threshold | Severity | Action |
|--------|-----------|----------|--------|
| Disk Usage | > 85% | Warning | Clean up logs/backups |
| Disk Usage | > 95% | Critical | Immediate intervention |
| Inode Usage | > 80% | Warning | Check for small file accumulation |
| Docker Volume Growth | > 10GB/day | Warning | Investigate log/config issues |
| Container Log Size | > 80MB | Info | Verify rotation working |
| PostgreSQL WAL Size | > 500MB | Warning | Tune WAL settings |
| PostgreSQL Table Size | > 5GB | Warning | Archive old data |
| Memory Usage | > 90% | Critical | Scale resources or optimize |
| CPU Usage | > 80% sustained | Warning | Check for runaway processes |

### Example Grafana Alert Rule

```yaml
# Disk Usage Alert
alert: HighDiskUsage
expr: (node_filesystem_size_bytes - node_filesystem_avail_bytes) / node_filesystem_size_bytes * 100 > 85
for: 5m
labels:
  severity: warning
annotations:
  summary: "Disk usage above 85% on {{ $labels.instance }}"
  description: "Disk partition {{ $labels.mountpoint }} is {{ $value }}% full"
```

---

## 10. 🛠️ Practical Deployment Steps

### Step 1: Prepare Host Directories

```bash
# Create all required directories
sudo mkdir -p /data/{postgres,redis,prometheus,grafana,loki,logs,app,backups,metrics}

# Set correct ownership (match Docker container UIDs)
sudo chown -R 1000:1000 /data/postgres /data/grafana /data/loki
sudo chown -R 999:999 /data/redis
sudo chown -R $(whoami):$(whoami) /data/logs /data/app /data/backups /data/metrics /data/prometheus

# Set permissions
sudo chmod -R 750 /data
```

### Step 2: Configure Production Environment

```bash
# Copy example config
cp .env.example .env.prod

# Edit with production values
nano .env.prod

# NEVER commit this file!
echo ".env.prod" >> .gitignore
```

### Step 3: Configure Docker Daemon

```bash
# Create/edit daemon config
sudo nano /etc/docker/daemon.json

# Paste configuration from Section 6

# Restart Docker
sudo systemctl restart docker

# Verify
docker info | grep -A 5 "Logging Driver"
```

### Step 4: Start Production Services

```bash
# Navigate to project directory
cd /opt/apps/auto-trade-system

# Start with production environment
docker-compose --env-file .env.prod up -d

# Verify all services healthy
docker-compose ps

# Check logs
docker-compose logs -f trading-bot
```

### Step 5: Validate Deployment

```bash
# Check health endpoints
curl http://localhost:8000/api/v1/health
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3000/api/health  # Grafana

# Verify disk usage
df -h /data
du -sh /data/*

# Check container logs size
docker inspect --format='{{.HostConfig.LogConfig}}' trading-bot-api
```

### Step 6: Schedule Maintenance Tasks

```bash
# Edit crontab
sudo crontab -e

# Add entries from Section 5 (Docker cleanup)
# Add PostgreSQL archival if needed
# Add backup schedule (see scripts/backup_database.sh)
```

### Step 7: Monitor for 48 Hours

Follow the **Phase 1 Deployment Requirements**:

- ✅ Check `logs/all_*.log` for watchdog activity
- ✅ Verify `logs/json_*.log` has structured entries
- ✅ Confirm NO false-positive alerts
- ✅ Measure system overhead (< 0.2% CPU)
- ✅ Validate all dashboard panels show data
- ✅ Test Telegram notifications

---

## 11. 📦 Backup Strategy

### Automated Database Backups

Use the existing backup script:

```bash
# Manual backup
./scripts/backup_database.sh --retention 90

# Schedule daily backups at 2:00 AM
0 2 * * * cd /opt/apps/auto-trade-system && ./scripts/backup_database.sh --retention 90 >> /data/logs/backup.log 2>&1
```

### Backup Contents

- PostgreSQL database dump (compressed)
- Redis RDB snapshot (if enabled)
- Application configuration snapshots
- Trading history archives

### Backup Verification

```bash
# List backups
ls -lh /data/backups/

# Test restore (on staging environment!)
gunzip -c /data/backups/vmassit_db_LATEST.db.gz | psql -U trading -d vmassit_test
```

### Off-Site Backup Recommendation

For production systems, sync backups to remote storage:

```bash
# Example: Sync to S3 (install aws-cli first)
aws s3 sync /data/backups/ s3://your-bucket/auto-trade-backups/ --delete

# Or use rsync to backup server
rsync -avz /data/backups/ backup-server:/backups/auto-trade/
```

---

## 12. 🎯 Summary & Best Practices

### What This Plan Achieves

✅ **Separated Storage** - Persistent data isolated from OS root  
✅ **Bind Mounts** - Easy migration and backup of databases/monitoring  
✅ **Log Management** - Docker and host-level rotation prevents disk exhaustion  
✅ **Production Variables** - `.env.prod` exposes all storage paths  
✅ **Automated Cleanup** - Cron jobs prevent Docker data accumulation  
✅ **PostgreSQL Tuning** - Optimized for trading workload stability  
✅ **Monitoring Ready** - Host-level metrics complement app metrics  
✅ **Backup Strategy** - Automated, verified, off-site capable  

### Critical Success Factors

1. **Start in Paper Mode** - Never go directly to live trading
2. **Validate for 48+ Hours** - Monitor stability before proceeding
3. **Test Backups Regularly** - Verify restore procedure monthly
4. **Monitor Disk Usage** - Set alerts at 85% and 95%
5. **Keep Logs Structured** - Use JSON format for easier analysis
6. **Document Changes** - Update this plan as system evolves
7. **Security First** - Rotate credentials, use strong passwords
8. **Performance Baseline** - Record metrics before going live

### Next Steps After Deployment

1. **Week 1**: Monitor closely, adjust PostgreSQL tuning if needed
2. **Week 2**: Review log sizes, optimize retention policies
3. **Month 1**: Perform first backup restore test
4. **Month 2**: Evaluate disk growth trends, plan capacity
5. **Quarterly**: Full security audit, credential rotation

---

## 📞 Support & Resources

### Internal Documentation

- [PRODUCTION_DEPLOYMENT_README.md](PRODUCTION_DEPLOYMENT_README.md) - Complete deployment guide
- [PRODUCTION_DEPLOYMENT_PLAN.md](PRODUCTION_DEPLOYMENT_PLAN.md) - Detailed checklist
- [EXECUTION_LAYER_OPTIMIZATION_PLAN.md](EXECUTION_LAYER_OPTIMIZATION_PLAN.md) - Freqtrade integration roadmap
- [QUICK_REFERENCE_PRODUCTION_MONITORING.md](QUICK_REFERENCE_PRODUCTION_MONITORING.md) - Monitoring quick reference

### External Resources

- Docker Best Practices: https://docs.docker.com/develop/dev-best-practices/
- PostgreSQL Performance: https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server
- Prometheus Monitoring: https://prometheus.io/docs/practices/naming/
- Grafana Alerting: https://grafana.com/docs/grafana/latest/alerting/

---

*Last Updated: May 17, 2026*  
*Maintained By: Auto Trade System Team*  
*Version: 1.0 - Production Ready*
