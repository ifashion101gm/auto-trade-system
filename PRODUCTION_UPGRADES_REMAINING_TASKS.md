# Production Upgrades - Remaining Tasks Checklist

**Phase 1:** ✅ Complete (Critical Fixes)  
**Phase 2:** 🔄 In Progress (Resilience & Observability)

---

## High Priority Tasks (Complete Within 1 Week)

### 1. Implement Execution Service Layer ⏳

**Issue:** `/trading/execute` endpoint returns fake success  
**Location:** `/app/dashboard/trading_api.py:97-110`

**Action Required:**
```python
# Replace placeholder with proper implementation
@router.post("/trading/execute", response_model=ExecutionResult)
async def execute_trade(
    request: Request,
    signal: TradeSignalRequest,
    auth: str = None
):
    """Execute trade through proper execution service."""
    verify_trading_secret(auth)
    await enforce_trading_rate_limit(request)
    
    # Use execution service
    execution_service = ExecutionService()
    result = await execution_service.execute_trade(signal)
    
    return result
```

**Create New File:** `/app/execution/execution_service.py`
```python
class ExecutionService:
    """Centralized trade execution with proper layering."""
    
    async def execute_trade(self, signal: TradeSignal) -> ExecutionResult:
        # 1. Validate through risk engine
        await self.risk_manager.validate(signal)
        
        # 2. Place order on exchange
        order = await self.exchange_connector.place_order(signal)
        
        # 3. Save to database
        await self.trade_repo.save(order)
        
        # 4. Publish event
        await self.event_bus.publish('ORDER_EXECUTED', order.to_dict())
        
        # 5. Send notification
        await self.notifier.notify(order)
        
        return ExecutionResult(success=True, order=order)
```

**Priority:** 🔴 CRITICAL  
**Estimated Effort:** 4-6 hours

---

### 2. Build Order Reconciliation Engine ⏳

**Purpose:** Detect and repair state mismatches between database and exchange

**Create New File:** `/app/execution/reconciliation_engine.py`
```python
class OrderReconciliationEngine:
    """Periodic reconciliation of database vs exchange state."""
    
    def __init__(self, exchange_manager, db_session_factory):
        self.exchange_manager = exchange_manager
        self.db_session_factory = db_session_factory
    
    async def run_reconciliation(self, user_id: str):
        """Compare database positions with exchange positions."""
        async with self.db_session_factory() as db_session:
            # Get open positions from database
            db_positions = await self._get_db_positions(db_session, user_id)
            
            # Get actual positions from exchange
            exchange_positions = await self.exchange_manager.get_open_positions()
            
            # Compare and detect mismatches
            mismatches = await self._detect_mismatches(db_positions, exchange_positions)
            
            # Repair or alert
            for mismatch in mismatches:
                await self._handle_mismatch(mismatch, db_session)
    
    async def _detect_mismatches(self, db_pos, exchange_pos):
        """Detect various types of mismatches."""
        mismatches = []
        
        # Check for orphaned orders (in DB but not on exchange)
        for db_trade in db_pos:
            if db_trade.exchange_order_id not in exchange_pos:
                mismatches.append({
                    'type': 'ORPHANED_ORDER',
                    'trade_id': db_trade.id,
                    'symbol': db_trade.symbol,
                    'action': 'CLOSE_OR_ALERT'
                })
        
        # Check for ghost positions (on exchange but not in DB)
        for exc_position in exchange_pos:
            if not self._exists_in_db(exc_position, db_pos):
                mismatches.append({
                    'type': 'GHOST_POSITION',
                    'exchange_order_id': exc_position['order_id'],
                    'symbol': exc_position['symbol'],
                    'action': 'IMPORT_OR_CLOSE'
                })
        
        return mismatches
    
    async def _handle_mismatch(self, mismatch, db_session):
        """Handle detected mismatch."""
        if mismatch['type'] == 'ORPHANED_ORDER':
            # Mark as failed in database
            trade = await db_session.get(PaperTrades, mismatch['trade_id'])
            trade.status = 'failed'
            trade.notes += '\nOrphaned order detected during reconciliation'
            await db_session.flush()
            
            # Alert operator
            await self.notifier.send_reconciliation_alert(...)
            
        elif mismatch['type'] == 'GHOST_POSITION':
            # Import position into database
            new_trade = PaperTrades(...)
            db_session.add(new_trade)
            await db_session.flush()
            
            # Alert operator
            await self.notifier.send_reconciliation_alert(...)
```

**Add Background Task:** `/app/main.py`
```python
async def periodic_reconciliation():
    """Run reconciliation every 60 seconds."""
    engine = OrderReconciliationEngine(exchange_manager, get_session)
    
    while True:
        try:
            await engine.run_reconciliation(user_id="default_user")
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
        
        await asyncio.sleep(60)  # Run every minute

# Start background task
asyncio.create_task(periodic_reconciliation())
```

**Priority:** 🔴 CRITICAL  
**Estimated Effort:** 8-10 hours

---

### 3. Enhance Self-Healing System with Watchdogs ⏳

**Create Watchdog Modules:**

#### API Watchdog
```python
# /app/self_healing/api_watchdog.py
class APIWatchdog:
    """Monitor exchange API health."""
    
    async def check_api_health(self):
        """Check if exchange APIs are responsive."""
        endpoints = ['ticker', 'balance', 'orders']
        
        for endpoint in endpoints:
            try:
                start = time.time()
                await self.exchange_manager.test_endpoint(endpoint)
                latency = (time.time() - start) * 1000
                
                if latency > 5000:  # 5 seconds
                    await self.trigger_degraded_mode()
                    
            except Exception:
                await self.trigger_emergency_stop()
```

#### Database Watchdog
```python
# /app/self_healing/db_watchdog.py
class DatabaseWatchdog:
    """Monitor database connectivity and transaction health."""
    
    async def check_db_health(self):
        """Check for stale transactions and connection pool exhaustion."""
        try:
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            await self.alert_db_failure()
```

#### Memory Watchdog
```python
# /app/self_healing/memory_watchdog.py
import psutil

class MemoryWatchdog:
    """Monitor memory usage and detect leaks."""
    
    async def check_memory(self):
        """Check memory usage."""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        if memory_mb > 1024:  # 1GB threshold
            logger.warning(f"High memory usage: {memory_mb:.0f}MB")
            await self.trigger_gc()
```

#### Queue Watchdog
```python
# /app/self_healing/queue_watchdog.py
class QueueWatchdog:
    """Monitor task queue for frozen workers."""
    
    async def check_queue_health(self):
        """Check if tasks are processing."""
        last_processed = await self.get_last_task_time()
        
        if (datetime.utcnow() - last_processed).seconds > 300:
            logger.error("Task queue appears frozen!")
            await self.restart_workers()
```

**Priority:** 🟡 HIGH  
**Estimated Effort:** 12-15 hours

---

### 4. Add Structured JSON Logging ⏳

**Create JSON Logger:** `/app/logging_config.py`
```python
import json
import logging
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for Loki/Grafana integration."""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'correlation_id'):
            log_entry['correlation_id'] = record.correlation_id
        
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_json_logging():
    """Configure JSON logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
```

**Usage Example:**
```python
logger.info("Order executed", extra={
    'correlation_id': 'abc-123',
    'extra_data': {
        'event': 'ORDER_EXECUTED',
        'symbol': 'XAUUSDT',
        'side': 'BUY',
        'qty': 0.1,
        'latency_ms': 523
    }
})
```

**Priority:** 🟡 HIGH  
**Estimated Effort:** 4-6 hours

---

### 5. Async Task Isolation for Dual Exchange Trading ⏳

**Fix:** `/app/execution/trading_service.py:1245-1250`

**Current Problem:**
```python
result = await hybrid_manager.execute_dual_trade(...)
# If one fails, what happens to the other?
```

**Solution:**
```python
async def execute_dual_gold_trade(self, proposal, user_id, db_session):
    """Execute Gold trade with proper error isolation."""
    binance_result = None
    mexc_result = None
    
    try:
        # Try MEXC first (primary)
        mexc_result = await self._execute_mexc_trade(proposal, user_id, db_session)
        
        # If MEXC succeeds, try Binance
        if mexc_result['status'] == 'success':
            binance_result = await self._execute_binance_trade(proposal, user_id, db_session)
        else:
            logger.error("MEXC trade failed, skipping Binance")
            raise Exception(f"MEXC execution failed: {mexc_result.get('error')}")
            
    except Exception as e:
        # Rollback: Close MEXC position if Binance failed
        if mexc_result and mexc_result['status'] == 'success' and not binance_result:
            logger.warning(f"Binance failed after MEXC success, closing MEXC position: {e}")
            await self._close_mexc_position(mexc_result['order']['order_id'])
            mexc_result = {
                'status': 'rolled_back',
                'reason': str(e),
                'original_result': mexc_result
            }
        
        raise
    
    return {
        'binance': binance_result,
        'mexc': mexc_result
    }
```

**Alternative: Parallel Execution with Isolation**
```python
async def execute_parallel_trades(self, signals):
    """Execute multiple trades with isolation."""
    tasks = [
        asyncio.create_task(self.execute_single_trade(signal))
        for signal in signals
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    successful = []
    failed = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Trade {i} failed: {result}")
            failed.append({'signal': signals[i], 'error': str(result)})
        else:
            successful.append(result)
    
    return {'successful': successful, 'failed': failed}
```

**Priority:** 🟡 HIGH  
**Estimated Effort:** 3-4 hours

---

## Medium Priority Tasks (Complete Within 1 Month)

### 6. Implement Circuit Breaker Levels ⏳

**Enhance:** `/app/infra/circuit_breaker.py`

```python
class CircuitBreakerState(Enum):
    CLOSED = "closed"           # Normal operation
    WARNING = "warning"         # Log only
    DEGRADED = "degraded"       # Reduce trade size
    CRITICAL = "critical"       # Stop new entries
    EMERGENCY = "emergency"     # Close all positions

class EnhancedCircuitBreaker:
    """Multi-level circuit breaker."""
    
    async def check_state(self):
        """Return appropriate action based on severity."""
        failures = self.get_recent_failures()
        
        if failures >= 10:
            return CircuitBreakerState.EMERGENCY
        elif failures >= 5:
            return CircuitBreakerState.CRITICAL
        elif failures >= 3:
            return CircuitBreakerState.DEGRADED
        elif failures >= 1:
            return CircuitBreakerState.WARNING
        else:
            return CircuitBreakerState.CLOSED
    
    async def handle_state(self, state):
        """Take action based on circuit breaker state."""
        if state == CircuitBreakerState.EMERGENCY:
            await self.close_all_positions()
            await self.notifier.send_emergency_alert()
            
        elif state == CircuitBreakerState.CRITICAL:
            await self.stop_new_entries()
            await self.notifier.send_critical_alert()
            
        elif state == CircuitBreakerState.DEGRADED:
            await self.reduce_position_size(0.5)  # 50% reduction
            await self.notifier.send_warning_alert()
```

**Priority:** 🟢 MEDIUM  
**Estimated Effort:** 6-8 hours

---

### 7. Add Health Check Endpoints ⏳

**Create:** `/app/dashboard/health_api.py`

```python
@router.get("/health")
async def health_check():
    """Public health check (no auth)."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check(auth: str = None):
    """Detailed health check with authentication."""
    verify_trading_secret(auth)
    
    # Check components
    db_status = await check_database()
    redis_status = await check_redis()
    exchange_status = await check_exchange()
    
    overall = "healthy" if all([db_status, redis_status, exchange_status]) else "degraded"
    
    return {
        "status": overall,
        "components": {
            "database": db_status,
            "redis": redis_status,
            "exchange": exchange_status
        },
        "timestamp": datetime.utcnow().isoformat()
    }
```

**Priority:** 🟢 MEDIUM  
**Estimated Effort:** 2-3 hours

---

### 8. Add Metrics & Analytics Endpoints ⏳

**Create:** `/app/dashboard/metrics_api.py`

```python
@router.get("/metrics/performance")
async def get_performance_metrics(
    user_id: str,
    period: str = "24h",
    db_session: AsyncSession = Depends(get_session)
):
    """Get trading performance metrics."""
    # Query closed trades
    # Calculate win rate, P&L, Sharpe ratio, etc.
    return {...}

@router.get("/trades/history")
async def get_trade_history(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    db_session: AsyncSession = Depends(get_session)
):
    """Get paginated trade history."""
    # Query trades with pagination
    return {"trades": [...], "total": count}
```

**Priority:** 🟢 MEDIUM  
**Estimated Effort:** 4-6 hours

---

## Low Priority Tasks (Improve When Convenient)

### 9. Add OpenAPI Documentation ⏳

**Add Pydantic models and docstrings to all endpoints**

**Priority:** 🔵 LOW  
**Estimated Effort:** 3-4 hours

---

### 10. Standardize Error Handling Patterns ⏳

**Create unified result object:**
```python
@dataclass
class OperationResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Priority:** 🔵 LOW  
**Estimated Effort:** 6-8 hours

---

### 11. Add Distributed Tracing ⏳

**Implement correlation IDs across all layers**

**Priority:** 🔵 LOW  
**Estimated Effort:** 4-6 hours

---

## Summary

| Task | Priority | Status | Est. Hours |
|------|----------|--------|------------|
| Execution Service Layer | 🔴 CRITICAL | ⏳ Pending | 4-6 |
| Order Reconciliation Engine | 🔴 CRITICAL | ⏳ Pending | 8-10 |
| Self-Healing Watchdogs | 🟡 HIGH | ⏳ Pending | 12-15 |
| Structured JSON Logging | 🟡 HIGH | ⏳ Pending | 4-6 |
| Async Task Isolation | 🟡 HIGH | ⏳ Pending | 3-4 |
| Circuit Breaker Levels | 🟢 MEDIUM | ⏳ Pending | 6-8 |
| Health Check Endpoints | 🟢 MEDIUM | ⏳ Pending | 2-3 |
| Metrics Endpoints | 🟢 MEDIUM | ⏳ Pending | 4-6 |
| OpenAPI Documentation | 🔵 LOW | ⏳ Pending | 3-4 |
| Error Handling Standardization | 🔵 LOW | ⏳ Pending | 6-8 |
| Distributed Tracing | 🔵 LOW | ⏳ Pending | 4-6 |

**Total Estimated Effort:** 54-75 hours

---

## Recommended Implementation Order

**Week 1:** Execution Service + Reconciliation Engine (CRITICAL)  
**Week 2:** Watchdogs + JSON Logging + Task Isolation (HIGH)  
**Week 3:** Circuit Breakers + Health Checks + Metrics (MEDIUM)  
**Week 4:** Documentation + Error Handling + Tracing (LOW)

---

**Last Updated:** May 14, 2026  
**Status:** Phase 1 Complete, Phase 2 Ready to Start
