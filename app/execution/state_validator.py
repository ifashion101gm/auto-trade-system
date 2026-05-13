"""
State Validator - Enforces strict state machine transitions with audit trail.
Prevents illegal state changes that could cause financial errors.
"""
from typing import Optional
from datetime import datetime
from functools import wraps

from app.execution.states import ExecutionState, is_valid_transition, OrderState, is_valid_order_state_transition
from app.logging_config import get_logger

logger = get_logger(__name__)


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, from_state, to_state, context=""):
        self.from_state = from_state
        self.to_state = to_state
        self.context = context
        super().__init__(
            f"Illegal state transition: {from_state} → {to_state}"
            + (f" [{context}]" if context else "")
        )


class StateValidator:
    """
    Validates and logs all state transitions.
    
    Features:
    - Strict transition enforcement
    - Audit trail for debugging
    - Alert on suspicious patterns
    """
    
    def __init__(self):
        self.transition_log = []
        self.violation_count = 0
    
    def validate_execution_transition(
        self,
        from_state: ExecutionState,
        to_state: ExecutionState,
        context: str = ""
    ) -> bool:
        """
        Validate execution state transition.
        
        Args:
            from_state: Current state
            to_state: Target state
            context: Additional context for error messages
        
        Returns:
            True if valid
        
        Raises:
            StateTransitionError: If transition is invalid
        """
        if not is_valid_transition(from_state, to_state):
            self.violation_count += 1
            error = StateTransitionError(from_state, to_state, context)
            
            logger.error(
                f"🚨 STATE VIOLATION #{self.violation_count}: {error}"
            )
            
            # Log violation for audit
            self.transition_log.append({
                'type': 'VIOLATION',
                'from_state': from_state.value,
                'to_state': to_state.value,
                'context': context,
                'timestamp': datetime.utcnow().isoformat(),
                'violation_number': self.violation_count
            })
            
            raise error
        
        # Log valid transition
        self.transition_log.append({
            'type': 'VALID',
            'from_state': from_state.value,
            'to_state': to_state.value,
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.debug(f"✅ Valid transition: {from_state.value} → {to_state.value}")
        return True
    
    def validate_order_transition(
        self,
        from_state: OrderState,
        to_state: OrderState,
        order_id: str,
        context: str = ""
    ) -> bool:
        """Validate order state transition."""
        if not is_valid_order_state_transition(from_state, to_state):
            self.violation_count += 1
            error = StateTransitionError(
                from_state, to_state,
                f"Order {order_id}: {context}"
            )
            
            logger.error(f"🚨 ORDER STATE VIOLATION: {error}")
            
            self.transition_log.append({
                'type': 'ORDER_VIOLATION',
                'order_id': order_id,
                'from_state': from_state.value,
                'to_state': to_state.value,
                'context': context,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            raise error
        
        return True
    
    def get_audit_trail(self) -> list:
        """Get complete transition audit trail."""
        return self.transition_log
    
    def get_violation_summary(self) -> dict:
        """Get summary of violations."""
        return {
            'total_violations': self.violation_count,
            'recent_violations': [
                log for log in self.transition_log
                if log['type'] in ['VIOLATION', 'ORDER_VIOLATION']
            ][-10:]
        }


# Singleton instance
state_validator = StateValidator()


def enforce_state_transition(context: str = ""):
    """
    Decorator to enforce state transitions on methods.
    
    Usage:
        @enforce_state_transition("trading_cycle")
        async def execute_cycle(self):
            await self._transition_to(ExecutionState.FETCHING_DATA)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find state holder (first arg with current_state attribute)
            state_holder = None
            for arg in args:
                if hasattr(arg, 'current_state'):
                    state_holder = arg
                    break
            
            if not state_holder:
                logger.warning("State validator decorator used but no state holder found")
                return await func(*args, **kwargs)
            
            old_state = state_holder.current_state
            try:
                result = await func(*args, **kwargs)
                new_state = state_holder.current_state
                
                if old_state != new_state:
                    state_validator.validate_execution_transition(
                        old_state, new_state,
                        context=f"{func.__name__}: {context}"
                    )
                
                return result
            except Exception as e:
                logger.error(f"State transition failed in {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator
