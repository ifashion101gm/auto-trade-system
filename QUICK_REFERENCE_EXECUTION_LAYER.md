# Quick Reference: Execution Layer Components

## New Files Created

```
app/
├── exchange/
│   ├── base_exchange.py          ✅ Enhanced with CCXT-standard methods
│   └── exchange_adapter.py       ✅ NEW - Circuit breaker + rate limiting
├── events/
│   ├── event_bus.py              ✅ Upgraded with priority queue
│   └── event_store.py            ✅ NEW - Event persistence
├── services/
│   ├── execution_states.py       ✅ NEW - State machine enum
│   └── position_monitor.py       ✅ NEW - SL/TP monitoring
└── config.py                     ✅ Added new config options
```

---

## Component Quick Start

### 1. ExchangeAdapter (Reliability Layer)

```python
from app.infra.mexc_client import MEXCClient
from app.exchange.exchange_adapter import ExchangeAdapter

# Wrap any BaseExchange implementation
client = MEXCClient(api_key="...", api_secret="...")
adapter = ExchangeAdapter(
    exchange=client,
    max_retries=3,
    circuit_breaker_threshold=5
)

# All calls now have automatic retry + circuit breaker
try:
    order = await adapter.create_market_order("XAUT/USDT", "buy", 0.01)
except Exception as e:
    print(f"Failed after retries: {e}")

# Check metrics
metrics = adapter.get_metrics()
print(f"Error rate: {metrics['error_rate_pct']}%")
print(f"Circuit breaker: {metrics['circuit_breaker_state']}")
```

### 2. EventBus (Priority Processing)

```python
from app.events.event_bus import event_bus

# Start background processing (do this once at startup)
await event_bus.start_processing()

# Subscribe to events with priority
async def handle_order_filled(event):
    print(f"Order filled: {event['payload']}")

event_bus.subscribe('ORDER_FILLED', handle_order_filled, priority=2)

# Publish events with priority
await event_bus.publish(
    'ORDER_FILLED',
    {'order_id': '123', 'price': 2000},
    priority=2  # Lower = higher priority
)

# Get metrics
metrics = event_bus.get_metrics()
print(f"Events processed: {metrics['events_processed']}")
print(f"Dead letter count: {metrics['dead_letter_count']}")

# Stop processing (on shutdown)
await event_bus.stop_processing()
```

### 3. EventStore (Persistence)

```python
from app.events.event_store import event_store
from sqlalchemy.ext.asyncio import AsyncSession

# Persist critical events (subscribe in initialization)
async def persist_critical_events(event):
    await event_store.persist_event(event, db_session)

event_bus.subscribe('ORDER_FILLED', persist_critical_events)

# Retrieve events for debugging
events = await event_store.get_events_for_trade(
    trade_id='abc123',
    db_session=db_session
)

# Replay events to reconstruct state
timeline = await event_store.replay_events_for_trade(
    trade_id='abc123',
    db_session=db_session
)
```

### 4. PositionMonitor (SL/TP Tracking)

```python
from app.services.position_monitor import PositionMonitor

# Initialize monitor
monitor = PositionMonitor(
    event_bus=event_bus,
    exchange_manager=exchange_manager,
    check_interval=5.0  # Check every 5 seconds
)

# Start monitoring after order execution
await monitor.start_monitoring(
    trade_id='abc123',
    symbol='XAUT/USDT',
    side='LONG',
    entry_price=2000.0,
    quantity=0.01,
    stop_loss=1950.0,
    take_profit=2100.0,
    db_session=db_session
)

# Monitor runs in background until SL/TP hit
# Check how many positions being monitored
count = monitor.get_monitored_count()

# Get metrics
metrics = monitor.get_metrics()
print(f"Monitored positions: {metrics['monitored_positions']}")

# Stop monitoring manually (if needed)
await monitor.stop_monitoring('abc123')
```

### 5. ExecutionState (State Machine)

```python
from app.services.execution_states import ExecutionState, is_valid_transition

# Track current state
current_state = ExecutionState.IDLE

# Check if transition is valid
if is_valid_transition(current_state, ExecutionState.FETCHING_DATA):
    current_state = ExecutionState.FETCHING_DATA
    print(f"Transitioned to {current_state}")
else:
    print(f"Invalid transition from {current_state}")

# Get valid next states
next_states = get_valid_next_states(ExecutionState.EXECUTING)
print(f"Can transition to: {next_states}")
# Output: [ExecutionState.MONITORING, ExecutionState.ERROR]
```

---

## Configuration (.env)

```bash
# Event Bus
EVENT_BUS_MAX_QUEUE_SIZE=10000

# WebSocket
WEBSOCKET_HEARTBEAT_INTERVAL=30
WEBSOCKET_HEARTBEAT_TIMEOUT=45

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60

# Rate Limiter
RATE_LIMIT_MAX_CALLS=10
RATE_LIMIT_TIME_WINDOW=1.0

# Retry
MAX_RETRIES=3
BASE_RETRY_DELAY=1.0
MAX_RETRY_DELAY=30.0

# Position Monitor
POSITION_CHECK_INTERVAL=5.0

# Reconciliation
RECONCILIATION_INTERVAL_SECONDS=120
```

---

## Integration Example: LiveTradingService

Here's how to integrate all components into your trading service:

```python
from app.exchange.exchange_adapter import ExchangeAdapter
from app.services.position_monitor import PositionMonitor
from app.services.execution_states import ExecutionState
from app.events.event_bus import event_bus
from app.events.event_store import event_store

class LiveTradingService:
    def __init__(self):
        # Initialize exchange with adapter
        client = MEXCClient(...)
        self.exchange = ExchangeAdapter(client)
        
        # Initialize position monitor
        self.position_monitor = PositionMonitor(
            event_bus=event_bus,
            exchange_manager=self.exchange
        )
        
        # Track state
        self.current_state = ExecutionState.IDLE
    
    async def execute_trading_cycle(self, symbol, user_id, db_session):
        """Execute one trading cycle with state tracking."""
        try:
            # Transition to FETCHING_DATA
            self._transition_to(ExecutionState.FETCHING_DATA)
            
            # Fetch market data (with automatic retry)
            ticker = await self.exchange.fetch_ticker(symbol)
            
            # ... AI analysis, validation, etc ...
            
            # Transition to EXECUTING
            self._transition_to(ExecutionState.EXECUTING)
            
            # Execute order (with circuit breaker protection)
            order = await self.exchange.create_market_order(
                symbol=symbol,
                side='buy',
                amount=0.01
            )
            
            # Transition to MONITORING
            self._transition_to(ExecutionState.MONITORING)
            
            # Start position monitoring
            await self.position_monitor.start_monitoring(
                trade_id=trade_record.id,
                symbol=symbol,
                side='LONG',
                entry_price=order['price'],
                quantity=order['amount'],
                stop_loss=stop_loss_price,
                take_profit=take_profit_price,
                db_session=db_session
            )
            
            # Transition back to IDLE
            self._transition_to(ExecutionState.IDLE)
            
        except Exception as e:
            # Transition to ERROR
            self._transition_to(ExecutionState.ERROR)
            logger.error(f"Trading cycle failed: {e}")
            raise
    
    def _transition_to(self, new_state):
        """Validate and perform state transition."""
        old_state = self.current_state
        
        if not is_valid_transition(old_state, new_state):
            raise ValueError(
                f"Invalid transition: {old_state} -> {new_state}"
            )
        
        self.current_state = new_state
        logger.info(f"State: {old_state.value} -> {new_state.value}")
        
        # Publish state change event
        asyncio.create_task(event_bus.publish(
            'STATE_CHANGED',
            {
                'old_state': old_state.value,
                'new_state': new_state.value
            },
            priority=15
        ))
```

---

## Metrics Dashboard Example

Create a simple endpoint to monitor system health:

```python
@app.get("/metrics")
async def get_system_metrics():
    return {
        "exchange_adapter": adapter.get_metrics(),
        "event_bus": event_bus.get_metrics(),
        "websocket": websocket_manager.get_metrics(),
        "position_monitor": position_monitor.get_metrics(),
        "current_state": trading_service.current_state.value
    }
```

**Sample Output:**
```json
{
  "exchange_adapter": {
    "request_count": 1523,
    "error_count": 12,
    "error_rate_pct": 0.79,
    "avg_latency_ms": 245.3,
    "circuit_breaker_state": "CLOSED"
  },
  "event_bus": {
    "events_published": 5432,
    "events_processed": 5420,
    "events_failed": 2,
    "queue_size": 0,
    "dead_letter_count": 2
  },
  "websocket": {
    "connected": true,
    "subscriptions_count": 3,
    "avg_message_latency_ms": 45.2,
    "last_heartbeat_age_s": 12.5
  },
  "position_monitor": {
    "monitored_positions": 2,
    "active_tasks": 2
  },
  "current_state": "MONITORING"
}
```

---

## Troubleshooting

### Circuit Breaker Open

**Symptom:** All requests fail immediately with `CircuitBreakerError`

**Solution:**
1. Check exchange status (might be down)
2. Wait for recovery timeout (default: 60s)
3. Circuit breaker will automatically transition to HALF_OPEN and test
4. If test succeeds, transitions back to CLOSED

```python
# Check circuit breaker state
metrics = adapter.get_metrics()
if metrics['circuit_breaker_state'] == 'OPEN':
    print("Waiting for recovery...")
    await asyncio.sleep(60)
```

### Event Queue Full

**Symptom:** Events being dropped, dead letter queue growing

**Solution:**
1. Increase queue size: `EVENT_BUS_MAX_QUEUE_SIZE=20000`
2. Check for slow event handlers (add logging)
3. Reduce event frequency (batch updates)

```python
# Check queue health
metrics = event_bus.get_metrics()
if metrics['queue_size'] > 8000:
    print("Warning: Event queue nearly full!")
```

### WebSocket Disconnected

**Symptom:** No real-time updates, falling back to REST

**Solution:**
1. Check WebSocket metrics
2. Verify network connectivity
3. Auto-reconnect should happen within 45s

```python
# Check WebSocket health
ws_metrics = websocket_manager.get_metrics()
if not ws_metrics['connected']:
    print("WebSocket disconnected, attempting reconnect...")
```

### Position Not Closing on SL/TP

**Symptom:** Price hits SL/TP but position stays open

**Solution:**
1. Check position monitor logs
2. Verify SL/TP prices are correct
3. Check if monitoring task is running

```python
# Check monitor status
metrics = position_monitor.get_metrics()
print(f"Monitoring {metrics['monitored_positions']} positions")

# Manually check a position
ticker = await exchange.fetch_ticker('XAUT/USDT')
print(f"Current price: {ticker['last_price']}")
```

---

## Best Practices

1. **Always use ExchangeAdapter** instead of raw clients for production
2. **Start EventBus early** in application lifecycle
3. **Monitor metrics regularly** to catch issues before they escalate
4. **Use state machine** to track execution flow (even if not fully enforced yet)
5. **Persist critical events** for post-mortem debugging
6. **Set appropriate timeouts** based on your exchange's typical latency
7. **Test circuit breaker** by simulating exchange failures
8. **Log state transitions** to understand execution flow

---

## Further Reading

- Full implementation details: `EXECUTION_LAYER_UPGRADE_SUMMARY.md`
- Architecture plan: `.lingma/plans/Execution_Layer_Architecture_Upgrade_*.md`
- Freqtrade docs: https://www.freqtrade.io/
- Hummingbot docs: https://hummingbot.org/
- CCXT docs: https://docs.ccxt.com/
