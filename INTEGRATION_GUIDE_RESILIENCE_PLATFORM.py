"""
Quick Integration Guide for Resilience Platform

This file shows exactly how to integrate the new resilience platform into your existing system.
"""

# ============================================================================
# STEP 1: Update main.py - Add Resilience Platform Initialization
# ============================================================================

# In app/main.py, find the init_services() function and add:

"""
from app.resilience import ResilienceManager, SystemStateMachine, RecoveryExecutor

async def init_services():
    # ... existing initialization code ...
    
    # NEW: Initialize resilience platform
    logger.info("🛡️ Initializing resilience platform...")
    
    # 1. Create state machine
    state.state_machine = SystemStateMachine(
        notifier=state.telegram_agent,  # Use existing Telegram notifier
        event_bus=event_bus
    )
    
    # 2. Create recovery executor
    state.recovery_executor = RecoveryExecutor(
        cooldown_manager=None,  # Created internally
        notifier=state.telegram_agent
    )
    
    # 3. Create resilience manager (central hub)
    state.resilience_manager = ResilienceManager(
        state_machine=state.state_machine,
        recovery_executor=state.recovery_executor,
        event_bus=event_bus,
        notifier=state.telegram_agent
    )
    
    # 4. Update watchdog orchestrator to use resilience manager
    state.watchdog_orchestrator = WatchdogOrchestrator(
        exchange_manager=exchange_manager,
        db_session_factory=get_session,
        resilience_manager=state.resilience_manager,  # PASS THIS!
        api_check_interval=getattr(settings, 'API_WATCHDOG_CHECK_INTERVAL_SEC', 30),
        db_check_interval=getattr(settings, 'DB_WATCHDOG_CHECK_INTERVAL_SEC', 60),
        memory_check_interval=getattr(settings, 'MEMORY_WATCHDOG_CHECK_INTERVAL_SEC', 120),
        queue_check_interval=getattr(settings, 'QUEUE_WATCHDOG_CHECK_INTERVAL_SEC', 60)
    )
    
    logger.info("✅ Resilience platform initialized")
    
    # ... rest of initialization ...
"""


# ============================================================================
# STEP 2: Add AppState Fields
# ============================================================================

# In app/main.py, update the AppState class:

"""
class AppState:
    def __init__(self):
        # ... existing fields ...
        
        # NEW: Resilience platform components
        self.resilience_manager = None
        self.state_machine = None
        self.recovery_executor = None
"""


# ============================================================================
# STEP 3: Trading Service State Checks
# ============================================================================

# In app/execution/trading_service.py, add state checks before executing trades:

"""
from app.main import state
from app.resilience import SystemMode

class LiveTradingService:
    async def _execute_trade(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        # NEW: Check if trading is allowed by resilience platform
        if hasattr(state, 'resilience_manager') and state.resilience_manager:
            current_mode = state.resilience_manager.current_mode
            
            # Block all trading in certain modes
            if current_mode.blocks_all_trading():
                logger.warning(f"🚫 Trading blocked in {current_mode.value} mode")
                return {
                    'status': 'blocked',
                    'reason': f'System in {current_mode.value} mode',
                    'mode': current_mode.value
                }
            
            # Block new entries in safe mode
            if not current_mode.allows_new_entries():
                logger.warning(f"⚠️ New entries blocked in {current_mode.value} mode")
                return {
                    'status': 'blocked',
                    'reason': 'No new entries allowed in current mode',
                    'mode': current_mode.value
                }
            
            # Log degraded mode warnings
            if current_mode == SystemMode.DEGRADED:
                logger.warning(f"⚠️ Trading in DEGRADED mode - exercising caution")
        
        # ... continue with existing trade execution logic ...
"""


# ============================================================================
# STEP 4: Create Dashboard API Endpoints
# ============================================================================

# Create new file: app/dashboard/resilience_api.py

"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.main import state

router = APIRouter(prefix="/resilience", tags=["resilience"])

@router.get("/status")
async def get_resilience_status() -> Dict[str, Any]:
    """Get comprehensive resilience platform status."""
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(status_code=503, detail="Resilience platform not initialized")
    
    return state.resilience_manager.get_status()

@router.get("/state-machine")
async def get_state_machine_status() -> Dict[str, Any]:
    """Get state machine status and history."""
    if not hasattr(state, 'state_machine') or not state.state_machine:
        raise HTTPException(status_code=503, detail="State machine not initialized")
    
    return state.state_machine.get_status()

@router.get("/health-score")
async def get_health_score() -> Dict[str, Any]:
    """Get detailed health score breakdown."""
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(status_code=503, detail="Resilience platform not initialized")
    
    rm = state.resilience_manager
    return {
        'composite_score': round(rm.health_score.composite_score, 1),
        'components': {
            'api': round(rm.health_score.api_health, 1),
            'websocket': round(rm.health_score.websocket_health, 1),
            'execution': round(rm.health_score.execution_health, 1),
            'memory': round(rm.health_score.memory_health, 1),
            'reconciliation': round(rm.health_score.reconciliation_health, 1),
        },
        'current_mode': rm.current_mode.value
    }

@router.post("/reset-to-normal")
async def reset_to_normal(reason: str = "Manual override") -> Dict[str, Any]:
    """
    Force reset system to NORMAL mode.
    
    WARNING: Use only when you're sure the system is healthy.
    This bypasses normal transition validation.
    """
    if not hasattr(state, 'state_machine') or not state.state_machine:
        raise HTTPException(status_code=503, detail="State machine not initialized")
    
    state.state_machine.reset_to_normal(reason)
    
    return {
        'status': 'success',
        'message': f'System reset to NORMAL mode',
        'reason': reason
    }

@router.get("/backpressure")
async def get_backpressure_status() -> Dict[str, Any]:
    """Get current backpressure settings."""
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(status_code=503, detail="Resilience platform not initialized")
    
    rm = state.resilience_manager
    return {
        'trade_frequency_multiplier': rm.backpressure_controller.trade_frequency_multiplier,
        'current_delay_ms': rm.backpressure_controller.current_delay_ms,
        'should_delay': rm.backpressure_controller.should_delay_execution()
    }
"""

# Then register in app/main.py:
"""
from app.dashboard import resilience_router

app.include_router(resilience_router.router)
"""


# ============================================================================
# STEP 5: Testing the Integration
# ============================================================================

# Test script to verify everything works:

"""
import asyncio
from app.resilience import FailureEvent, FailureSeverity, FailureDomain

async def test_resilience_platform():
    # Simulate a failure
    failure = FailureEvent(
        source="test",
        failure_type="api_timeout",
        severity=FailureSeverity.WARNING,
        domain=FailureDomain.API,
        metadata={"test": True}
    )
    
    # Handle it through resilience manager
    await state.resilience_manager.handle_failure(failure)
    
    # Check status
    status = state.resilience_manager.get_status()
    print(f"Current mode: {status['current_mode']}")
    print(f"Health score: {status['health_score']['composite']}")
    
    # Verify state machine
    sm_status = state.state_machine.get_status()
    print(f"Can trade: {sm_status['can_trade']}")
    print(f"Recent transitions: {len(sm_status['recent_transitions'])}")

# Run test
# asyncio.run(test_resilience_platform())
"""


# ============================================================================
# STEP 6: Monitoring & Alerts
# ============================================================================

# Add to your monitoring dashboard:

"""
# Prometheus metrics (add to app/monitoring/prometheus_metrics.py):

self.resilience_health_score = Gauge(
    'resilience_health_score',
    'Composite health score (0-100)',
    registry=self.registry
)

self.resilience_system_mode = Gauge(
    'resilience_system_mode',
    'Current system mode (encoded as number)',
    registry=self.registry
)

# Update in ResilienceManager._update_health_score():
metrics.resilience_health_score.set(self.health_score.composite_score)
metrics.resilience_system_mode.set(list(SystemMode).index(self.current_mode))
"""


# ============================================================================
# Verification Checklist
# ============================================================================

"""
After integration, verify:

✅ ResilienceManager is initialized in main.py
✅ WatchdogOrchestrator receives resilience_manager parameter
✅ Trading service checks system mode before executing trades
✅ Dashboard endpoints return correct data
✅ Health scores update when failures occur
✅ State transitions are logged
✅ No duplicate recovery actions occur
✅ Cooldowns prevent spam
✅ System blocks trading in EMERGENCY mode

Test scenarios:
1. Simulate API failure → Verify ResilienceManager handles it
2. Trigger multiple failures → Verify correlation works
3. Enter EMERGENCY mode → Verify trading is blocked
4. Reset to NORMAL → Verify system recovers
5. Check dashboard → Verify all endpoints work
"""


print("Integration guide loaded. Follow steps 1-6 above.")
