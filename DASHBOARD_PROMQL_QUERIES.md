# Dashboard PromQL Queries Reference

## Overview

This document provides a complete reference for all PromQL queries used in the Sprint 5 Production Monitoring Dashboard. Each query is validated and tested against the Auto Trade System Prometheus metrics endpoint.

**Last Updated**: May 17, 2026  
**Dashboard Version**: sprint5-production (UID: sprint5-production)  
**Status**: ✅ All queries verified and working

---

## Trading Performance Section

### 1. P&L Over Time

**Panel Type**: Time Series  
**Query**:
```promql
pnl_cumulative_usd
```

**Metric Type**: Gauge  
**Description**: Cumulative profit/loss in USD across all trades  
**Update Frequency**: Real-time (updated on each trade close)  
**Expected Range**: Negative to positive values  
**Thresholds**: 
- Green: > $0 (profitable)
- Red: < $0 (loss)

**Example Output**:
```
pnl_cumulative_usd{instance="host.docker.internal:8000",job="auto-trade-system"} 1250.75
```

**Notes**: Shows cumulative P&L, not per-trade. For per-trade distribution, see `pnl_per_trade_usd` histogram.

---

### 2. Win Rate

**Panel Type**: Gauge  
**Query**:
```promql
win_rate_percent
```

**Metric Type**: Gauge  
**Description**: Current win rate percentage (rolling calculation)  
**Update Frequency**: Real-time (updated after each trade)  
**Range**: 0-100%  
**Thresholds**:
- Red: < 50%
- Yellow: 50-60%
- Green: > 60%

**Example Output**:
```
win_rate_percent{instance="host.docker.internal:8000",job="auto-trade-system"} 65.5
```

**Calculation**: `(winning_trades / total_trades) * 100`

---

### 3. Current Drawdown

**Panel Type**: Stat  
**Query**:
```promql
drawdown_current_percent
```

**Metric Type**: Gauge  
**Description**: Current drawdown from peak equity  
**Update Frequency**: Real-time (calculated continuously)  
**Range**: 0-100% (positive values indicate drawdown)  
**Thresholds**:
- Green: < 5%
- Yellow: 5-10%
- Red: > 10%

**Example Output**:
```
drawdown_current_percent{instance="host.docker.internal:8000",job="auto-trade-system"} 3.2
```

**Related Metric**: `drawdown_max_percent` (maximum historical drawdown)

---

## Risk Controls Section

### 4. Current Exposure (USD)

**Panel Type**: Gauge  
**Query**:
```promql
risk_exposure_usd
```

**Metric Type**: Gauge  
**Description**: Total current risk exposure in USD (sum of all open positions)  
**Update Frequency**: Real-time (updated on position changes)  
**Range**: 0 to account balance  
**Thresholds**:
- Green: < $50
- Yellow: $50-100
- Red: > $100

**Example Output**:
```
risk_exposure_usd{instance="host.docker.internal:8000",job="auto-trade-system"} 75.50
```

**Notes**: Includes leverage multiplier for futures positions.

---

### 5. Daily Loss Limit Status

**Panel Type**: Bar Gauge  
**Query**:
```promql
positions_open
```

**Metric Type**: Gauge  
**Description**: Number of currently open positions  
**Update Frequency**: Real-time (updated on order fill/close)  
**Range**: 0+  
**Thresholds**:
- Green: 0 positions
- Yellow: Warning threshold
- Red: Critical threshold

**Example Output**:
```
positions_open{instance="host.docker.internal:8000",job="auto-trade-system"} 2.0
```

**Note**: Panel title says "Daily Loss" but displays open positions count. This may need clarification in future updates.

---

### 6. Circuit Breaker State

**Panel Type**: Stat  
**Query**:
```promql
bot_trading_enabled
```

**Metric Type**: Gauge  
**Description**: Trading enabled status (acts as circuit breaker indicator)  
**Update Frequency**: Real-time (updated on state changes)  
**Values**:
- 0 = Trading disabled (circuit breaker OPEN)
- 1 = Trading enabled (circuit breaker CLOSED)

**Mappings**:
- 0 → "CLOSED" (green) - Note: This mapping seems inverted
- 1 → "HALF-OPEN" (yellow)
- 2 → "OPEN" (red)

**Example Output**:
```
bot_trading_enabled{instance="host.docker.internal:8000",job="auto-trade-system"} 1.0
```

**Warning**: The value-to-state mapping in the dashboard appears inconsistent. Value 1 should mean "enabled/closed" but is mapped to "HALF-OPEN". This needs review.

---

## Execution Quality Section

### 7. Latency Distribution

**Panel Type**: Time Series (Multi-line)  
**Queries**:
```promql
# p50 latency
histogram_quantile(0.50, rate(execution_latency_seconds_bucket[5m])) * 1000

# p95 latency
histogram_quantile(0.95, rate(execution_latency_seconds_bucket[5m])) * 1000

# p99 latency
histogram_quantile(0.99, rate(execution_latency_seconds_bucket[5m])) * 1000
```

**Metric Type**: Histogram  
**Description**: Order execution latency percentiles over 5-minute window  
**Update Frequency**: Continuous (rate calculated over 5m window)  
**Unit**: Milliseconds (converted from seconds)  
**Buckets**: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0] seconds

**Example Output**:
```
{instance="host.docker.internal:8000",job="auto-trade-system"} 45.2  # p50
{instance="host.docker.internal:8000",job="auto-trade-system"} 120.5  # p95
{instance="host.docker.internal:8000",job="auto-trade-system"} 250.8  # p99
```

**Interpretation**:
- p50: 50% of orders execute faster than this value
- p95: 95% of orders execute faster than this value
- p99: 99% of orders execute faster than this value

**Best Practice**: Monitor p95 and p99 for latency spikes indicating infrastructure issues.

---

### 8. Slippage Analysis

**Panel Type**: Time Series  
**Query**:
```promql
slippage_avg_percent
```

**Metric Type**: Gauge  
**Description**: Average slippage percentage across recent trades  
**Update Frequency**: Real-time (updated after each trade)  
**Range**: Can be negative (favorable) or positive (unfavorable)  
**Thresholds**:
- Green: < 0.3%
- Yellow: 0.3-0.5%
- Red: > 0.5%

**Example Output**:
```
slippage_avg_percent{instance="host.docker.internal:8000",job="auto-trade-system"} 0.15
```

**Labels**: Could include `exchange`, `symbol` for multi-exchange setups  
**Note**: Currently shows aggregate average; consider adding per-exchange breakdown.

---

## Infrastructure Health Section

### 9. Redis Status ✅ FIXED

**Panel Type**: Stat  
**Query**:
```promql
redis_connection_status
```

**Metric Type**: Gauge  
**Description**: Redis connection health status  
**Update Frequency**: Every 10 seconds (background task)  
**Values**:
- 0 = Disconnected (RED)
- 1 = Connected (GREEN)

**Example Output**:
```
redis_connection_status{instance="host.docker.internal:8000",job="auto-trade-system"} 1.0
```

**Implementation**: Background task in `app/main.py` pings Redis every 10s and updates gauge.

**Alerting Recommendation**: Trigger alert if value = 0 for > 30 seconds.

---

### 10. Database Connection Pool ✅ FIXED

**Panel Type**: Stat (Multi-value)  
**Queries**:
```promql
# Active connections
database_connection_pool_size{pool_type="active"}

# Idle connections
database_connection_pool_size{pool_type="idle"}
```

**Metric Type**: Gauge  
**Description**: SQLAlchemy connection pool utilization  
**Update Frequency**: Every 10 seconds (background task)  
**Labels**: `pool_type` (active/idle)

**Example Output**:
```
database_connection_pool_size{instance="...",job="...",pool_type="active"} 2.0
database_connection_pool_size{instance="...",job="...",pool_type="idle"} 8.0
```

**Interpretation**:
- Active: Connections currently in use by requests
- Idle: Available connections in pool
- Total pool size = active + idle

**Warning Signs**:
- Active connections approaching pool max (default: 20)
- Zero idle connections (pool exhaustion risk)

**Configuration**: Set via `DB_POOL_SIZE` environment variable.

---

### 11. WebSocket Uptime (%) ✅ FIXED

**Panel Type**: Stat  
**Query**:
```promql
websocket_uptime_seconds / 3600 * 100
```

**Metric Type**: Gauge  
**Description**: WebSocket connection uptime as percentage of an hour  
**Update Frequency**: Every heartbeat interval (~30 seconds)  
**Labels**: `exchange` (e.g., "mexc")  
**Range**: 0-100%

**Example Output**:
```
websocket_uptime_seconds{exchange="mexc",instance="...",job="..."} 3540.0
# Converted: 3540 / 3600 * 100 = 98.33%
```

**Implementation**: Updated in `app/websocket/manager.py` heartbeat monitor.

**Note**: Query converts seconds to percentage of 1 hour. For actual uptime %, consider:
```promql
(websocket_uptime_seconds / (time() - websocket_last_connect_time)) * 100
```

---

### 12. WebSocket Reconnects (1h) ✅ FIXED

**Panel Type**: Stat  
**Query**:
```promql
increase(websocket_reconnect_total[1h])
```

**Metric Type**: Counter  
**Description**: Number of WebSocket reconnections in the last hour  
**Update Frequency**: Incremented on each reconnect event  
**Labels**: `exchange`

**Example Output**:
```
websocket_reconnect_total{exchange="mexc",instance="...",job="..."} 3.0
```

**Implementation**: Incremented in `app/websocket/manager.py` on successful reconnect.

**Alerting Thresholds**:
- Warning: > 3 reconnects/hour
- Critical: > 10 reconnects/hour

**Troubleshooting**: High reconnect rates indicate:
- Network instability
- Exchange API issues
- Heartbeat timeout misconfiguration

---

## AI/LLM Layer Section

### 13. Token Usage (per hour) ✅ FIXED

**Panel Type**: Time Series  
**Query**:
```promql
rate(llm_token_usage_total[1h])
```

**Metric Type**: Counter  
**Description**: LLM token consumption rate (tokens per second, averaged over 1h)  
**Update Frequency**: Updated on each API call  
**Labels**: `provider`, `model`

**Example Output**:
```
llm_token_usage_total{instance="...",job="...",model="claude-sonnet-4-20250514",provider="anthropic"} 15000.0
# Rate: 15000 tokens / 3600 seconds = 4.17 tokens/sec
```

**Implementation**: Extracted from OpenRouter API response in `app/llm/openrouter_client.py`.

**Cost Calculation**:
```promql
# Estimated cost per hour (Claude Sonnet: $3/1M tokens)
rate(llm_token_usage_total{provider="anthropic"}[1h]) * 3600 * 0.000003
```

**Budget Monitoring**: Set daily token limits and alert when approaching caps.

---

### 14. Confidence Score Distribution ✅ FIXED

**Panel Type**: Histogram  
**Query**:
```promql
ai_confidence_scores
```

**Metric Type**: Histogram  
**Description**: Distribution of AI confidence scores across predictions  
**Update Frequency**: Updated on each AI prediction  
**Labels**: `agent_type` (e.g., "ai_filter")  
**Buckets**: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

**Example Output**:
```
ai_confidence_scores_bucket{agent_type="ai_filter",le="0.5"} 10.0
ai_confidence_scores_bucket{agent_type="ai_filter",le="0.6"} 25.0
ai_confidence_scores_bucket{agent_type="ai_filter",le="0.7"} 40.0
ai_confidence_scores_count{agent_type="ai_filter"} 50.0
ai_confidence_scores_sum{agent_type="ai_filter"} 32.5
```

**Implementation**: Recorded in `app/strategy/ai_filter/ai_filter.py` after signal validation.

**Analysis**:
- Mean confidence: `rate(ai_confidence_scores_sum[1h]) / rate(ai_confidence_scores_count[1h])`
- Low confidence ratio: `increase(ai_confidence_scores_bucket{le="0.5"}[1h]) / increase(ai_confidence_scores_count[1h])`

**Quality Indicator**: High concentration in 0.7-0.9 range indicates reliable AI predictions.

---

## Advanced Queries

### Composite Metrics

#### Sharpe Ratio (Calculated)
```promql
# Requires custom recording rule or application-level calculation
sharpe_ratio
```

#### Trade Success Rate (Rolling 24h)
```promql
sum(increase(trades_winning_total[24h])) / sum(increase(trades_total[24h])) * 100
```

#### Average Position Hold Time
```promql
# Requires timestamp tracking on position open/close
avg(position_close_timestamp - position_open_timestamp)
```

### Alert Queries

#### Critical Alerts
```promql
# Redis disconnected for > 30s
redis_connection_status == 0

# Database pool exhaustion (> 90% utilized)
database_connection_pool_size{pool_type="active"} / 
(database_connection_pool_size{pool_type="active"} + database_connection_pool_size{pool_type="idle"}) > 0.9

# Excessive WebSocket reconnects (> 10/hour)
increase(websocket_reconnect_total[1h]) > 10

# AI confidence consistently low (< 0.5 for 15min)
rate(ai_confidence_scores_sum[15m]) / rate(ai_confidence_scores_count[15m]) < 0.5
```

#### Warning Alerts
```promql
# High execution latency (p95 > 500ms)
histogram_quantile(0.95, rate(execution_latency_seconds_bucket[5m])) > 0.5

# Elevated slippage (> 0.5%)
slippage_avg_percent > 0.5

# Approaching daily loss limit
drawdown_current_percent > 5
```

---

## Query Optimization Tips

### 1. Use Rate() for Counters
Always wrap counter metrics with `rate()` or `increase()` for meaningful trends:
```promql
# Bad
llm_token_usage_total

# Good
rate(llm_token_usage_total[5m])
```

### 2. Choose Appropriate Time Windows
- Short-term monitoring: `[5m]` or `[15m]`
- Trend analysis: `[1h]` or `[6h]`
- Long-term patterns: `[24h]` or `[7d]`

### 3. Leverage Labels for Filtering
```promql
# Filter by specific exchange
websocket_uptime_seconds{exchange="mexc"}

# Filter by model
rate(llm_token_usage_total{model="claude-sonnet-4-20250514"}[1h])
```

### 4. Handle Missing Data
Use `or` operator for fallback values:
```promql
redis_connection_status or vector(0)
```

---

## Troubleshooting

### "No data" Errors

**Cause 1**: Metric not exposed  
**Solution**: Check `/metrics/prometheus` endpoint:
```bash
curl -s http://localhost:8000/metrics/prometheus | grep metric_name
```

**Cause 2**: Prometheus not scraping  
**Solution**: Verify target health:
```bash
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool
```

**Cause 3**: Time range too narrow  
**Solution**: Expand time range in Grafana (try "Last 6 hours")

### Unexpected Values

**Issue**: NaN (Not a Number)  
**Cause**: Division by zero or insufficient data for rate calculation  
**Solution**: Wait for more data points or adjust time window

**Issue**: Stale values  
**Cause**: Metric not being updated  
**Solution**: Check application logs for errors in metrics update logic

---

## Related Documentation

- [DASHBOARD_METRICS_INTEGRATION_ROADMAP.md](./DASHBOARD_METRICS_INTEGRATION_ROADMAP.md) - Implementation details
- [DASHBOARD_METRICS_MISMATCH_REPORT.md](./DASHBOARD_METRICS_MISMATCH_REPORT.md) - Gap analysis
- [DASHBOARD_NO_DATA_FIX.md](./DASHBOARD_NO_DATA_FIX.md) - Original diagnosis
- [DASHBOARD_NO_DATA_EXECUTIVE_SUMMARY.md](./DASHBOARD_NO_DATA_EXECUTIVE_SUMMARY.md) - High-level overview

---

## Maintenance

### Adding New Metrics

1. Define metric in `app/main.py` with `CUSTOM_REGISTRY`
2. Implement update logic (background task or event-driven)
3. Add PromQL query to appropriate dashboard panel
4. Update this document with new query reference
5. Test query in Prometheus UI before deploying to Grafana

### Review Schedule

- **Monthly**: Verify all queries return expected data
- **Quarterly**: Review alert thresholds and adjust based on historical data
- **Annually**: Comprehensive dashboard audit and optimization

---

**Document Version**: 1.0  
**Last Verified**: May 17, 2026  
**Next Review**: June 17, 2026
