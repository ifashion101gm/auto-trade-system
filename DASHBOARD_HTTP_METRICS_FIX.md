# HTTP Metrics Dashboard Fix - Request Rate, Error Rate, API Response Time

## Issue

Three panels in the Grafana dashboard showing "No data":
- Request Rate
- Error Rate  
- API Response Time

## Root Cause

The metrics **are being tracked** by the middleware but appear as "No data" due to:

1. **Low traffic volume**: Only ~45 requests since restart (mostly Prometheus scrapes)
2. **Rate calculation over 5m window**: With low traffic, `rate()` returns very small values
3. **Zero error count**: No 5xx errors means error rate query may return empty result
4. **Grafana visualization**: May not display near-zero values properly

## Current Status

✅ **Metrics ARE exposed and working:**
```bash
$ curl -s http://localhost:8000/metrics/prometheus | grep "^http_requests_total"
http_requests_total{method="GET",path="/metrics/prometheus",status="200"} 41.0
http_requests_total{method="GET",path="/health",status="200"} 4.0

$ curl -s http://localhost:8000/metrics/prometheus | grep "^http_request_duration"
http_request_duration_seconds_bucket{le="0.005"} 25.0
http_request_duration_seconds_bucket{le="0.01"} 33.0
...
```

✅ **Prometheus queries work:**
```bash
$ curl -s "http://localhost:9090/api/v1/query?query=rate(http_requests_total[5m])"
Status: success
Results: 2
  /health: 0.0069 req/s
  /metrics/prometheus: 0.103 req/s
```

## Solutions

### Option 1: Adjust Grafana Time Range (Immediate Fix)

**Problem**: 5-minute rate window with low traffic shows near-zero values

**Solution**: 
1. In Grafana, change time range from "Last 5 minutes" to "Last 1 hour" or "Last 6 hours"
2. This gives more data points for rate calculation
3. Values will still be low but should display

**Steps**:
- Open Grafana dashboard
- Click time picker (top right)
- Select "Last 1h" or "Last 6h"
- Click "Apply"

### Option 2: Update Dashboard Queries (Recommended)

Modify the PromQL queries to handle low-traffic scenarios better:

#### Request Rate Panel
**Current Query**:
```promql
rate(http_requests_total[5m])
```

**Improved Query** (sum all requests):
```promql
sum(rate(http_requests_total[5m]))
```

**Alternative** (use longer window):
```promql
sum(rate(http_requests_total[15m]))
```

#### Error Rate Panel
**Current Query**:
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100
```

**Improved Query** (handle division by zero):
```promql
(
  sum(rate(http_requests_total{status=~"5.."}[5m])) 
  / 
  sum(rate(http_requests_total[5m]))
) * 100
or vector(0)
```

This ensures the panel shows "0%" instead of "No data" when there are no errors.

#### API Response Time Panel
**Current Query**:
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))
```

**Improved Query** (use longer window):
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[15m]))
histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[15m]))
```

### Option 3: Generate Test Traffic (For Verification)

To verify the panels work correctly, generate some test traffic:

```bash
# Generate 100 requests over 2 minutes
for i in {1..100}; do
  curl -s http://localhost:8000/health > /dev/null &
  sleep 0.02
done

# Wait 1 minute, then check Grafana
sleep 60
```

After this, the panels should show:
- **Request Rate**: ~0.8-1.0 req/s
- **Error Rate**: 0% (all requests successful)
- **API Response Time**: ~5-10ms (p50 and p95)

## Implementation Plan

### Immediate Actions (5 minutes)
1. ✅ Verify metrics are exposed (DONE - confirmed working)
2. ✅ Verify Prometheus can query them (DONE - confirmed working)
3. ⏳ Adjust Grafana time range to "Last 1h" or "Last 6h"
4. ⏳ Check if panels now display data

### Short-term Fixes (30 minutes)
1. Update dashboard JSON with improved queries
2. Add `or vector(0)` fallback for error rate
3. Change rate windows from 5m to 15m for stability
4. Reload dashboard in Grafana

### Long-term Improvements (Optional)
1. Add request counting per endpoint for better visibility
2. Create separate panels for different endpoint groups
3. Add alerts for high error rates (>1%)
4. Add alerts for high latency (p95 > 500ms)

## Updated Dashboard Queries

Here are the recommended query updates for `monitoring/grafana/dashboards/trading-system.json`:

### Panel 1: Request Rate (Line 59)
```json
"expr": "sum(rate(http_requests_total[15m]))"
```

### Panel 2: Error Rate (Line 119)
```json
"expr": "(sum(rate(http_requests_total{status=~\"5..\"}[15m])) / sum(rate(http_requests_total[15m]))) * 100 or vector(0)"
```

### Panel 3: API Response Time (Lines 206, 215)
```json
"expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[15m]))"
"expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[15m]))"
```

## Verification Checklist

After applying fixes:

- [ ] Request Rate panel shows value > 0 (even if small)
- [ ] Error Rate panel shows "0%" (not "No data")
- [ ] API Response Time panel shows latency lines
- [ ] All panels update when refreshing dashboard
- [ ] Panels respond to time range changes
- [ ] No console errors in browser developer tools

## Why This Happens

### Understanding Prometheus `rate()` Function

The `rate()` function calculates per-second average rate of increase over a time window.

**Example with low traffic**:
- 41 requests over 10 minutes = 0.068 requests/second
- Over 5-minute window: even fewer requests
- Grafana may display this as "No data" if below visualization threshold

**Example with normal traffic**:
- 1000 requests over 10 minutes = 1.67 requests/second
- Clearly visible in graphs

### Why Error Rate Shows "No Data"

When there are **zero 5xx errors**:
```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))  # Returns 0 or no data
/
sum(rate(http_requests_total[5m]))                  # Returns small positive number
```

If numerator returns "no data" (not 0), the division results in "no data".

**Fix**: Use `or vector(0)` to convert "no data" to actual zero:
```promql
(sum(rate(http_requests_total{status=~"5.."}[5m])) or vector(0)) 
/ 
sum(rate(http_requests_total[5m])) 
* 100
```

## Related Documentation

- [DASHBOARD_METRICS_INTEGRATION_ROADMAP.md](./DASHBOARD_METRICS_INTEGRATION_ROADMAP.md) - Main metrics integration
- [DASHBOARD_PROMQL_QUERIES.md](./DASHBOARD_PROMQL_QUERIES.md) - PromQL query reference
- [DASHBOARD_NO_DATA_FIX.md](./DASHBOARD_NO_DATA_FIX.md) - Previous dashboard fix

---

**Date**: May 17, 2026  
**Status**: Analysis Complete, Fix Ready  
**Priority**: LOW (metrics working, just low traffic)
