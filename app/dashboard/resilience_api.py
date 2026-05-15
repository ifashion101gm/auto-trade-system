"""
Resilience Platform API Endpoints for Dashboard Observability.

Provides REST API access to resilience platform status, health scores,
state machine transitions, and backpressure metrics.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resilience", tags=["resilience"])


@router.get("/status")
async def get_resilience_status() -> Dict[str, Any]:
    """
    Get comprehensive resilience platform status.
    
    Returns:
        Dictionary containing current mode, health score, active incidents, etc.
    """
    from app.main import state
    
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(
            status_code=503,
            detail="Resilience platform not initialized"
        )
    
    return state.resilience_manager.get_status()


@router.get("/state-machine")
async def get_state_machine_status() -> Dict[str, Any]:
    """
    Get state machine status and transition history.
    
    Returns:
        Dictionary with current state, can_trade flag, recent transitions
    """
    from app.main import state
    
    if not hasattr(state, 'state_machine') or not state.state_machine:
        raise HTTPException(
            status_code=503,
            detail="State machine not initialized"
        )
    
    return state.state_machine.get_status()


@router.get("/health-score")
async def get_health_score() -> Dict[str, Any]:
    """
    Get detailed health score breakdown by component.
    
    Returns:
        Dictionary with composite score and individual domain scores
    """
    from app.main import state
    
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(
            status_code=503,
            detail="Resilience platform not initialized"
        )
    
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
        'current_mode': rm.current_mode.value,
        'weights': rm.health_score.WEIGHTS
    }


@router.post("/reset-to-normal")
async def reset_to_normal(reason: str = "Manual override") -> Dict[str, Any]:
    """
    Force reset system to NORMAL mode.
    
    WARNING: Use only when you're sure the system is healthy.
    This bypasses normal transition validation.
    
    Args:
        reason: Reason for manual reset (logged for audit)
        
    Returns:
        Success message with reset details
    """
    from app.main import state
    
    if not hasattr(state, 'state_machine') or not state.state_machine:
        raise HTTPException(
            status_code=503,
            detail="State machine not initialized"
        )
    
    logger.warning(f"⚠️ Manual reset to NORMAL requested: {reason}")
    state.state_machine.reset_to_normal(reason)
    
    return {
        'status': 'success',
        'message': f'System reset to NORMAL mode',
        'reason': reason,
        'timestamp': __import__('datetime').datetime.utcnow().isoformat()
    }


@router.get("/backpressure")
async def get_backpressure_status() -> Dict[str, Any]:
    """
    Get current backpressure settings and trade frequency multiplier.
    
    Returns:
        Dictionary with current backpressure parameters
    """
    from app.main import state
    
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(
            status_code=503,
            detail="Resilience platform not initialized"
        )
    
    rm = state.resilience_manager
    return {
        'trade_frequency_multiplier': rm.backpressure_controller.trade_frequency_multiplier,
        'current_delay_ms': rm.backpressure_controller.current_delay_ms,
        'should_delay': rm.backpressure_controller.should_delay_execution(),
        'backpressure_level': rm.backpressure_controller.calculate_backpressure()['pressure_level']
    }


@router.get("/incidents")
async def get_active_incidents() -> Dict[str, Any]:
    """
    Get list of active incidents being tracked by correlation engine.
    
    Returns:
        Dictionary with incident summaries
    """
    from app.main import state
    
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(
            status_code=503,
            detail="Resilience platform not initialized"
        )
    
    rm = state.resilience_manager
    incidents = rm.correlation_engine.get_all_incidents()
    
    return {
        'active_incidents': len(incidents),
        'incidents': {
            incident_id: {
                'event_count': len(events),
                'first_event': events[0].timestamp.isoformat() if events else None,
                'last_event': events[-1].timestamp.isoformat() if events else None,
                'domains': list(set(e.domain.value for e in events)),
                'severities': list(set(e.severity.value for e in events))
            }
            for incident_id, events in incidents.items()
        }
    }


@router.get("/cooldowns")
async def get_cooldown_status() -> Dict[str, Any]:
    """
    Get current cooldown status for recovery actions.
    
    Returns:
        Dictionary showing which actions are in cooldown
    """
    from app.main import state
    
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(
            status_code=503,
            detail="Resilience platform not initialized"
        )
    
    rm = state.resilience_manager
    cooldowns = rm.cooldown_manager.get_active_cooldowns()
    
    return {
        'active_cooldowns': len(cooldowns),
        'cooldowns': {
            action: {
                'remaining_seconds': max(0, int(expiry - __import__('time').time())),
                'expired': expiry < __import__('time').time()
            }
            for action, expiry in cooldowns.items()
        }
    }


@router.get("/recovery-history")
async def get_recovery_history(limit: int = 20) -> Dict[str, Any]:
    """
    Get recent recovery plan execution history.
    
    Args:
        limit: Maximum number of recent executions to return
        
    Returns:
        Dictionary with recovery execution summaries
    """
    from app.main import state
    
    if not hasattr(state, 'recovery_executor') or not state.recovery_executor:
        raise HTTPException(
            status_code=503,
            detail="Recovery executor not initialized"
        )
    
    executor = state.recovery_executor
    history = executor.get_execution_history(limit=limit)
    
    return {
        'total_executions': len(history),
        'recent_executions': [
            {
                'plan_id': exec_record['plan_id'],
                'failure_type': exec_record.get('failure_type', 'unknown'),
                'success': exec_record['success'],
                'steps_completed': exec_record.get('steps_completed', 0),
                'duration_ms': exec_record.get('duration_ms', 0),
                'timestamp': exec_record['timestamp'].isoformat() if hasattr(exec_record['timestamp'], 'isoformat') else str(exec_record['timestamp'])
            }
            for exec_record in history
        ]
    }


@router.post("/simulate-failure")
async def simulate_failure(
    failure_type: str = "api_timeout",
    severity: str = "WARNING",
    domain: str = "API"
) -> Dict[str, Any]:
    """
    Simulate a failure event for testing purposes.
    
    WARNING: Only use in staging/test environments!
    
    Args:
        failure_type: Type of failure to simulate (e.g., "api_timeout", "high_latency")
        severity: Severity level (INFO, WARNING, CRITICAL, EMERGENCY)
        domain: Failure domain (API, WEBSOCKET, EXECUTION, MEMORY, RECONCILIATION)
        
    Returns:
        Result of failure handling
    """
    from app.main import state
    from app.resilience import FailureEvent, FailureSeverity, FailureDomain
    
    if not hasattr(state, 'resilience_manager') or not state.resilience_manager:
        raise HTTPException(
            status_code=503,
            detail="Resilience platform not initialized"
        )
    
    # Map string values to enums
    severity_map = {
        'INFO': FailureSeverity.INFO,
        'WARNING': FailureSeverity.WARNING,
        'CRITICAL': FailureSeverity.CRITICAL,
        'EMERGENCY': FailureSeverity.EMERGENCY
    }
    
    domain_map = {
        'API': FailureDomain.API,
        'WEBSOCKET': FailureDomain.WEBSOCKET,
        'EXECUTION': FailureDomain.EXECUTION,
        'MEMORY': FailureDomain.MEMORY,
        'RECONCILIATION': FailureDomain.RECONCILIATION
    }
    
    severity_enum = severity_map.get(severity.upper(), FailureSeverity.WARNING)
    domain_enum = domain_map.get(domain.upper(), FailureDomain.API)
    
    # Create and handle failure event
    failure_event = FailureEvent(
        source="dashboard_simulation",
        failure_type=failure_type,
        severity=severity_enum,
        domain=domain_enum,
        metadata={'simulated': True}
    )
    
    await state.resilience_manager.handle_failure(failure_event)
    
    return {
        'status': 'simulated',
        'failure_type': failure_type,
        'severity': severity,
        'domain': domain,
        'new_mode': state.resilience_manager.current_mode.value,
        'new_health_score': round(state.resilience_manager.health_score.composite_score, 1)
    }
