"""
Execution module exports.

Heavy service classes are loaded lazily so lightweight utilities (for example
state machines and the self-healing engine) can be imported in environments
where optional runtime dependencies are not installed yet.
"""
from app.execution.states import ExecutionState, is_valid_transition

__all__ = [
    "LiveTradingService",
    "ExecutionAgent",
    "ExecutionState",
    "SelfHealingExecutionEngine",
    "HealingDecision",
    "is_valid_transition",
]


def __getattr__(name):
    if name == "LiveTradingService":
        from app.execution.trading_service import LiveTradingService

        return LiveTradingService
    if name == "ExecutionAgent":
        from app.execution.execution_agent import ExecutionAgent

        return ExecutionAgent
    if name in {"SelfHealingExecutionEngine", "HealingDecision"}:
        from app.execution.self_healing_engine import HealingDecision, SelfHealingExecutionEngine

        return {
            "SelfHealingExecutionEngine": SelfHealingExecutionEngine,
            "HealingDecision": HealingDecision,
        }[name]
    raise AttributeError(f"module 'app.execution' has no attribute {name!r}")
