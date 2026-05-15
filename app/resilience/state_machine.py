"""
System State Machine - Global operational state management.

This tracks the system-wide operational mode and enforces state transitions
with proper validation, logging, and notifications.
"""
import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.resilience.resilience_platform import SystemMode

logger = logging.getLogger(__name__)


class StateTransitionError(Exception):
    """Raised when invalid state transition is attempted."""
    pass


class SystemStateMachine:
    """
    Global system state machine that governs all operational behavior.
    
    This is the SINGLE SOURCE OF TRUTH for what the system can/cannot do
    at any given time. All components must query this state machine before
    taking actions.
    
    Valid transitions:
        NORMAL → DEGRADED → SAFE_MODE → RECOVERY → EMERGENCY → SHUTDOWN
        Any state → NORMAL (when health recovers)
        Any state → EMERGENCY (on critical failures)
    """
    
    def __init__(self, notifier=None, event_bus=None):
        self.current_state = SystemMode.NORMAL
        self.state_history: List[Dict[str, Any]] = []
        self.notifier = notifier
        self.event_bus = event_bus
        
        # Define valid transitions
        self.valid_transitions = {
            SystemMode.NORMAL: [SystemMode.DEGRADED, SystemMode.EMERGENCY, SystemMode.SHUTDOWN],
            SystemMode.DEGRADED: [SystemMode.NORMAL, SystemMode.SAFE_MODE, SystemMode.EMERGENCY],
            SystemMode.SAFE_MODE: [SystemMode.DEGRADED, SystemMode.RECOVERY, SystemMode.EMERGENCY],
            SystemMode.RECOVERY: [SystemMode.NORMAL, SystemMode.SAFE_MODE, SystemMode.EMERGENCY],
            SystemMode.RECONCILING: [SystemMode.NORMAL, SystemMode.RECOVERY, SystemMode.EMERGENCY],
            SystemMode.EMERGENCY: [SystemMode.SHUTDOWN, SystemMode.RECOVERY],
            SystemMode.SHUTDOWN: [],  # Terminal state
        }
        
        logger.info(f"✅ SystemStateMachine initialized in {self.current_state.value} mode")
    
    async def transition_to(self, target_mode: SystemMode, reason: str = ""):
        """
        Transition to a new system mode with validation.
        
        Args:
            target_mode: The target operational mode
            reason: Human-readable reason for transition
            
        Raises:
            StateTransitionError: If transition is not valid
        """
        
        if target_mode == self.current_state:
            logger.debug(f"No state change needed (already in {target_mode.value})")
            return
        
        # Validate transition
        allowed_targets = self.valid_transitions.get(self.current_state, [])
        if target_mode not in allowed_targets:
            error_msg = (
                f"Invalid state transition: {self.current_state.value} → {target_mode.value}\n"
                f"Allowed transitions from {self.current_state.value}: "
                f"{[m.value for m in allowed_targets]}"
            )
            logger.error(error_msg)
            raise StateTransitionError(error_msg)
        
        # Log transition
        old_state = self.current_state
        logger.info(
            f"🔄 STATE TRANSITION: {old_state.value} → {target_mode.value}\n"
            f"   Reason: {reason}"
        )
        
        # Execute pre-transition hooks
        await self._pre_transition_hooks(old_state, target_mode)
        
        # Perform transition
        self.current_state = target_mode
        
        # Record in history
        self.state_history.append({
            'from_state': old_state.value,
            'to_state': target_mode.value,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Keep only last 100 transitions
        if len(self.state_history) > 100:
            self.state_history = self.state_history[-100:]
        
        # Execute post-transition hooks
        await self._post_transition_hooks(old_state, target_mode)
        
        # Publish event
        if self.event_bus:
            try:
                await self.event_bus.publish('STATE_TRANSITION', {
                    'from_state': old_state.value,
                    'to_state': target_mode.value,
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to publish state transition event: {e}")
    
    async def _pre_transition_hooks(self, from_state: SystemMode, to_state: SystemMode):
        """Execute actions before state transition."""
        
        if to_state == SystemMode.EMERGENCY:
            logger.critical("🚨 Entering EMERGENCY mode - preparing for emergency stop")
            # Could trigger position close here if needed
        
        elif to_state == SystemMode.SAFE_MODE:
            logger.warning("⚠️ Entering SAFE_MODE - blocking new entries")
        
        elif to_state == SystemMode.RECOVERY:
            logger.info("🔧 Entering RECOVERY mode - pausing trading")
    
    async def _post_transition_hooks(self, from_state: SystemMode, to_state: SystemMode):
        """Execute actions after state transition."""
        
        # Send notification for significant state changes
        if self.notifier and to_state in (SystemMode.SAFE_MODE, SystemMode.EMERGENCY, SystemMode.RECOVERY):
            try:
                await self.notifier.send_message(
                    f"🔄 System State Changed\n"
                    f"From: {from_state.value.upper()}\n"
                    f"To: {to_state.value.upper()}\n"
                    f"Trading {'ALLOWED' if to_state.allows_trading() else 'BLOCKED'}"
                )
            except Exception as e:
                logger.error(f"Failed to send state change notification: {e}")
    
    def can_trade(self) -> bool:
        """Check if trading is currently allowed."""
        return self.current_state.allows_trading()
    
    def can_enter_new_positions(self) -> bool:
        """Check if new position entries are allowed."""
        return self.current_state.allows_new_entries()
    
    def can_exit_positions(self) -> bool:
        """Check if position exits are allowed."""
        return not self.current_state.blocks_all_trading()
    
    def is_in_emergency(self) -> bool:
        """Check if system is in emergency mode."""
        return self.current_state == SystemMode.EMERGENCY
    
    def get_current_mode(self) -> SystemMode:
        """Get current operational mode."""
        return self.current_state
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive state machine status."""
        
        return {
            'current_state': self.current_state.value,
            'can_trade': self.can_trade(),
            'can_enter_positions': self.can_enter_new_positions(),
            'can_exit_positions': self.can_exit_positions(),
            'is_emergency': self.is_in_emergency(),
            'recent_transitions': self.state_history[-10:],  # Last 10 transitions
            'total_transitions': len(self.state_history)
        }
    
    def reset_to_normal(self, reason: str = "Manual reset"):
        """Force reset to NORMAL mode (use with caution)."""
        
        logger.warning(f"⚠️ FORCING RESET to NORMAL mode: {reason}")
        
        # Bypass normal transition validation for manual override
        old_state = self.current_state
        self.current_state = SystemMode.NORMAL
        
        self.state_history.append({
            'from_state': old_state.value,
            'to_state': SystemMode.NORMAL.value,
            'reason': f"{reason} (FORCE RESET)",
            'timestamp': datetime.utcnow().isoformat(),
            'forced': True
        })
        
        if self.notifier:
            asyncio.create_task(
                self.notifier.send_message(
                    f"⚠️ SYSTEM RESET\n"
                    f"Forced reset from {old_state.value} to NORMAL\n"
                    f"Reason: {reason}"
                )
            )
