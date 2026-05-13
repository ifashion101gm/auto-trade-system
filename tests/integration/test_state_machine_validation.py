"""Integration tests for state machine enforcement."""
import pytest

from app.execution.state_validator import StateValidator, StateTransitionError
from app.execution.states import ExecutionState, OrderState


@pytest.mark.asyncio
async def test_invalid_transition_raises_error():
    """Test that illegal state transitions raise StateTransitionError."""
    validator = StateValidator()
    
    with pytest.raises(StateTransitionError):
        validator.validate_execution_transition(
            ExecutionState.IDLE,
            ExecutionState.EXECUTING,  # Invalid skip
            context="test"
        )
    
    assert validator.violation_count == 1


@pytest.mark.asyncio
async def test_valid_transition_logged():
    """Test that valid transitions are logged correctly."""
    validator = StateValidator()
    
    result = validator.validate_execution_transition(
        ExecutionState.IDLE,
        ExecutionState.FETCHING_DATA,
        context="valid_test"
    )
    
    assert result is True
    assert len(validator.transition_log) == 1
    assert validator.transition_log[0]['type'] == 'VALID'
    assert validator.transition_log[0]['from_state'] == 'idle'
    assert validator.transition_log[0]['to_state'] == 'fetching_data'


@pytest.mark.asyncio
async def test_order_state_validation():
    """Test order state machine prevents terminal state transitions."""
    validator = StateValidator()
    
    # FILLED is terminal, cannot go back to PENDING
    with pytest.raises(StateTransitionError):
        validator.validate_order_transition(
            OrderState.FILLED,
            OrderState.PENDING,
            order_id="ord_123"
        )
    
    assert validator.violation_count >= 1
    
    # Verify violation was logged
    violations = [log for log in validator.transition_log if log['type'] == 'ORDER_VIOLATION']
    assert len(violations) > 0
    assert violations[0]['order_id'] == 'ord_123'
