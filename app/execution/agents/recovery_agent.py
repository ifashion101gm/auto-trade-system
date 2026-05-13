"""Recovery Agent - Auto-repairs detected failures without manual intervention."""
import asyncio
from typing import Dict, Any
from app.execution.agents.base_agent import BaseAgent
from app.services.startup_recovery import StartupRecoveryService
from app.execution.state_validator import state_validator
from app.execution.states import ExecutionState
from app.events.event_bus import EventBus


class RecoveryAgent(BaseAgent):
    """Performs automatic recovery from various failure scenarios."""
    
    def __init__(self, startup_recovery: StartupRecoveryService,
                 event_bus: EventBus):
        super().__init__("RecoveryAgent")
        self.startup_recovery = startup_recovery
        self.event_bus = event_bus
        self.recovery_attempts = 0
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt recovery based on detected issues."""
        issues = context.get('issues', [])
        recovery_actions = []
        
        for issue in issues:
            action = await self._handle_issue(issue, context)
            recovery_actions.append(action)
        
        # If state machine is stuck, reset to IDLE
        if any(a.get('action') == 'reset_state_machine' for a in recovery_actions):
            await self._reset_state_machine()
        
        return {
            'recovery_attempted': len(recovery_actions) > 0,
            'actions_taken': recovery_actions,
            'success': all(a.get('success', False) for a in recovery_actions)
        }
    
    async def _handle_issue(self, issue: Dict, context: Dict) -> Dict:
        """Handle specific issue type."""
        issue_type = issue.get('type')
        
        if issue_type == 'circuit_breaker_open':
            return await self._handle_circuit_breaker(context)
        
        elif issue_type == 'api_connectivity_failed':
            return await self._handle_api_failure(context)
        
        elif issue_type == 'state_mismatch':
            return await self._handle_state_mismatch(context)
        
        elif issue_type == 'position_sync_error':
            return await self._handle_position_sync(context)
        
        else:
            return {
                'issue_type': issue_type,
                'action': 'unknown',
                'success': False,
                'message': f"No recovery handler for {issue_type}"
            }
    
    async def _handle_circuit_breaker(self, context: Dict) -> Dict:
        """Handle open circuit breaker."""
        self.logger.info("Attempting circuit breaker recovery...")
        
        # Wait for cooldown period
        await asyncio.sleep(30)
        
        # Re-check health
        health = await self.startup_recovery.circuit_breaker.check_system_health()
        
        return {
            'issue_type': 'circuit_breaker_open',
            'action': 'wait_and_retry',
            'success': health.can_trade,
            'new_state': health.state
        }
    
    async def _handle_api_failure(self, context: Dict) -> Dict:
        """Handle API connectivity failure."""
        self.logger.info("Attempting API reconnection...")
        
        # Try to reconnect
        try:
            await self.startup_recovery.exchange_manager.fetch_ticker("BTC/USDT")
            return {
                'issue_type': 'api_connectivity_failed',
                'action': 'reconnect',
                'success': True
            }
        except Exception as e:
            return {
                'issue_type': 'api_connectivity_failed',
                'action': 'reconnect',
                'success': False,
                'error': str(e)
            }
    
    async def _handle_state_mismatch(self, context: Dict) -> Dict:
        """Handle state machine mismatch."""
        self.logger.warning("State mismatch detected - triggering full recovery")
        
        # Trigger startup recovery sequence
        recovery_result = await self.startup_recovery.execute_recovery(
            user_id=context.get('user_id'),
            db_session=context.get('db_session')
        )
        
        return {
            'issue_type': 'state_mismatch',
            'action': 'full_recovery',
            'success': recovery_result.success,
            'details': recovery_result.to_dict()
        }
    
    async def _handle_position_sync(self, context: Dict) -> Dict:
        """Handle position synchronization error."""
        self.logger.info("Triggering position reconciliation...")
        
        # Trigger reconciliation
        await self.startup_recovery.reconciliation_service.reconcile_positions(
            user_id=context.get('user_id'),
            db_session=context.get('db_session'),
            auto_repair=True
        )
        
        return {
            'issue_type': 'position_sync_error',
            'action': 'reconcile',
            'success': True
        }
    
    async def _reset_state_machine(self):
        """Reset state validator to clean IDLE state."""
        self.logger.warning("Resetting state machine to IDLE")
        state_validator.current_state = None
        state_validator.transition_log.clear()
