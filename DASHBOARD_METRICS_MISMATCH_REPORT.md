# Dashboard Metrics Mismatch Report

## Overview

This report documents the discrepancies identified between Grafana dashboard expectations and actual metrics exposure in the Auto Trade System monitoring stack.

**Date**: May 17, 2026  
**Status**: ✅ RESOLVED  
**Resolution**: Implemented via DASHBOARD_METRICS_INTEGRATION_ROADMAP.md

---

## Executive Summary

Analysis of the Sprint 5 Production Monitoring Dashboard revealed that **6 out of 13 metrics** required by Grafana panels were not being exposed by the application's Prometheus endpoint. This caused "No data" errors in critical infrastructure health and AI/LLM monitoring panels.

### Impact Assessment
- **Severity**: HIGH - Critical infrastructure visibility gaps
- **Affected Panels**: 6 out of 13 (46%)
- **User Impact**: Inability to monitor Redis, database, WebSocket, and AI system health
- **Risk**: Undetected infrastructure failures could lead to trading disruptions

---

## Metrics Gap Analysis

### Missing Metrics Inventory

| # | Metric Name | Type | Expected By | Status Before Fix | Root Cause |
|---|-------------|------|-------------|-------------------|------------|
| 1 | `redis_connection_status` | Gauge | Redis Status Panel | ❌ Not Exposed | Defined but not instantiated |
| 2 | `database_connection_pool_size` | Gauge | Database Pool Panel | ❌ Not Exposed | Defined but not instantiated |
| 3 | `websocket_uptime_seconds` | Gauge | WebSocket Uptime Panel | ❌ Not Exposed | No tracking implementation |
| 4 | `websocket_reconnect_total` | Counter | WebSocket Reconnects Panel | ❌ Not Exposed | No tracking implementation |
| 5 | `llm_token_usage_total` | Counter | Token Usage Panel | ❌ Not Exposed | No API response parsing |
| 6 | `ai_confidence_scores` | Histogram | Confidence Distribution Panel | ❌ Not Exposed | No observation recording |

### Working Metrics (No Action Required)

| # | Metric Name | Type | Panel | Status |
|---|-------------|------|-------|--------|
| 1 | `pnl_cumulative_usd` | Gauge | P&L Over Time | ✅ Working |
| 2 | `win_rate_percent` | Gauge | Win Rate | ✅ Working |
| 3 | `drawdown_current_percent` | Gauge | Current Drawdown | ✅ Working |
| 4 | `risk_exposure_usd` | Gauge | Current Exposure | ✅ Working |
| 5 | `positions_open` | Gauge | Daily Loss Limit | ✅ Working |
| 6 | `bot_trading_enabled` | Gauge | Circuit Breaker State | ✅ Working |
| 7 | `execution_latency_seconds` | Histogram | Latency Distribution | ✅ Working |
| 8 | `slippage_avg_percent` | Gauge | Slippage Analysis | ✅ Working |

---

## Root Cause Analysis

### Issue 1: Metrics Defined But Not Registered

**Location**: `app/monitoring/metrics.py`

The metrics module contained definitions for all 6 missing metrics:

```python
# app/monitoring/metrics.py (lines 139-159)
WEBSOCKET_RECONNECT_COUNT = Counter(
    'websocket_reconnect_total',
    'Total WebSocket reconnection attempts',
    ['exchange']
)

WEBSOCKET_UPTIME_SECONDS = Gauge(
    'websocket_uptime_seconds',
    'WebSocket connection uptime in seconds',
    ['exchange']
)

LLM_TOKEN_USAGE = Counter(
    'llm_token_usage_total',
    'Total LLM token usage',
    ['provider', 'model']
)

AI_CONFIDENCE_SCORES = Histogram(
    'ai_confidence_scores',
    'AI confidence score distribution',
    ['agent_type'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

DATABASE_CONNECTION_POOL_SIZE = Gauge(
    'database_connection_pool_size',
    'Database connection pool size',
    ['pool_type']
)

REDIS_CONNECTION_STATUS = Gauge(
    'redis_connection_status',
    'Redis connection status (1=connected, 0=disconnected)'
)
```

**Problem**: These metrics were defined in a separate registry (`prometheus_client.REGISTRY`) but never imported or registered with the `CUSTOM_REGISTRY` used by the `/metrics/prometheus` endpoint in `app/main.py`.

**Impact**: Metrics existed in code but were invisible to Prometheus scraper.

### Issue 2: No Background Metrics Updater

**Problem**: Infrastructure metrics like Redis status and database pool size require periodic polling to stay current. No background task existed to:
- Ping Redis and update connection status
- Query SQLAlchemy pool for active/idle connection counts
- Handle errors gracefully when services are unavailable

**Impact**: Even if metrics were registered, they would show stale or zero values.

### Issue 3: Event-Driven Metrics Not Tracked

**Problem**: WebSocket and AI metrics should be updated when events occur (reconnections, predictions), but no integration existed:
- WebSocket manager didn't record reconnects or uptime
- AI filter didn't observe confidence scores
- OpenRouter client didn't extract token usage from API responses

**Impact**: Real-time events were not captured in monitoring system.

---

## Diagnostic Process

### Step 1: Dashboard Panel Audit

Examined each Grafana panel's PromQL query:

```bash
# Extract all queries from dashboard JSON
python3 -c "
import json
with open('monitoring/grafana/dashboards/sprint5-production-dashboard.json') as f:
    dashboard = json.load(f)
    
for panel in dashboard['panels']:
    if 'targets' in panel:
        for target in panel['targets']:
            print(f\"Panel: {panel.get('title', 'Unknown')}\")
            print(f\"Query: {target.get('expr', 'N/A')}\")
            print()
"
```

### Step 2: Metrics Endpoint Verification

Checked which metrics are actually exposed:

```bash
# Get all exposed metrics
curl -s http://localhost:8000/metrics/prometheus | grep "^#" | grep -v HELP | awk '{print $2}' | sort -u > exposed_metrics.txt

# Compare with dashboard requirements
grep -oE '[a-z_]+' dashboard_queries.txt | sort -u > required_metrics.txt
comm -23 required_metrics.txt exposed_metrics.txt
```

**Result**: 6 metrics found in required list but not in exposed list.

### Step 3: Code Search for Metric Definitions

```bash
# Search for metric definitions
grep -r "websocket_reconnect_total\|redis_connection_status\|database_connection_pool" app/ --include="*.py"
```

**Finding**: All 6 metrics were defined in `app/monitoring/metrics.py` but never used.

### Step 4: Prometheus Target Health Check

```bash
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep -A 10 "auto-trade-system"
```

**Result**: Prometheus scraping successfully (`health: "up"`), confirming issue was metrics exposure, not connectivity.

---

## Resolution Strategy

### Phase 1: Register Metrics (Immediate)
- Define all 6 metrics in `app/main.py` using `CUSTOM_REGISTRY`
- Ensure proper labels and bucket configurations
- Add comprehensive docstrings

### Phase 2: Background Updater (Short-term)
- Create async background task in `app/main.py`
- Update Redis status every 10 seconds
- Update database pool stats every 10 seconds
- Implement graceful error handling

### Phase 3: Event Integration (Medium-term)
- Modify WebSocket manager to track reconnections and uptime
- Modify AI filter to record confidence scores
- Modify OpenRouter client to extract token usage
- Add fallback logic for import failures

---

## Verification Methodology

### Pre-Fix Baseline
```bash
# Count missing metrics
curl -s http://localhost:9090/api/v1/query?query=redis_connection_status | \
  python3 -c "import sys, json; print(len(json.load(sys.stdin)['data']['result']))"
# Output: 0 (no data)
```

### Post-Fix Validation
```bash
# Verify all 6 metrics now return data
for metric in redis_connection_status database_connection_pool_size websocket_uptime_seconds websocket_reconnect_total llm_token_usage_total ai_confidence_scores; do
  count=$(curl -s "http://localhost:9090/api/v1/query?query=$metric" | \
    python3 -c "import sys, json; print(len(json.load(sys.stdin)['data']['result']))")
  echo "$metric: $count results"
done

# Expected output:
# redis_connection_status: 1 results
# database_connection_pool_size: 2 results (active + idle)
# websocket_uptime_seconds: 1 results
# websocket_reconnect_total: 1 results
# llm_token_usage_total: 1+ results (per model)
# ai_confidence_scores: 1+ results (per agent)
```

### Grafana Dashboard Test
1. Open Grafana at http://localhost:3000
2. Navigate to "Sprint 5 - Production Monitoring Dashboard"
3. Verify no "No data" warnings in any panels
4. Check that infrastructure panels show live data
5. Confirm refresh rate is 10 seconds

---

## Lessons Learned

### What Went Wrong
1. **Metric Definition Fragmentation**: Metrics were scattered across multiple files without clear ownership
2. **Registry Confusion**: Multiple Prometheus registries created confusion about which metrics were exposed
3. **Missing Integration Tests**: No tests verified that dashboard queries matched exposed metrics
4. **Assumption Gap**: Assumed defining metrics was sufficient; didn't verify end-to-end flow

### Improvements Implemented
1. **Centralized Metrics**: All critical metrics now defined in `app/main.py` alongside endpoint
2. **Background Task Pattern**: Established pattern for periodic metric updates
3. **Event-Driven Tracking**: Integrated metrics into existing event flows
4. **Documentation**: Created comprehensive roadmap for future metric additions

### Recommendations
1. **Add Metrics Integration Test**: Create test that verifies all dashboard queries return data
2. **Implement Alert Rules**: Set up Prometheus alerts for missing metrics
3. **Create Metrics Catalog**: Maintain living document of all available metrics
4. **Automate Dashboard Validation**: Script to check dashboard vs exposed metrics on each deploy

---

## Related Documents

- [DASHBOARD_METRICS_INTEGRATION_ROADMAP.md](./DASHBOARD_METRICS_INTEGRATION_ROADMAP.md) - Implementation plan
- [DASHBOARD_NO_DATA_FIX.md](./DASHBOARD_NO_DATA_FIX.md) - Original diagnosis
- [DASHBOARD_PROMQL_QUERIES.md](./DASHBOARD_PROMQL_QUERIES.md) - Query reference
- [DASHBOARD_NO_DATA_EXECUTIVE_SUMMARY.md](./DASHBOARD_NO_DATA_EXECUTIVE_SUMMARY.md) - High-level overview

---

## Conclusion

The metrics mismatch has been fully resolved through a systematic 3-phase approach. All 6 missing metrics are now properly exposed, tracked, and visible in the Grafana dashboard. The implementation includes robust error handling, follows Prometheus best practices, and establishes patterns for future metric additions.

**Status**: ✅ COMPLETE  
**Next Review**: Monitor for 48 hours, then conduct post-implementation review
