# Loki Monitoring - Quick Reference Guide

## Quick Start

### 1. Check Docker Status
```bash
sudo systemctl status docker
docker info | head -10
```

### 2. Start Monitoring Stack
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
docker compose up -d loki promtail grafana
```

### 3. Verify Services
```bash
# Check if running
docker ps | grep -E "(loki|promtail)"

# Test Loki health
curl http://localhost:3100/ready
# Expected: "ready"

# Test Grafana
curl http://localhost:3000/api/health
# Expected: {"commit":"...","database":"ok","version":"..."}
```

---

## Common Issues & Solutions

### Issue 1: Loki Not Accessible

**Symptom**: `curl http://localhost:3100/ready` returns nothing or error

**Solution**:
```bash
# Check container status
docker ps -a | grep loki

# View logs
docker logs trading-loki --tail 50

# Restart Loki
docker restart trading-loki

# If config error, fix and restart
docker compose down loki
docker compose up -d loki
```

### Issue 2: Docker Daemon Unresponsive

**Symptom**: Docker commands timeout or hang

**Solution**:
```bash
# Restart Docker daemon
sudo systemctl restart docker

# Verify
docker ps

# Then start monitoring
docker compose up -d loki promtail
```

### Issue 3: Promtail Not Sending Logs

**Symptom**: No logs appearing in Loki

**Solution**:
```bash
# Check Promtail logs
docker logs trading-promtail --tail 50

# Verify Docker socket is accessible
ls -la /var/run/docker.sock

# Restart Promtail
docker restart trading-promtail

# Check connectivity from Promtail to Loki
docker exec trading-promtail curl -s http://loki:3100/ready
```

### Issue 4: Configuration Errors

**Symptom**: Loki fails to start with YAML parsing errors

**Common Fixes**:
- Ensure `shared_store` is under `storage_config.boltdb_shipper`
- Check indentation in YAML files
- Validate config syntax before restarting

---

## Useful Commands

### Service Management
```bash
# Start all monitoring services
docker compose up -d loki promtail grafana prometheus

# Stop all monitoring services
docker compose down loki promtail grafana prometheus

# Restart specific service
docker restart trading-loki

# View real-time logs
docker logs -f trading-loki
docker logs -f trading-promtail
```

### Health Checks
```bash
# Loki readiness
curl -s http://localhost:3100/ready

# Loki metrics
curl -s http://localhost:3100/metrics | head -20

# Promtail metrics
curl -s http://localhost:9080/metrics | head -20

# Grafana health
curl -s http://localhost:3000/api/health
```

### Log Queries (via API)
```bash
# Get recent logs from all containers
curl -s "http://localhost:3100/loki/api/v1/query_range?query={job=\"docker-containers\"}&limit=10&direction=backward"

# Get logs from specific container
curl -s "http://localhost:3100/loki/api/v1/query_range?query={container=\"trading-postgres\"}&limit=10"

# Search for specific text
curl -s "http://localhost:3100/loki/api/v1/query_range?query={container=\"trading-postgres\"}~=\"error\"&limit=10"
```

---

## Configuration Files

### Loki Config
**Location**: [`monitoring/loki-config.yml`](file:///home/admin/.openclaw/workspace/auto-trade-system/monitoring/loki-config.yml)

**Key Settings**:
- Port: 3100
- Storage: Filesystem (development)
- Retention: 7 days (168h)
- Auth: Disabled

### Promtail Config
**Location**: [`monitoring/promtail-config.yml`](file:///home/admin/.openclaw/workspace/auto-trade-system/monitoring/promtail-config.yml)

**Key Settings**:
- Port: 9080
- Source: Docker container logs
- Target: `http://loki:3100/loki/api/v1/push`
- Discovery: Docker socket

### Docker Compose
**Location**: [`docker-compose.yml`](file:///home/admin/.openclaw/workspace/auto-trade-system/docker-compose.yml)

**Services**:
- Lines 77-88: Loki configuration
- Lines 90-102: Promtail configuration
- Lines 59-75: Grafana configuration
- Lines 41-57: Prometheus configuration

---

## Grafana Dashboard Access

### Login
- **URL**: http://localhost:3000
- **Username**: admin
- **Password**: admin123

### Add Loki Datasource
1. Go to: ⚙️ Configuration → Data Sources
2. Click: "Add data source"
3. Select: Loki
4. URL: `http://loki:3100` (if accessing from Grafana container)
   - OR: `http://localhost:3100` (if accessing from host)
5. Click: "Save & Test"

### Query Examples (LogQL)
```logql
# All logs from trading system
{container=~"trading-.*"}

# Error logs only
{container="trading-postgres"} |= "error"

# Logs containing specific text
{job="docker-containers"} |= "trade executed"

# Logs by time range
{container="trading-redis"} |= "connection" | timestamp > now() - 1h

# Count logs by level
sum by (level) (count_over_time({container="trading-postgres"} |= "error" [5m]))
```

---

## Integration with Trading System

### Application Logging

Your Python application automatically logs to stdout/stderr when running in Docker. Promtail will collect these logs.

**Example**:
```python
import logging
from app.logging_config import get_logger

logger = get_logger(__name__)

# These logs will be collected by Promtail
logger.info("Trade executed: XAU/USDT buy 0.01 @ $2000")
logger.error("Bybit API error: retCode 10003")
logger.warning("Rate limit approaching")
```

### Key Events to Monitor

Based on your trading system architecture:

1. **Order Events**
   - Order placement success/failure
   - Order cancellation
   - Order status changes

2. **Position Events**
   - Position opened/closed
   - PnL updates
   - Liquidation warnings

3. **API Events**
   - Bybit API calls (success/error)
   - Rate limit warnings
   - Authentication failures

4. **System Events**
   - Service startup/shutdown
   - Health check failures
   - Database connection issues

---

## Troubleshooting Flowchart

```
Loki not accessible?
    │
    ├─ Docker not running?
    │   └─ sudo systemctl restart docker
    │
    ├─ Container not started?
    │   └─ docker compose up -d loki
    │
    ├─ Configuration error?
    │   ├─ Check logs: docker logs trading-loki
    │   └─ Fix config and restart
    │
    └─ Port conflict?
        ├─ Check: netstat -tlnp | grep 3100
        └─ Kill conflicting process or change port
```

---

## Performance Tuning

### For Development (Current Setup)
- ✅ Filesystem storage (simple, no dependencies)
- ✅ 7-day retention
- ✅ Single replica
- ✅ In-memory ring

### For Production (Future)
Consider:
- Object storage (S3, GCS) for scalability
- Increased retention based on compliance needs
- Multiple replicas for high availability
- Distributed ring (Consul, etcd)

---

## Backup & Restore

### Backup Loki Data
```bash
# Stop Loki
docker stop trading-loki

# Backup volume
docker run --rm -v trading-loki-data:/source -v $(pwd):/backup \
  alpine tar czf /backup/loki-backup.tar.gz -C /source .

# Restart Loki
docker start trading-loki
```

### Restore Loki Data
```bash
# Stop Loki
docker stop trading-loki

# Restore volume
docker run --rm -v trading-loki-data:/target -v $(pwd):/backup \
  alpine tar xzf /backup/loki-backup.tar.gz -C /target

# Restart Loki
docker start trading-loki
```

---

## Monitoring the Monitoring

Check resource usage:
```bash
# Loki resource usage
docker stats trading-loki --no-stream

# Promtail resource usage
docker stats trading-promtail --no-stream

# Disk usage
docker system df -v | grep loki
```

Set up alerts for:
- Loki down for > 5 minutes
- Promtail not sending logs
- Disk usage > 80%
- Log ingestion rate drops

---

## Quick Diagnostics Script

Save as `check_loki.sh`:

```bash
#!/bin/bash
echo "=== Loki Monitoring Diagnostics ==="
echo ""

echo "1. Docker Status:"
docker ps | grep -E "(loki|promtail)" || echo "   ❌ Services not running"
echo ""

echo "2. Loki Health:"
curl -s http://localhost:3100/ready && echo " ✅ Ready" || echo " ❌ Not ready"
echo ""

echo "3. Recent Loki Logs:"
docker logs trading-loki --tail 5 2>&1 | tail -5
echo ""

echo "4. Promtail Status:"
docker logs trading-promtail --tail 3 2>&1 | tail -3
echo ""

echo "5. Port Availability:"
netstat -tlnp 2>/dev/null | grep -E "(3100|9080|3000)" || echo "   Ports not listening"
echo ""

echo "=== End Diagnostics ==="
```

Run with:
```bash
chmod +x check_loki.sh
./check_loki.sh
```

---

## Additional Resources

- **Official Docs**: https://grafana.com/docs/loki/latest/
- **LogQL Reference**: https://grafana.com/docs/loki/latest/logql/
- **Promtail Docs**: https://grafana.com/docs/loki/latest/clients/promtail/
- **Grafana Dashboards**: https://grafana.com/grafana/dashboards/?search=loki

---

**Last Updated**: May 13, 2026  
**Version**: 1.0
