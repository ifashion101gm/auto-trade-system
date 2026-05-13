# Self-Healing Trading Architecture

## Overview

The Auto Trade System has been upgraded from a fragile linear pipeline ("Signal → Order → Done") to a **resilient closed-loop lifecycle** with self-healing capabilities. The system now automatically detects, diagnoses, and repairs issues without manual intervention.

### Closed-Loop Lifecycle

```
Signal → Execution → Verification → Monitoring → Recovery → Reconciliation
   ↑                                                              |
   └──────────────────────────────────────────────────────────────┘
```

---

## Architecture Components

### 6 Specialized Agents

| Agent | Responsibility | Key Features |
|-------|----------------|--------------|
| **SignalAgent** | Generate trade signals with risk validation | AI orchestration + deterministic risk checks |
| **ExecutionAgent** | Place orders with retry logic | Exponential backoff, slippage protection |
| **VerificationAgent** | Post-execution state verification | Exchange order check, DB sync validation |
| **MonitoringAgent** | Continuous health tracking | Circuit breaker, latency, drawdown monitoring |
| **RecoveryAgent** | Automatic failure recovery | State reset, API reconnection, reconciliation |
| **ReconciliationAgent** | Exchange-DB consistency checks | Position sync, orphan detection, auto-repair |

### Base Agent Pattern

All agents inherit from `BaseAgent` which provides:
- Standardized error handling wrapper
- Metrics collection (error count, last run timestamp)
- Structured result format (`success`, `agent`, `timestamp`)

```python
class BaseAgent(ABC):
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper with error handling and metrics."""
        try:
            self.last_run = datetime.utcnow()
            result = await self.execute(context)
            result['agent'] = self.name
            result['success'] = True
            return result
        except Exception as e:
            self.error_count += 1
            return {
                'agent': self.name,
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
```

---

## Integration Flow

### Trading Cycle Enhancement

The `execute_trading_cycle()` method in `trading_service.py` now integrates agents at each stage:

1. **Pre-Cycle Health Check** (MonitoringAgent)
   - Verifies circuit breaker status
   - Tests API connectivity
   - Checks drawdown limits
   - Blocks trading if unhealthy

2. **Signal Generation** (SignalAgent)
   - Runs AI analysis via orchestrator
   - Validates against risk engine
   - Returns approved proposal or rejection reason

3. **Order Execution** (ExecutionAgent)
   - Places market order with retry logic (3 attempts)
   - Exponential backoff on failures
   - Slippage detection and warning
   - Tracks order lifecycle state

4. **Post-Execution Verification** (VerificationAgent)
   - Confirms order exists on exchange
   - Validates TP/SL orders placed
   - Checks database record created
   - Triggers recovery if verification fails

5. **Position Monitoring** (PositionMonitor service)
   - Starts continuous SL/TP enforcement
   - Monitors position health

6. **Post-Cycle Reconciliation** (ReconciliationAgent)
   - Cross-validates exchange positions vs database
   - Detects orphaned/ghost positions
   - Auto-repairs inconsistencies

7. **Periodic Background Reconciliation**
   - Runs every 60 seconds independently
   - Alerts on critical sync issues via Telegram

### Code Example

```python
async def execute_trading_cycle(self, symbol: str, user_id: str, db_session):
    # Pre-cycle health check
    health_check = await self.monitoring_agent.run({
        'user_id': user_id,
        'db_session': db_session
    })
    
    if not health_check.get('can_continue_trading', True):
        return {'status': 'blocked_by_health_check'}
    
    # Signal generation
    signal_result = await self.signal_agent.run({
        'market_data': market_data,
        'user_id': user_id,
        'db_session': db_session
    })
    
    if not signal_result.get('signal'):
        return {'status': 'no_signal'}
    
    # Execution with retries
    execution_result = await self.execution_agent.run({
        'proposal': signal_result['signal'],
        'user_id': user_id
    })
    
    # Immediate verification
    verification_result = await self.verification_agent.run({
        'execution_result': execution_result,
        'proposal': signal_result['signal'],
        'db_session': db_session
    })
    
    if not verification_result.get('verification_passed'):
        # Auto-recover
        await self.recovery_agent.run({
            'issues': [{'type': 'verification_failed'}],
            'user_id': user_id,
            'db_session': db_session
        })
```

---

## Recovery Scenarios

### 1. Circuit Breaker Open

**Detection**: MonitoringAgent detects open circuit breaker  
**Action**: RecoveryAgent waits for cooldown period, then re-checks health  
**Result**: Trading resumes when API errors subside

### 2. API Connectivity Failure

**Detection**: MonitoringAgent fails connectivity test  
**Action**: RecoveryAgent attempts reconnection via test API call  
**Result**: Connection restored or trading blocked until fixed

### 3. State Machine Stuck

**Detection**: StateValidator detects invalid transition or ERROR state  
**Action**: RecoveryAgent triggers full startup recovery sequence  
**Result**: State reset to IDLE, positions reconciled

### 4. Verification Failure

**Detection**: VerificationAgent can't find order on exchange  
**Action**: RecoveryAgent triggers reconciliation to sync state  
**Result**: Database updated to match exchange reality

### 5. Position Sync Error

**Detection**: ReconciliationAgent finds mismatch between exchange and DB  
**Action**: Auto-repair updates local records  
**Result**: Data integrity restored

---

## Configuration

### Agent Thresholds

All thresholds are configurable in agent initialization:

```python
# Execution Agent
execution_agent = ExecutionAgent(
    exchange_manager=exchange_manager,
    max_retries=3,              # Retry failed orders 3 times
    max_slippage_pct=0.5        # Warn if slippage > 0.5%
)

# Monitoring Agent
monitoring_agent = MonitoringAgent(
    circuit_breaker=circuit_breaker,
    position_monitor=position_monitor,
    max_latency_ms=5000,        # Alert if API latency > 5s
    max_drawdown_pct=5.0        # Block trading if drawdown > 5%
)
```

### Environment Variables

Add to `.env`:

```bash
# Self-healing configuration
MAX_EXECUTION_RETRIES=3
MAX_SLIPPAGE_PCT=0.5
MAX_API_LATENCY_MS=5000
MAX_DRAWDOWN_PCT=5.0
RECONCILIATION_INTERVAL_SEC=60
```

---

## Observability

### Agent Metrics

Each agent tracks:
- `last_run`: Timestamp of last execution
- `error_count`: Total errors encountered
- `is_active`: Whether agent is currently running

Access metrics via:
```python
metrics = agent.get_metrics()
# Returns: {'name': 'ExecutionAgent', 'is_active': False, 
#           'last_run': '2026-05-14T05:20:00', 'error_count': 2}
```

### Logging

Agents use structured logging with agent-specific loggers:
- `agent.SignalAgent`
- `agent.ExecutionAgent`
- `agent.VerificationAgent`
- `agent.MonitoringAgent`
- `agent.RecoveryAgent`
- `agent.ReconciliationAgent`

Example log output:
```
2026-05-14 05:20:15 | WARNING | agent.ExecutionAgent | Execution attempt 1 failed: Network timeout
2026-05-14 05:20:17 | INFO | agent.ExecutionAgent | Order executed on attempt 2
2026-05-14 05:20:18 | WARNING | agent.VerificationAgent | High slippage detected: 0.75%
2026-05-14 05:20:20 | INFO | agent.ReconciliationAgent | Reconciliation complete: 2 positions synced
```

### Event Bus Integration

Agents publish events for external monitoring:
- `execution.order_placed`
- `verification.failed`
- `recovery.attempted`
- `reconciliation.completed`

Subscribe via:
```python
event_bus.subscribe("verification.failed", handler_function)
```

---

## Testing

### Integration Tests

Comprehensive test suite in `tests/integration/test_self_healing_agents.py`:

```bash
# Run all agent tests
pytest tests/integration/test_self_healing_agents.py -v

# Run specific test category
pytest tests/integration/test_self_healing_agents.py::TestSelfHealingAgents -v
pytest tests/integration/test_self_healing_agents.py::TestAgentErrorHandling -v
pytest tests/integration/test_self_healing_agents.py::TestAgentMetrics -v
```

### Test Coverage

- ✅ Verification detects missing orders
- ✅ Verification confirms existing orders
- ✅ Recovery handles state mismatches
- ✅ Monitoring blocks trading on circuit breaker
- ✅ Monitoring allows trading when healthy
- ✅ Execution retries on failure (exponential backoff)
- ✅ Execution detects high slippage
- ✅ Reconciliation detects sync issues
- ✅ Base agent error handling
- ✅ Recovery handles unknown issue types
- ✅ Agent metrics tracking
- ✅ Agent timestamp updates

---

## Troubleshooting

### Common Issues

#### 1. "Trading blocked by health check"

**Cause**: MonitoringAgent detected unhealthy system state  
**Check**:
```python
# Review health check results
health = await monitoring_agent.run({...})
print(health['issues'])
```

**Fix**: Address underlying issue (API errors, high latency, excessive drawdown)

#### 2. "Verification failed - triggering recovery"

**Cause**: Order not found on exchange or DB sync issue  
**Check**:
```python
# Review verification details
verification = await verification_agent.run({...})
print(verification['checks'])
```

**Fix**: RecoveryAgent will auto-repair. If persistent, check exchange API status.

#### 3. "Reconciliation found issues"

**Cause**: Exchange positions don't match database  
**Check**:
```python
# Review reconciliation details
recon = await reconciliation_agent.run({...})
print(f"Orphaned: {recon['orphaned_positions']}")
print(f"Ghosts: {recon['ghost_positions']}")
```

**Fix**: Auto-repair enabled by default. Manual fix via `reconciliation_service.reconcile_positions(auto_repair=True)`

#### 4. Agent Import Errors

**Cause**: Circular dependencies in agent imports  
**Fix**: Use lazy imports via `__getattr__` in `app/execution/agents/__init__.py`

```python
from app.execution.agents import ExecutionAgent  # Lazy-loaded
```

---

## Rollback Plan

If issues arise with the self-healing architecture:

1. **Disable Agents**: Set `use_agents=False` in trading service config (future enhancement)
2. **Revert to Original Flow**: Keep original `execute_trading_cycle` logic as fallback
3. **Keep Agent Code**: Retain agent implementations for debugging/future use

Currently, agents are additive - they enhance rather than replace existing functionality.

---

## Future Enhancements

### Planned Improvements

1. **Duplicate Order Protection**
   - Signal hash tracking to prevent duplicate execution
   - Redis-based deduplication cache

2. **AI Anomaly Detection**
   - Unusual latency patterns
   - Repeated order failures
   - Abnormal slippage trends
   - Overtrading detection

3. **Multi-Agent Supervisors**
   - Execution supervisor monitors all executions
   - Risk supervisor enforces global limits
   - Latency supervisor optimizes response times

4. **Cross-Exchange Smart Routing**
   - Best execution across Binance/MEXC/Bybit
   - Liquidity-aware routing
   - Cost optimization

5. **Crash Recovery Enhancement**
   - Persistent state storage (Redis)
   - Automatic restart with state restoration
   - Missing SL/TP repair on startup

6. **Websocket Auto-Reconnect**
   - Market data stream recovery
   - Missing candle download
   - Orderbook resynchronization

---

## Design Principles

### 1. Agent Isolation
Each agent has a single responsibility and communicates via structured dictionaries, making them independently testable and replaceable.

### 2. Non-Breaking Integration
Agents wrap existing functionality rather than replacing it. The system maintains backward compatibility while gaining self-healing capabilities.

### 3. Recovery Priority
The system prioritizes auto-repair over failure. Every error path includes a recovery attempt before returning failure to the caller.

### 4. Event Bus Integration
Agents publish events for observability but don't depend on event bus for core functionality (graceful degradation).

### 5. Configuration-Driven
All thresholds (max retries, slippage %, latency limits) are configurable via environment variables or settings.

---

## Critical Success Factors

1. **Verification Speed**: Post-execution verification must complete within 2 seconds to avoid blocking the trading cycle.

2. **Recovery Idempotency**: Recovery actions must be safe to retry without causing duplicate repairs.

3. **Monitoring Overhead**: Health checks should add <100ms latency to trading cycles.

4. **Database Consistency**: All reconciliation actions must use transactions to prevent partial updates.

---

## References

- [Freqtrade](https://www.freqtrade.io) - Open-source crypto trading bot
- [Hummingbot](https://hummingbot.org) - Market making bot framework
- [CCXT](https://github.com/ccxt/ccxt) - Unified crypto exchange API
- [FastAPI](https://fastapi.tiangolo.com) - Modern Python web framework

---

## Summary

The self-healing architecture transforms the trading system from a fragile linear pipeline into a resilient, self-healing organism that:

- ✅ Immediately detects execution failures via Verification Agent
- ✅ Continuously monitors system health to prevent degraded trading
- ✅ Automatically recovers from common failure scenarios
- ✅ Guarantees data integrity through periodic reconciliation
- ✅ Requires zero manual intervention for transient errors
- ✅ Maintains full audit trail of all state transitions and recovery actions
- ✅ Improves system resilience from reactive to proactive

**Result**: A production-ready automated trading infrastructure capable of operating 24/7 with minimal human oversight.
