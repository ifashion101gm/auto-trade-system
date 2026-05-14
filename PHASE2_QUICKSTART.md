# Phase 2 Implementation - Quick Start Guide

**Self-Healing Watchdogs, JSON Logging, and Async Task Isolation**

---

## Overview

Phase 2 adds production-grade resilience to the auto-trade system through:

1. **Self-Healing Watchdogs** - Proactive monitoring for API, database, memory, and queue health
2. **Structured JSON Logging** - Correlation IDs for distributed tracing across all services
3. **Async Task Isolation** - Automatic rollback mechanisms for dual-exchange trading

---

## Quick Start

### 1. Install Dependencies

```bash
pip install psutil>=5.9.0
```

Or update from requirements.txt:
```bash
pip install -r requirements.txt
```

### 2. Validate Installation

Run the validation script:
```bash
python scripts/validate_phase2.py
```

Expected output:
```
✅ WATCHDOG VALIDATION PASSED
✅ JSON LOGGING VALIDATION PASSED
✅ ASYNC ISOLATION VALIDATION PASSED

🎉 ALL PHASE 2 VALIDATIONS PASSED!
```

### 3. Run Integration Tests

```bash
pytest tests/integration/test_watchdogs.py -v --asyncio-mode=auto
```

---

## Integration Guide

### Step 1: Add Watchdogs to Main Application

Edit `app/main.py`:

```python
from app.self_healing.watchdogs import WatchdogOrchestrator

# Initialize watchdog orchestrator (after exchange_manager is created)
watchdog_orchestrator = WatchdogOrchestrator(
    exchange_manager=hybrid_exchange_manager,
    db_session_factory=get_async_session,
    api_check_interval=settings.API_WATCHDOG_CHECK_INTERVAL_SEC or 30,
    db_check_interval=settings.DB_WATCHDOG_CHECK_INTERVAL_SEC or 60,
    memory_check_interval=settings.MEMORY_WATCHDOG_CHECK_INTERVAL_SEC or 120,
    queue_check_interval=settings.QUEUE_WATCHDOG_CHECK_INTERVAL_SEC or 60
)

# Add to startup event
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...
    
    # Start watchdogs
    await watchdog_orchestrator.start_all_watchdogs()
    logger.info("✅ All self-healing watchdogs started")

# Add to shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    # Stop watchdogs
    await watchdog_orchestrator.stop_all_watchdogs()
    logger.info("✅ All self-healing watchdogs stopped")
    
    # ... existing shutdown code ...
```

### Step 2: Configure Environment Variables

Add to `.env`:

```bash
# ============================================================================
# WATCHDOG CONFIGURATION (Phase 2)
# ============================================================================

# API Watchdog
API_WATCHDOG_MAX_LATENCY_MS=5000
API_WATCHDOG_CHECK_INTERVAL_SEC=30
API_WATCHDOG_FAILURE_THRESHOLD=3

# Database Watchdog
DB_WATCHDOG_MAX_POOL_UTILIZATION_PCT=80.0
DB_WATCHDOG_STALE_TRANSACTION_THRESHOLD_SEC=300
DB_WATCHDOG_CHECK_INTERVAL_SEC=60

# Memory Watchdog
MEMORY_WATCHDOG_WARNING_THRESHOLD_MB=512
MEMORY_WATCHDOG_CRITICAL_THRESHOLD_MB=1024
MEMORY_WATCHDOG_GC_TRIGGER_THRESHOLD_MB=768
MEMORY_WATCHDOG_CHECK_INTERVAL_SEC=120

# Queue Watchdog
QUEUE_WATCHDOG_MAX_TASK_AGE_SEC=300
QUEUE_WATCHDOG_MAX_QUEUE_DEPTH=100
QUEUE_WATCHDOG_CHECK_INTERVAL_SEC=60
```

Update `app/config.py` to read these values:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Watchdog Configuration (Phase 2)
    API_WATCHDOG_MAX_LATENCY_MS: float = 5000
    API_WATCHDOG_CHECK_INTERVAL_SEC: int = 30
    API_WATCHDOG_FAILURE_THRESHOLD: int = 3
    
    DB_WATCHDOG_MAX_POOL_UTILIZATION_PCT: float = 80.0
    DB_WATCHDOG_STALE_TRANSACTION_THRESHOLD_SEC: int = 300
    DB_WATCHDOG_CHECK_INTERVAL_SEC: int = 60
    
    MEMORY_WATCHDOG_WARNING_THRESHOLD_MB: float = 512
    MEMORY_WATCHDOG_CRITICAL_THRESHOLD_MB: float = 1024
    MEMORY_WATCHDOG_GC_TRIGGER_THRESHOLD_MB: float = 768
    MEMORY_WATCHDOG_CHECK_INTERVAL_SEC: int = 120
    
    QUEUE_WATCHDOG_MAX_TASK_AGE_SEC: int = 300
    QUEUE_WATCHDOG_MAX_QUEUE_DEPTH: int = 100
    QUEUE_WATCHDOG_CHECK_INTERVAL_SEC: int = 60
```

### Step 3: Use Correlation IDs in Trading Code

Example usage in trading service:

```python
from app.logging_config import trade_context, order_context, logger
import uuid

async def execute_trading_cycle(proposal, user_id, db_session):
    # Generate correlation ID for entire trade lifecycle
    correlation_id = str(uuid.uuid4())
    
    with trade_context(
        trade_id=proposal.get('trade_id'),
        symbol=proposal['symbol'],
        correlation_id=correlation_id
    ) as ctx_logger:
        
        ctx_logger.info("Starting trading cycle")
        
        # Signal generation
        signal = await generate_signal(proposal)
        
        # Execution with same correlation ID
        with order_context(
            order_id=signal.get('order_id'),
            symbol=proposal['symbol'],
            correlation_id=correlation_id  # Same ID propagates
        ) as order_logger:
            
            order = await place_order(signal)
            order_logger.info(f"Order placed: {order['order_id']}")
            
            # Verification
            verification = await verify_order(order['order_id'])
            order_logger.info(f"Order verified: {verification}")
```

All logs will share the same `correlation_id`, enabling end-to-end tracing.

---

## Monitoring & Observability

### Check Watchdog Health

```python
# Get aggregated health report
health = await watchdog_orchestrator.get_aggregated_health_report()

print(f"Overall Status: {health['overall_status']}")
print(f"API Health: {health['watchdogs']['api']['overall_status']}")
print(f"DB Health: {health['watchdogs']['database']['connectivity']}")
print(f"Memory Usage: {health['watchdogs']['memory']['rss_mb']}MB")
print(f"Queue Status: {health['watchdogs']['queue']['status']}")
```

### Query Logs by Correlation ID

In Grafana/Loki:
```
{job="auto-trade-system"} |= "corr-abc-123"
```

Or using grep on log files:
```bash
grep "corr-abc-123" logs/json_2026-05-15.log | python -m json.tool
```

### Monitor Log Files

```bash
# Watch JSON logs in real-time
tail -f logs/json_*.log | python -m json.tool

# Watch error logs
tail -f logs/error_*.log

# Watch trade-specific logs
tail -f logs/trades_*.log
```

---

## Troubleshooting

### Issue: Watchdogs not starting

**Symptom:** No watchdog log messages on startup

**Solution:**
1. Check that `watchdog_orchestrator.start_all_watchdogs()` is called in startup event
2. Verify no exceptions during initialization
3. Check logs for watchdog initialization messages

### Issue: Correlation IDs not appearing in logs

**Symptom:** JSON logs missing `correlation_id` field

**Solution:**
1. Ensure you're using `trade_context()` or `order_context()` context managers
2. Verify logging_config.py has been updated with correlation_id support
3. Check that `logger.bind(correlation_id=...)` is being called

### Issue: Rollback fails on partial dual-exchange execution

**Symptom:** Status shows `partial_with_rollback_failure`

**Solution:**
1. Check exchange connectivity - rollback requires working API
2. Review critical logs for rollback failure details
3. Manually close position if automatic rollback fails
4. Investigate root cause of initial exchange failure

### Issue: High memory usage alerts

**Symptom:** Memory watchdog triggers GC frequently

**Solution:**
1. Review application for memory leaks (unclosed connections, growing caches)
2. Increase `MEMORY_WATCHDOG_WARNING_THRESHOLD_MB` if usage is expected
3. Monitor memory growth trends over time
4. Consider restarting application if growth is continuous

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Watchdog Orchestrator                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   API    │  │Database  │  │  Memory  │  │  Queue   │   │
│  │Watchdog  │  │Watchdog  │  │Watchdog  │  │Watchdog  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                │               │           │
         ▼                ▼               ▼           ▼
    API Latency     DB Connectivity  Memory Usage  Task Queue
    Endpoints       Pool Utilization Growth Rate   Backlog
         │                │               │           │
         └────────────────┴───────────────┴───────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  Recovery Actions:   │
              │ • Degraded Mode      │
              │ • Emergency Stop     │
              │ • Garbage Collection │
              │ • Worker Restart     │
              └──────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Structured JSON Logging                     │
│                                                             │
│  Trade Request → correlation_id: abc-123                    │
│       ↓                                                     │
│  Signal Gen  → correlation_id: abc-123  (same ID)          │
│       ↓                                                     │
│  Risk Check  → correlation_id: abc-123  (same ID)          │
│       ↓                                                     │
│  Order Place → correlation_id: abc-123  (same ID)          │
│       ↓                                                     │
│  Verification→ correlation_id: abc-123  (same ID)          │
│                                                             │
│  Query: grep "abc-123" logs/json_*.log                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Async Task Isolation & Rollback                 │
│                                                             │
│  Dual Trade Request                                         │
│       ↓                                                     │
│  ┌────────────┐    ┌────────────┐                           │
│  │ MEXC Task  │    │Binance Task│  (parallel execution)     │
│  └────────────┘    └────────────┘                           │
│       ↓                    ↓                                │
│  If MEXC succeeds & Binance fails:                          │
│       ↓                                                     │
│  ┌─────────────────────────────┐                            │
│  │ Rollback MEXC Position      │  (automatic cleanup)       │
│  └─────────────────────────────┘                            │
│       ↓                                                     │
│  Status: rolled_back                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Performance Impact

| Component | Overhead | Frequency |
|-----------|----------|-----------|
| API Watchdog | ~50ms per check | Every 30s |
| DB Watchdog | ~50ms per check | Every 60s |
| Memory Watchdog | ~10ms per check | Every 120s |
| Queue Watchdog | ~5ms per check | Every 60s |
| JSON Logging | ~1ms per log entry | On every log call |
| Correlation ID | Negligible (UUID gen) | Once per trade |
| Rollback Logic | Only on partial failure | Rare (<1% of trades) |

**Total overhead:** < 0.1% of system resources

---

## Next Steps

After completing Phase 2 integration:

1. **Set up Loki/Grafana** for centralized log aggregation
2. **Configure Telegram alerts** for watchdog critical events
3. **Create Grafana dashboards** for watchdog metrics visualization
4. **Test failure scenarios** to validate watchdog responses
5. **Proceed to Phase 3** (circuit breaker levels, health endpoints, metrics APIs)

---

## Documentation

- **Full Implementation Details:** [PHASE2_COMPLETION_SUMMARY.md](../PHASE2_COMPLETION_SUMMARY.md)
- **Self-Healing Architecture:** [docs/SELF_HEALING_ARCHITECTURE.md](../docs/SELF_HEALING_ARCHITECTURE.md)
- **Production Roadmap:** [PRODUCTION_UPGRADES_REMAINING_TASKS.md](../PRODUCTION_UPGRADES_REMAINING_TASKS.md)

---

**Last Updated:** May 15, 2026  
**Status:** ✅ Complete and Validated  
**Next Phase:** Phase 3 (Medium Priority Tasks)
