"""
Execution state machine for trading cycle.
Inspired by Freqtrade's state-aware execution loop.

Defines explicit states for the trading lifecycle to ensure:
- Predictable behavior during errors
- Clear control flow (vs nested conditionals)
- Easy debugging via state history
- Automatic recovery from transient failures
"""
from enum import Enum


class ExecutionState(Enum):
    """
    States for the trading execution lifecycle.
    
    State transitions:
    IDLE → FETCHING_DATA → ANALYZING → PROPOSING → VALIDATING → EXECUTING → MONITORING → IDLE
    
    Error handling:
    Any state → ERROR → RECOVERING → IDLE (or manual intervention)
    """
    
    IDLE = "idle"                    # Waiting for next cycle
    FETCHING_DATA = "fetching_data"  # Fetching market data from exchange
    ANALYZING = "analyzing"          # Running AI analysis / strategy evaluation
    PROPOSING = "proposing"          # Generating trade proposal
    VALIDATING = "validating"        # Trade validation (risk checks, rules)
    EXECUTING = "executing"          # Placing order on exchange
    MONITORING = "monitoring"        # Tracking open positions (SL/TP)
    RECONCILING = "reconciling"      # Syncing DB with exchange state
    ERROR = "error"                  # Error state, requires intervention
    RECOVERING = "recovering"        # Attempting automatic recovery
    
    def __str__(self):
        return self.value


# Valid state transitions (state -> allowed next states)
VALID_TRANSITIONS = {
    ExecutionState.IDLE: [
        ExecutionState.FETCHING_DATA,
        ExecutionState.RECONCILING,
        ExecutionState.ERROR
    ],
    ExecutionState.FETCHING_DATA: [
        ExecutionState.ANALYZING,
        ExecutionState.ERROR
    ],
    ExecutionState.ANALYZING: [
        ExecutionState.PROPOSING,
        ExecutionState.IDLE,  # Analysis rejected trade
        ExecutionState.ERROR
    ],
    ExecutionState.PROPOSING: [
        ExecutionState.VALIDATING,
        ExecutionState.ERROR
    ],
    ExecutionState.VALIDATING: [
        ExecutionState.EXECUTING,
        ExecutionState.IDLE,  # Validation rejected trade
        ExecutionState.ERROR
    ],
    ExecutionState.EXECUTING: [
        ExecutionState.MONITORING,
        ExecutionState.ERROR
    ],
    ExecutionState.MONITORING: [
        ExecutionState.IDLE,  # Position closed or monitoring complete
        ExecutionState.RECONCILING,
        ExecutionState.ERROR
    ],
    ExecutionState.RECONCILING: [
        ExecutionState.IDLE,
        ExecutionState.ERROR
    ],
    ExecutionState.ERROR: [
        ExecutionState.RECOVERING,
        ExecutionState.IDLE  # Manual reset
    ],
    ExecutionState.RECOVERING: [
        ExecutionState.IDLE,
        ExecutionState.ERROR  # Recovery failed
    ]
}


def is_valid_transition(from_state: ExecutionState, to_state: ExecutionState) -> bool:
    """
    Check if state transition is valid.
    
    Args:
        from_state: Current state
        to_state: Target state
    
    Returns:
        True if transition is allowed
    """
    allowed_transitions = VALID_TRANSITIONS.get(from_state, [])
    return to_state in allowed_transitions


def get_valid_next_states(current_state: ExecutionState) -> list:
    """
    Get list of valid next states from current state.
    
    Args:
        current_state: Current execution state
    
    Returns:
        List of allowed next states
    """
    return VALID_TRANSITIONS.get(current_state, [])
