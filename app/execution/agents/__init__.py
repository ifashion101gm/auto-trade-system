"""
Self-Healing Trading Agents Package.

Provides specialized agents for resilient trading lifecycle:
- SignalAgent: Trade signal generation with risk validation
- ExecutionAgent: Order placement with retry logic
- VerificationAgent: Post-execution state verification
- MonitoringAgent: System health tracking
- RecoveryAgent: Automatic failure recovery
- ReconciliationAgent: Exchange-DB consistency checks
"""

from app.execution.agents.base_agent import BaseAgent

def __getattr__(name):
    """Lazy imports to avoid circular dependencies."""
    if name == 'SignalAgent':
        from app.execution.agents.signal_agent import SignalAgent
        return SignalAgent
    elif name == 'ExecutionAgent':
        from app.execution.agents.execution_agent import ExecutionAgent
        return ExecutionAgent
    elif name == 'VerificationAgent':
        from app.execution.agents.verification_agent import VerificationAgent
        return VerificationAgent
    elif name == 'MonitoringAgent':
        from app.execution.agents.monitoring_agent import MonitoringAgent
        return MonitoringAgent
    elif name == 'RecoveryAgent':
        from app.execution.agents.recovery_agent import RecoveryAgent
        return RecoveryAgent
    elif name == 'ReconciliationAgent':
        from app.execution.agents.reconciliation_agent import ReconciliationAgent
        return ReconciliationAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'BaseAgent',
    'SignalAgent',
    'ExecutionAgent',
    'VerificationAgent',
    'MonitoringAgent',
    'RecoveryAgent',
    'ReconciliationAgent'
]
