# Telegram Reporting & Monitoring Stack - Quick Reference

## Quick Start

### 1. Start Services
```bash
docker-compose up -d
```

### 2. Access Interfaces
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **Application Metrics**: http://localhost:8000/metrics/prometheus

### 3. Test Implementation
```bash
# Test Telegram notifications
python scripts/test_telegram_reporting.py

# Validate metrics exposure
python scripts/validate_metrics_instrumentation.py
```

---

## Telegram Events (5 New Handlers)

| Event Type | Handler | Purpose |
|------------|---------|---------|
| ORDER_STATE_CHANGED | `_on_order_state_changed()` | Critical order transitions (REJECTED, CANCELED, EXPIRED) |
| RISK_VIOLATION_DETECTED | `_on_risk_violation()` | Risk threshold breaches |
| RECOVERY_ACTION_TAKEN | `_on_recovery_action()` | Auto-recovery from issues |
| RECONCILIATION_ACTION | `_on_reconciliation_action()` | Position mismatches |
| SYNC_REPAIRED | `_on_sync_repaired()` | Sync repair confirmations |

---

## Prometheus Metrics (20 Total)

### Trading Performance (6)
- `trade_execution_latency_ms` - Execution time histogram
- `trade_slippage_percentage` - Slippage histogram
- `fill_rate_percentage` - Fill rate gauge
- `pnl_per_trade_usd` - P&L distribution
- `win_rate_percentage` - Win rate by strategy
- `total_trades_count` - Trade counter

### Reliability (4)
- `websocket_reconnect_total` - Reconnection counter
- `api_failure_total` - API failure counter
- `websocket_uptime_seconds` - Uptime gauge
- `order_rejection_total` - Rejection counter

### Data Integrity (3)
- `desync_events_total` - Desync counter
- `reconciliation_actions_total` - Reconciliation counter
- `position_sync_latency_ms` - Sync latency histogram

### Risk Management (3)
- `risk_violations_total` - Violation counter
- `daily_drawdown_percentage` - Drawdown gauge
- `circuit_breaker_state` - Circuit breaker gauge

### Existing (4)
- `http_requests_total` - HTTP request counter
- `http_request_duration_seconds` - HTTP latency histogram
- `websocket_connected` - WebSocket status
- `event_bus_queue_size` - Queue size histogram

---

## Grafana Dashboard Panels (13 Total)

### Performance
1. Request Rate
2. Error Rate
3. API Response Time
4. **Trade Execution Latency** (NEW)
5. **Strategy Win Rate** (NEW)

### Reliability
6. WebSocket Connection Status
7. WebSocket Message Latency
8. **WebSocket Reconnections per Hour** (NEW)

### Data Integrity
9. Event Bus Queue Size
10. **Synchronization Mismatches per Hour** (NEW)

### Risk Management
11. **Risk Limit Violations per Hour** (NEW)
12. **Circuit Breaker State** (NEW)

### Logs
13. **Application Logs (Errors)** (NEW - Loki)

---

## Alert Rules (12 Total)

### Critical Alerts
- **HighAPIFailureRate** - API failures > 0.1/sec
- **CircuitBreakerOpen** - Circuit breaker tripped
- **HighDailyDrawdown** - Drawdown > 5%
- **WebSocketDisconnected** - WS disconnected > 1 min
- **DatabaseConnectionPoolExhausted** - No DB connections
- **RedisDown** - Redis not responding

### Warning Alerts
- **HighExecutionLatency** - Latency > 1000ms (p95)
- **FrequentWebSocketReconnects** - > 5 reconnects/hour
- **DesyncEventsDetected** - Any desyncs in 1 hour
- **OrderRejectionSpike** - > 0.05 rejections/min
- **HighErrorRate** - HTTP 5xx errors > 0.1/sec
- **HighLatency** - HTTP latency > 1s (p95)

---

## File Locations

### Application Code
- `app/notifications/telegram_agent.py` - Telegram handlers
- `app/monitoring/metrics.py` - Metric definitions

### Infrastructure
- `docker-compose.yml` - Service definitions
- `monitoring/loki-config.yml` - Loki config
- `monitoring/promtail-config.yml` - Promtail config

### Monitoring
- `monitoring/grafana/dashboards/trading-system.json` - Dashboard
- `monitoring/prometheus-alerts.yml` - Alert rules
- `monitoring/grafana/datasources/loki-datasource.yml` - Loki datasource

### Testing
- `scripts/test_telegram_reporting.py` - Telegram tests
- `scripts/validate_metrics_instrumentation.py` - Metrics validation

---

## Common Queries

### Check if Services Are Running
```bash
docker-compose ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f trading-loki
docker-compose logs -f trading-promtail
```

### Query Loki Directly
```bash
# Get logs from trading containers
curl -G "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={container=~"trading-.*"}'

# Get error logs
curl -G "http://localhost:3100/loki/api/v1/query" \
  --data-urlencode 'query={container=~"trading-.*"} |= "ERROR"'
```

### Check Prometheus Targets
```bash
curl http://localhost:9090/api/v1/targets | jq
```

### Verify Metrics Endpoint
```bash
curl http://localhost:8000/metrics/prometheus | head -50
```

---

## Troubleshooting

### Problem: Telegram Notifications Not Received
**Solution**:
1. Check `.env` has `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
2. Run test script: `python scripts/test_telegram_reporting.py`
3. Check app logs for Telegram API errors

### Problem: Loki Not Collecting Logs
**Solution**:
```bash
# Check Promtail can reach Docker socket
docker exec trading-promtail ls -la /var/run/docker.sock

# Check Promtail logs
docker logs trading-promtail | tail -50

# Verify Loki is ready
curl http://localhost:3100/ready
```

### Problem: Metrics Not Showing in Grafana
**Solution**:
1. Verify app is running: `curl http://localhost:8000/metrics/prometheus`
2. Check Prometheus targets: http://localhost:9090/targets
3. Wait for first metric observation (metrics appear after first use)
4. Check Prometheus query: `up{job="auto-trade-system"}`

### Problem: Alerts Not Firing
**Solution**:
1. Check alerts loaded: http://localhost:9090/alerts
2. Verify metric has data in Prometheus UI
3. Adjust thresholds if needed
4. Check alert evaluation: `ALERTS` query in Prometheus

---

## Key Ports

| Service | Port | URL |
|---------|------|-----|
| Application | 8000 | http://localhost:8000 |
| Grafana | 3000 | http://localhost:3000 |
| Prometheus | 9090 | http://localhost:9090 |
| Loki | 3100 | http://localhost:3100 |
| PostgreSQL | 5432 | - |
| Redis | 6379 | - |

---

## Next Steps

To complete metric instrumentation, add recording calls in:

1. **Exchange Adapter** - Record execution latency and slippage
2. **WebSocket Manager** - Track reconnections and uptime
3. **Sync Agent** - Count desyncs and reconciliations
4. **Risk Engine** - Track violations and circuit breaker state

See `TELEGRAM_MONITORING_IMPLEMENTATION_COMPLETE.md` for detailed instrumentation examples.

---

## Documentation

- **Full Implementation Guide**: `TELEGRAM_MONITORING_IMPLEMENTATION_COMPLETE.md`
- **Plan Document**: See plan file in `.lingma/plans/`
- **Existing Docs**: Refer to project README files for component-specific details
