"""
Resilience Platform - Coordinated failure management and recovery orchestration.

This package transforms the auto-trade system from a reactive watchdog framework
into a production-grade resilience platform with centralized orchestration,
deterministic recovery, and state-aware healing.

Key Components:
- ResilienceManager: Central orchestration hub
- SystemStateMachine: Global operational state management
- RecoveryExecutor: Idempotent recovery action execution
- ResiliencePlatform: Core data structures and utilities

Usage:
    from app.resilience import ResilienceManager, SystemStateMachine, RecoveryExecutor
    
    # Initialize components
    state_machine = SystemStateMachine(notifier=telegram_notifier)
    executor = RecoveryExecutor(cooldown_manager=cooldown_mgr, notifier=telegram_notifier)
    resilience_mgr = ResilienceManager(
        state_machine=state_machine,
        recovery_executor=executor,
        event_bus=event_bus,
        notifier=telegram_notifier
    )
    
    # Handle failures
    from app.resilience import FailureEvent, FailureSeverity, FailureDomain
    
    await resilience_mgr.handle_failure(
        FailureEvent(
            source="api_watchdog",
            failure_type="high_latency",
            severity=FailureSeverity.WARNING,
            domain=FailureDomain.API,
            metadata={"latency_ms": 5500}
        )
    )
"""

from app.resilience.resilience_platform import (
    SystemMode,
    HealthScore,
    FailureSeverity,
    FailureDomain,
    FailureEvent,
    RecoveryStep,
    RecoveryPlan,
    HealingCooldownManager,
    FailureCorrelationEngine,
    BackpressureController,
)

from app.resilience.state_machine import SystemStateMachine, StateTransitionError
from app.resilience.recovery_executor import RecoveryExecutor
from app.resilience.resilience_manager import ResilienceManager

__all__ = [
    # Core orchestration
    'ResilienceManager',
    'SystemStateMachine',
    'RecoveryExecutor',
    
    # Data structures
    'SystemMode',
    'HealthScore',
    'FailureSeverity',
    'FailureDomain',
    'FailureEvent',
    'RecoveryStep',
    'RecoveryPlan',
    
    # Utilities
    'HealingCooldownManager',
    'FailureCorrelationEngine',
    'BackpressureController',
    
    # Exceptions
    'StateTransitionError',
]
