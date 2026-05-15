# Resilience Platform - Quick Reference Card

## 🚀 Quick Start

```python
# Import components
from app.resilience import (
    ResilienceManager,
    SystemStateMachine, 
    RecoveryExecutor,
    FailureEvent,
    FailureSeverity,
    FailureDomain,
    SystemMode
)

# Initialize
state_machine = SystemStateMachine(notifier=telegram_notifier)
recovery_executor = RecoveryExecutor(notifier=telegram_notifier)
resilience_mgr = ResilienceManager(
    state_machine=state_machine,
    recovery_executor=recovery_executor,
    event_bus=event_bus,
    notifier=telegram_notifier
)

# Handle failure
await resilience_mgr.handle_failure(
    FailureEvent(
        source="api_watchdog",
        failure_type="high_latency",
        severity=FailureSeverity.WARNING,
        domain=FailureDomain.API,
        metadata={"latency_ms": 5500}
    )
)

# Check if trading allowed
if not resilience_mgr.current_mode.allows_trading():
    logger.warning("Trading blocked!")
```

---

## 📊 System Modes

| Mode         | Trading | New Entries | Exits | Use Case                    |
|--------------|---------|-------------|-------|-----------------------------|
| NORMAL       | ✅      | ✅          | ✅    | Full operation              |
| DEGRADED     | ✅      | ✅          | ✅    | High latency, caution       |
| SAFE_MODE    | ⚠️      | ❌          | ✅    | API issues, exits only      |
| RECOVERY     | ❌      | ❌          | ❌    | Active healing              |
| EMERGENCY    | ❌      | ❌          | ❌    | Critical failures           |
| SHUTDOWN     | ❌      | ❌          | ❌    | Graceful shutdown           |

---

## 🎯 Health Score Thresholds

| Score  | Mode         | Action                          |
|--------|--------------|---------------------------------|
| 90-100 | NORMAL       | Full trading                    |
| 70-89  | DEGRADED     | Reduce position sizes by 50%    |
| 50-69  | SAFE_MODE    | Block new entries               |
| 30-49  | RECOVERY     | Stop all trading, heal          |
| 0-29   | EMERGENCY    | Close positions, emergency stop |

**Composite Formula:**
```
score = (API × 0.35) + (WebSocket × 0.25) + (Execution × 0.20) + 
        (Memory × 0.10) + (Reconciliation × 0.10)
```

---

## 🔧 API Endpoints

```bash
# Get resilience status
GET /resilience/status

# Get state machine status
GET /resilience/state-machine

# Get health score breakdown
GET /resilience/health-score

# Get backpressure status
GET /resilience/backpressure

# Force reset to NORMAL (use with caution!)
POST /resilience/reset-to-normal?reason=Manual+override
```

---

## 🛡️ Key Protections

### 1. Cooldowns (prevent spam)
```python
# Default cooldowns
api_reconnect: 60s
reconciliation: 120s
system_restart: 3600s (max 3/hour)
position_close: 30s
circuit_breaker_reset: 300s
state_reset: 600s
```

### 2. Rate Limiting
```python
# Max recoveries per hour per action type
max_per_hour = 3

if would_exceed_rate_limit(action, max_per_hour=3):
    escalate_to_emergency()
```

### 3. Idempotency
```python
# Actions tracked for 5 minutes
action_key = f"{plan_id}_{action_name}"
if is_already_executed(action_key):
    skip_action()
```

### 4. Backpressure
```python
# Trade frequency multiplier based on load
pressure > 0.8 → multiplier = 0.25 (75% reduction)
pressure > 0.6 → multiplier = 0.50 (50% reduction)
pressure > 0.4 → multiplier = 0.75 (25% reduction)
pressure < 0.4 → multiplier = 1.00 (normal)
```

---

## 🚨 Failure Severity Levels

| Severity   | Color | Response Time | Example                      |
|------------|-------|---------------|------------------------------|
| INFO       | 🔵    | Log only      | Dashboard refresh failed     |
| WARNING    | 🟡    | < 5 min       | API latency spike            |
| CRITICAL   | 🟠    | < 1 min       | WebSocket disconnected       |
| EMERGENCY  | 🔴    | Immediate     | Position mismatch detected   |

---

## 📝 Recovery Plan Structure

```python
RecoveryPlan(
    plan_id="abc123",
    failure_event=failure_event,
    priority=3,  # 1=highest, 10=lowest
    steps=[
        RecoveryStep(
            action_name="pause_new_entries",
            description="Block new trade entries",
            timeout_seconds=5,
            rollback_action=None,
            idempotent=True
        ),
        RecoveryStep(
            action_name="attempt_api_reconnect",
            description="Reconnect to exchange",
            timeout_seconds=30,
            rollback_action=None,
            idempotent=True
        ),
        RecoveryStep(
            action_name="verify_connectivity",
            description="Test API endpoint",
            timeout_seconds=10,
            rollback_action=None,
            idempotent=False
        )
    ]
)
```

---

## 🔍 Debugging Commands

```python
# Check current status
status = resilience_mgr.get_status()
print(f"Mode: {status['current_mode']}")
print(f"Health: {status['health_score']['composite']}")

# Check state machine
sm_status = state_machine.get_status()
print(f"Can trade: {sm_status['can_trade']}")
print(f"Recent transitions: {sm_status['recent_transitions']}")

# Simulate recovery plan
plan = RecoveryPlan(...)
simulation = plan.simulate()
print(f"Estimated downtime: {simulation['estimated_downtime']}s")
print(f"Risk level: {simulation['risk_level']}")

# Check incident correlation
incident_id = correlation_engine.correlate(failure_event)
summary = correlation_engine.get_incident_summary(incident_id)
print(f"Incident {incident_id}: {summary['event_count']} events")
```

---

## ⚠️ Common Pitfalls

### ❌ DON'T: Let watchdogs take direct actions
```python
# BAD
async def trigger_emergency(self):
    await close_all_positions()  # Direct action!
```

### ✅ DO: Emit events to ResilienceManager
```python
# GOOD
async def trigger_emergency(self):
    await resilience_mgr.handle_failure(
        FailureEvent(
            source="watchdog",
            failure_type="critical_issue",
            severity=FailureSeverity.EMERGENCY,
            domain=FailureDomain.API
        )
    )
```

---

### ❌ DON'T: Skip state checks before trading
```python
# BAD
async def execute_trade(self):
    await place_order()  # No state check!
```

### ✅ DO: Check system mode first
```python
# GOOD
async def execute_trade(self):
    if not resilience_mgr.current_mode.allows_new_entries():
        return {'status': 'blocked'}
    await place_order()
```

---

### ❌ DON'T: Ignore cooldowns
```python
# BAD
while True:
    await reconnect_api()  # Spam!
```

### ✅ DO: Respect cooldowns
```python
# GOOD
if cooldown_mgr.should_execute('api_reconnect'):
    await reconnect_api()
    cooldown_mgr.record_execution('api_reconnect')
```

---

## 📈 Monitoring Alerts

### Set up alerts for:

```python
# Health score dropping
if health_score.composite < 70:
    send_alert("Health score degraded")

# Frequent state transitions
if len(state_history) > 10 in last_hour:
    send_alert("Excessive state transitions")

# Recovery failures
if recovery_result.success == False:
    send_alert("Recovery plan failed")

# Cooldown violations (indicates bug)
if cooldown_violations > 0:
    send_alert("Cooldown violation detected")

# Emergency mode entered
if current_mode == SystemMode.EMERGENCY:
    send_urgent_alert("EMERGENCY MODE ACTIVATED")
```

---

## 🎓 Best Practices

1. **Always check state before acting**
   ```python
   if state_machine.can_trade():
       execute_trade()
   ```

2. **Use appropriate severity levels**
   ```python
   WARNING for degraded performance
   CRITICAL for component failures
   EMERGENCY for system-threatening issues
   ```

3. **Make recovery actions idempotent**
   ```python
   close_positions_if_not_already_closed()  # Safe
   close_all_positions()                     # Dangerous
   ```

4. **Log everything for audit trail**
   ```python
   logger.info(f"Executing recovery step: {step.action_name}")
   ```

5. **Test recovery plans in simulation mode first**
   ```python
   simulation = plan.simulate()
   if simulation['risk_level'] == 'high':
       require_manual_approval()
   ```

---

## 🔗 Related Documentation

- Full architecture: `RESILIENCE_PLATFORM_UPGRADE.md`
- Integration guide: `INTEGRATION_GUIDE_RESILIENCE_PLATFORM.py`
- Executive summary: `RESILIENCE_PLATFORM_EXECUTIVE_SUMMARY.md`

---

## 💡 Pro Tips

1. **Tune thresholds gradually** - Start conservative, adjust based on real data
2. **Monitor health score trends** - Look for gradual degradation patterns
3. **Review incident correlations weekly** - Identify recurring root causes
4. **Test emergency procedures monthly** - Ensure team knows how to respond
5. **Keep legacy fallbacks for first week** - Safety net during transition

---

**Remember:** The ResilienceManager is your SINGLE SOURCE OF TRUTH. All failures flow through it. Never bypass it with direct recovery actions! 🛡️
