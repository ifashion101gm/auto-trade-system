"""
Resilience Manager - Central orchestration hub for failure management.

This is the SINGLE SOURCE OF TRUTH for all recovery decisions in the system.
It coordinates between watchdogs, state machine, recovery planner, and executors
to prevent conflicting recovery actions and cascading failures.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.resilience.resilience_platform import (
    FailureEvent,
    FailureSeverity,
    FailureDomain,
    SystemMode,
    HealthScore,
    RecoveryPlan,
    HealingCooldownManager,
    FailureCorrelationEngine,
    BackpressureController,
)

logger = logging.getLogger(__name__)


class ResilienceManager:
    """
    Central resilience orchestration hub.
    
    All failure detection flows through this manager, which:
    1. Classifies failure severity
    2. Correlates related failures into incidents
    3. Builds deterministic recovery plans
    4. Executes plans with idempotency and cooldowns
    5. Updates global system state
    
    This prevents:
    - Watchdog storms
    - Recovery loops
    - Duplicate recovery actions
    - Cascading restarts
    - Reconciliation/execution conflicts
    """
    
    def __init__(
        self,
        state_machine=None,  # SystemStateMachine instance
        recovery_executor=None,  # RecoveryExecutor instance
        event_bus=None,  # EventBus for publishing
        notifier=None,  # TelegramNotifier for alerts
    ):
        # Core components
        self.state_machine = state_machine
        self.recovery_executor = recovery_executor
        self.event_bus = event_bus
        self.notifier = notifier
        
        # Sub-systems
        self.cooldown_manager = HealingCooldownManager()
        self.correlation_engine = FailureCorrelationEngine(correlation_window_seconds=60)
        self.backpressure_controller = BackpressureController()
        
        # Health tracking
        self.health_score = HealthScore()
        self.current_mode = SystemMode.NORMAL
        
        # Incident tracking
        self.active_incidents: Dict[str, Dict[str, Any]] = {}
        self.total_failures_handled = 0
        self.total_recoveries_executed = 0
        
        logger.info("✅ ResilienceManager initialized")
    
    async def handle_failure(self, failure_event: FailureEvent):
        """
        Main entry point for all failure handling.
        
        This method orchestrates the entire recovery pipeline:
        1. Classify failure
        2. Correlate with existing incidents
        3. Build recovery plan
        4. Execute plan (if appropriate)
        5. Update system state
        
        Args:
            failure_event: The detected failure
        """
        self.total_failures_handled += 1
        
        logger.info(
            f"🚨 Handling failure: {failure_event.failure_type} "
            f"(severity={failure_event.severity.value}, "
            f"domain={failure_event.domain.value})"
        )
        
        try:
            # Step 1: Classify and correlate
            incident_id = self.correlation_engine.correlate(failure_event)
            
            # Step 2: Determine if we should act (respect cooldowns)
            action_key = f"{failure_event.domain.value}_{failure_event.failure_type}"
            if not self.cooldown_manager.should_execute(action_key):
                logger.warning(
                    f"⏸️ Skipping recovery for {action_key} - in cooldown period"
                )
                return
            
            # Step 3: Check rate limits
            if self.cooldown_manager.would_exceed_rate_limit(action_key, max_per_hour=3):
                logger.error(
                    f"🛑 Rate limit exceeded for {action_key} - "
                    f"would exceed 3 executions/hour"
                )
                await self._escalate_to_emergency(failure_event)
                return
            
            # Step 4: Build recovery plan
            recovery_plan = await self._build_recovery_plan(failure_event, incident_id)
            
            # Step 5: Simulate plan before execution
            simulation = recovery_plan.simulate()
            logger.info(f"📋 Recovery plan simulated: {simulation}")
            
            # Step 6: Execute plan (if severity warrants it)
            if failure_event.severity in (FailureSeverity.CRITICAL, FailureSeverity.EMERGENCY):
                await self._execute_recovery_plan(recovery_plan, failure_event)
            
            # Step 7: Update health score and mode
            await self._update_health_score(failure_event)
            await self._transition_system_mode()
            
            # Step 8: Record execution
            self.cooldown_manager.record_execution(action_key)
            self.total_recoveries_executed += 1
            
        except Exception as e:
            logger.error(f"❌ Failure handling failed: {e}", exc_info=True)
            # Don't let recovery failures crash the system
    
    async def _build_recovery_plan(
        self,
        failure_event: FailureEvent,
        incident_id: Optional[str]
    ) -> RecoveryPlan:
        """Build deterministic recovery plan based on failure type and system state."""
        
        plan = RecoveryPlan(
            failure_event=failure_event,
            priority=self._calculate_priority(failure_event)
        )
        
        # Domain-specific recovery strategies
        if failure_event.domain == FailureDomain.API:
            await self._build_api_recovery_plan(plan, failure_event)
        
        elif failure_event.domain == FailureDomain.WEBSOCKET:
            await self._build_websocket_recovery_plan(plan, failure_event)
        
        elif failure_event.domain == FailureDomain.DATABASE:
            await self._build_database_recovery_plan(plan, failure_event)
        
        elif failure_event.domain == FailureDomain.MEMORY:
            await self._build_memory_recovery_plan(plan, failure_event)
        
        elif failure_event.domain == FailureDomain.EXECUTION:
            await self._build_execution_recovery_plan(plan, failure_event)
        
        elif failure_event.domain == FailureDomain.RECONCILIATION:
            await self._build_reconciliation_recovery_plan(plan, failure_event)
        
        else:
            # Generic recovery
            plan.add_step(
                action_name="log_and_alert",
                description=f"Log failure and send alert for {failure_event.failure_type}"
            )
        
        return plan
    
    async def _build_api_recovery_plan(self, plan: RecoveryPlan, failure: FailureEvent):
        """Build recovery plan for API failures."""
        
        if failure.failure_type == "high_latency":
            plan.add_step(
                action_name="activate_degraded_mode",
                description="Activate degraded trading mode (reduce position sizes)",
                timeout_seconds=10
            )
            plan.add_step(
                action_name="alert_operator",
                description="Send Telegram alert about API degradation"
            )
        
        elif failure.failure_type == "connection_failed":
            plan.add_step(
                action_name="pause_new_entries",
                description="Block new trade entries",
                timeout_seconds=5
            )
            plan.add_step(
                action_name="attempt_api_reconnect",
                description="Attempt to reconnect to exchange API",
                timeout_seconds=30,
                idempotent=True
            )
            plan.add_step(
                action_name="verify_connectivity",
                description="Verify API connectivity restored",
                timeout_seconds=10
            )
        
        elif failure.failure_type == "consecutive_failures":
            plan.add_step(
                action_name="open_circuit_breaker",
                description="Open circuit breaker to block all API calls",
                timeout_seconds=5
            )
            plan.add_step(
                action_name="snapshot_positions",
                description="Snapshot current positions for reconciliation",
                timeout_seconds=15
            )
            plan.add_step(
                action_name="enter_safe_mode",
                description="Transition to SAFE_MODE (exits only)"
            )
    
    async def _build_websocket_recovery_plan(self, plan: RecoveryPlan, failure: FailureEvent):
        """Build recovery plan for WebSocket failures."""
        
        plan.add_step(
            action_name="force_websocket_reconnect",
            description="Force WebSocket reconnection",
            timeout_seconds=30,
            idempotent=True
        )
        plan.add_step(
            action_name="verify_data_flow",
            description="Verify market data is flowing",
            timeout_seconds=10
        )
        plan.add_step(
            action_name="fallback_to_rest_polling",
            description="Enable REST API polling as fallback",
            timeout_seconds=5
        )
    
    async def _build_database_recovery_plan(self, plan: RecoveryPlan, failure: FailureEvent):
        """Build recovery plan for database failures."""
        
        plan.add_step(
            action_name="pause_all_writes",
            description="Pause all database writes to prevent corruption",
            timeout_seconds=5
        )
        plan.add_step(
            action_name="attempt_db_reconnect",
            description="Attempt database reconnection",
            timeout_seconds=30
        )
        plan.add_step(
            action_name="verify_integrity",
            description="Run database integrity checks",
            timeout_seconds=60
        )
    
    async def _build_memory_recovery_plan(self, plan: RecoveryPlan, failure: FailureEvent):
        """Build recovery plan for memory issues."""
        
        if failure.failure_type == "memory_critical":
            plan.add_step(
                action_name="trigger_garbage_collection",
                description="Force garbage collection",
                timeout_seconds=10,
                idempotent=True
            )
            plan.add_step(
                action_name="clear_caches",
                description="Clear application caches",
                timeout_seconds=15
            )
            plan.add_step(
                action_name="schedule_graceful_restart",
                description="Schedule graceful application restart",
                timeout_seconds=300
            )
    
    async def _build_execution_recovery_plan(self, plan: RecoveryPlan, failure: FailureEvent):
        """Build recovery plan for execution failures."""
        
        plan.add_step(
            action_name="block_new_orders",
            description="Block new order submissions",
            timeout_seconds=5
        )
        plan.add_step(
            action_name="verify_pending_orders",
            description="Verify status of pending orders on exchange",
            timeout_seconds=30
        )
        plan.add_step(
            action_name="reconcile_positions",
            description="Run position reconciliation",
            timeout_seconds=60
        )
    
    async def _build_reconciliation_recovery_plan(self, plan: RecoveryPlan, failure: FailureEvent):
        """Build recovery plan for reconciliation mismatches."""
        
        plan.add_step(
            action_name="snapshot_exchange_state",
            description="Snapshot current exchange positions",
            timeout_seconds=15
        )
        plan.add_step(
            action_name="snapshot_database_state",
            description="Snapshot current database positions",
            timeout_seconds=15
        )
        plan.add_step(
            action_name="auto_repair_safe_mismatches",
            description="Auto-repair safe mismatches (orphaned orders)",
            timeout_seconds=30,
            idempotent=True
        )
        plan.add_step(
            action_name="alert_unsafe_mismatches",
            description="Alert operator for manual review of unsafe mismatches"
        )
    
    async def _execute_recovery_plan(self, plan: RecoveryPlan, failure: FailureEvent):
        """Execute recovery plan with proper error handling."""
        
        logger.info(f"▶️ Executing recovery plan {plan.plan_id}")
        
        if not self.recovery_executor:
            logger.error("❌ No recovery executor configured")
            return
        
        try:
            result = await self.recovery_executor.execute_plan(plan)
            
            if result.get('success'):
                logger.info(f"✅ Recovery plan {plan.plan_id} succeeded")
            else:
                logger.error(f"❌ Recovery plan {plan.plan_id} failed: {result.get('error')}")
                await self._escalate_to_emergency(failure)
        
        except Exception as e:
            logger.error(f"❌ Recovery plan execution crashed: {e}", exc_info=True)
            await self._escalate_to_emergency(failure)
    
    async def _update_health_score(self, failure: FailureEvent):
        """Update health score based on failure impact."""
        
        severity_impact = {
            FailureSeverity.INFO: 0,
            FailureSeverity.WARNING: -5,
            FailureSeverity.CRITICAL: -15,
            FailureSeverity.EMERGENCY: -30,
        }
        
        impact = severity_impact.get(failure.severity, 0)
        
        # Update domain-specific health
        if failure.domain == FailureDomain.API:
            self.health_score.api_health = max(0, self.health_score.api_health + impact)
        elif failure.domain == FailureDomain.WEBSOCKET:
            self.health_score.websocket_health = max(0, self.health_score.websocket_health + impact)
        elif failure.domain == FailureDomain.EXECUTION:
            self.health_score.execution_health = max(0, self.health_score.execution_health + impact)
        elif failure.domain == FailureDomain.MEMORY:
            self.health_score.memory_health = max(0, self.health_score.memory_health + impact)
        elif failure.domain == FailureDomain.RECONCILIATION:
            self.health_score.reconciliation_health = max(
                0, self.health_score.reconciliation_health + impact
            )
        
        logger.info(
            f"📊 Health score updated: composite={self.health_score.composite_score:.1f}"
        )
    
    async def _transition_system_mode(self):
        """Transition system mode based on current health score."""
        
        target_mode = self.health_score.determine_mode()
        
        if target_mode != self.current_mode:
            logger.info(
                f"🔄 System mode transition: {self.current_mode.value} → {target_mode.value}"
            )
            
            if self.state_machine:
                await self.state_machine.transition_to(target_mode)
            
            self.current_mode = target_mode
            
            # Send mode change notification
            if self.notifier and target_mode in (SystemMode.SAFE_MODE, SystemMode.EMERGENCY):
                await self.notifier.send_message(
                    f"⚠️ System mode changed to {target_mode.value}\n"
                    f"Health score: {self.health_score.composite_score:.1f}/100"
                )
    
    async def _escalate_to_emergency(self, failure: FailureEvent):
        """Escalate to emergency mode when recovery fails repeatedly."""
        
        logger.critical(
            f"🚨 ESCALATING TO EMERGENCY MODE due to repeated failures: "
            f"{failure.failure_type}"
        )
        
        if self.state_machine:
            await self.state_machine.transition_to(SystemMode.EMERGENCY)
        
        self.current_mode = SystemMode.EMERGENCY
        
        if self.notifier:
            await self.notifier.send_critical_alert(
                'emergency_escalation',
                {
                    'reason': f"Repeated failures: {failure.failure_type}",
                    'health_score': self.health_score.composite_score,
                    'incident_count': len(self.active_incidents)
                }
            )
    
    def _calculate_priority(self, failure: FailureEvent) -> int:
        """Calculate recovery priority (1=highest, 10=lowest)."""
        
        priority_map = {
            ('position_mismatch', FailureDomain.RECONCILIATION): 1,
            ('order_stuck', FailureDomain.EXECUTION): 2,
            ('websocket_dead', FailureDomain.WEBSOCKET): 3,
            ('api_connection_failed', FailureDomain.API): 3,
            ('memory_critical', FailureDomain.MEMORY): 4,
            ('high_latency', FailureDomain.API): 5,
            ('dashboard_failure', FailureDomain.EXTERNAL): 8,
        }
        
        return priority_map.get(
            (failure.failure_type, failure.domain),
            5  # Default priority
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive resilience status for dashboard."""
        
        return {
            'current_mode': self.current_mode.value,
            'health_score': {
                'composite': round(self.health_score.composite_score, 1),
                'api': round(self.health_score.api_health, 1),
                'websocket': round(self.health_score.websocket_health, 1),
                'execution': round(self.health_score.execution_health, 1),
                'memory': round(self.health_score.memory_health, 1),
                'reconciliation': round(self.health_score.reconciliation_health, 1),
            },
            'active_incidents': len(self.active_incidents),
            'total_failures_handled': self.total_failures_handled,
            'total_recoveries_executed': self.total_recoveries_executed,
            'backpressure': {
                'trade_frequency_multiplier': self.backpressure_controller.trade_frequency_multiplier,
                'current_delay_ms': self.backpressure_controller.current_delay_ms,
            }
        }
