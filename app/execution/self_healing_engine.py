"""
Self-healing execution engine for closed-loop trade execution.

This module centralizes the guard rails that were previously spread across the
trading service: health gates, duplicate protection, execution telemetry,
anomaly checks, verification-triggered recovery, and post-cycle reconciliation.
The engine is intentionally dependency-injected so it can be used by the live
service and tested with lightweight mocks.
"""
import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.execution.anomaly_detector import AnomalyDetector
from app.execution.dedup_engine import DuplicateProtectionEngine
from app.events.event_types import RECOVERY_ACTION_TAKEN, RECOVERY_COMPLETED, RECOVERY_STARTED

logger = logging.getLogger(__name__)


class CircuitBreakerLevel(str, Enum):
    """
    Professional-grade circuit breaker levels for graduated response.
    
    WARNING: Log only, continue trading normally
    DEGRADED: Reduce position sizes, increase caution
    CRITICAL: Stop new entries, manage existing positions
    EMERGENCY: Close all positions immediately
    """
    WARNING = "WARNING"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class HealingDecision:
    """Outcome returned by self-healing gates and recovery actions."""

    can_continue: bool
    status: str
    issues: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    circuit_breaker_level: Optional[CircuitBreakerLevel] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the decision for API responses and logs."""
        return {
            "can_continue": self.can_continue,
            "status": self.status,
            "issues": self.issues,
            "actions": self.actions,
            "circuit_breaker_level": self.circuit_breaker_level.value if self.circuit_breaker_level else None,
            **self.metadata,
        }


class SelfHealingExecutionEngine:
    """
    Coordinates closed-loop execution safety and automatic repair.

    The engine does not place trades itself. Instead it wraps the surrounding
    trading workflow with deterministic guard rails:
    - pre-cycle health checks through the monitoring agent and circuit breaker
    - duplicate signal rejection before any exchange call
    - execution metric recording and anomaly detection
    - verification failure recovery
    - post-cycle reconciliation
    - consolidated health reporting
    """

    def __init__(
        self,
        *,
        monitoring_agent=None,
        verification_agent=None,
        recovery_agent=None,
        reconciliation_agent=None,
        circuit_breaker=None,
        notifier=None,
        dedup_engine: Optional[DuplicateProtectionEngine] = None,
        anomaly_detector: Optional[AnomalyDetector] = None,
        event_bus=None,
        critical_anomaly_severities: Optional[List[str]] = None,
        # Watchdog configuration
        api_watchdog_enabled: bool = True,
        db_watchdog_enabled: bool = True,
        memory_watchdog_enabled: bool = True,  # ENABLED for production
        queue_watchdog_enabled: bool = False,
        # Memory watchdog thresholds
        memory_warning_pct: float = 60.0,
        memory_critical_pct: float = 80.0,
        memory_auto_restart_enabled: bool = True,
    ):
        self.monitoring_agent = monitoring_agent
        self.verification_agent = verification_agent
        self.recovery_agent = recovery_agent
        self.reconciliation_agent = reconciliation_agent
        self.circuit_breaker = circuit_breaker
        self.notifier = notifier
        self.dedup_engine = dedup_engine or DuplicateProtectionEngine()
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        self.event_bus = event_bus
        self.critical_anomaly_severities = set(critical_anomaly_severities or ["CRITICAL"])
        self._last_recovery: Optional[Dict[str, Any]] = None
        
        # Watchdog configuration
        self.api_watchdog_enabled = api_watchdog_enabled
        self.db_watchdog_enabled = db_watchdog_enabled
        self.memory_watchdog_enabled = memory_watchdog_enabled
        self.queue_watchdog_enabled = queue_watchdog_enabled
        
        # Memory watchdog thresholds
        self.memory_warning_pct = memory_warning_pct
        self.memory_critical_pct = memory_critical_pct
        self.memory_auto_restart_enabled = memory_auto_restart_enabled
        
        # Watchdog state tracking
        self._watchdog_state: Dict[str, Any] = {
            "api_failures": 0,
            "db_stale_transactions": 0,
            "memory_usage_mb": 0,
            "memory_usage_pct": 0,
            "queue_depth": 0,
            "last_check": None,
            "auto_restart_triggered": False,
        }

    async def run_preflight(self, context: Dict[str, Any]) -> HealingDecision:
        """Run health gates before the trading cycle is allowed to continue."""
        issues: List[Dict[str, Any]] = []
        metadata: Dict[str, Any] = {}

        if self.monitoring_agent:
            health_check = await self.monitoring_agent.run(context)
            metadata["monitoring"] = health_check
            if not health_check.get("can_continue_trading", True):
                for issue in health_check.get("issues", []):
                    issues.append(self._normalize_issue(issue, "monitoring_block"))

        if self.circuit_breaker:
            health_state = await self.circuit_breaker.check_system_health()
            metadata["circuit_breaker"] = self._serialize_health_state(health_state)
            if not getattr(health_state, "can_trade", True):
                issues.append(
                    {
                        "type": "circuit_breaker_open",
                        "reason": getattr(health_state, "reason", "Circuit breaker blocked trading"),
                        "state": getattr(health_state, "state", None),
                    }
                )

        if issues:
            return HealingDecision(False, "blocked_by_self_healing", issues=issues, metadata=metadata)

        return HealingDecision(True, "healthy", metadata=metadata)

    async def guard_signal(self, proposal: Dict[str, Any]) -> HealingDecision:
        """Reject duplicate trade proposals before execution."""
        dedup_result = await self.dedup_engine.check_and_mark_signal(proposal)
        if dedup_result.get("is_duplicate"):
            return HealingDecision(
                False,
                "duplicate_signal_rejected",
                issues=[{"type": "duplicate_signal", "signal_hash": dedup_result.get("signal_hash")}],
                metadata={"deduplication": dedup_result},
            )

        return HealingDecision(True, "signal_accepted", metadata={"deduplication": dedup_result})

    async def execute_with_observation(
        self,
        operation: Callable[[], Awaitable[Dict[str, Any]]],
        *,
        proposal: Dict[str, Any],
        endpoint: str = "create_market_order",
    ) -> Dict[str, Any]:
        """Execute an async operation while recording circuit-breaker and anomaly telemetry."""
        started_at = time.time()
        try:
            result = await operation()
            latency_ms = (time.time() - started_at) * 1000
            anomalies = await self.record_execution_success(
                proposal=proposal,
                execution_result=result,
                latency_ms=latency_ms,
                endpoint=endpoint,
            )
            if isinstance(result, dict):
                result.setdefault('_self_healing_latency_ms', latency_ms)
                result.setdefault('_self_healing_anomalies', anomalies)
            return result
        except Exception:
            latency_ms = (time.time() - started_at) * 1000
            await self.record_execution_failure(latency_ms=latency_ms, endpoint=endpoint)
            raise

    async def record_execution_success(
        self,
        *,
        proposal: Dict[str, Any],
        execution_result: Dict[str, Any],
        latency_ms: float,
        endpoint: str = "create_market_order",
    ) -> List[Dict[str, Any]]:
        """Record successful execution and return any detected anomalies."""
        if self.circuit_breaker:
            await self.circuit_breaker.record_api_call(True, latency_ms, endpoint)

        self.anomaly_detector.record_latency(latency_ms)
        self.anomaly_detector.record_order_result(True)

        slippage_pct = self._calculate_slippage(proposal, execution_result)
        if slippage_pct is not None:
            self.anomaly_detector.record_slippage(slippage_pct)
            if self.circuit_breaker:
                actual_price = (
                    execution_result.get("filled_price")
                    or execution_result.get("price")
                    or proposal.get("entry_price")
                )
                await self.circuit_breaker.record_fill_slippage(
                    symbol=proposal.get("symbol"),
                    expected_price=proposal.get("entry_price"),
                    actual_price=actual_price,
                )

        order_id = execution_result.get("order_id")
        if order_id:
            await self.dedup_engine.mark_order_executed(order_id, execution_result)

        if execution_result.get("status") == "executed":
            self.anomaly_detector.record_trade(proposal.get("symbol", "unknown"), proposal.get("side", "unknown"))

        return self.anomaly_detector.run_comprehensive_check(
            current_latency_ms=latency_ms,
            current_slippage_pct=slippage_pct,
        )

    async def record_execution_failure(
        self,
        *,
        latency_ms: float,
        endpoint: str = "create_market_order",
    ) -> List[Dict[str, Any]]:
        """Record failed execution and return any detected anomalies."""
        if self.circuit_breaker:
            await self.circuit_breaker.record_api_call(False, latency_ms, endpoint)

        self.anomaly_detector.record_latency(latency_ms)
        self.anomaly_detector.record_order_result(False)
        return self.anomaly_detector.run_comprehensive_check(current_latency_ms=latency_ms)

    async def verify_and_recover(
        self,
        *,
        execution_result: Dict[str, Any],
        proposal: Dict[str, Any],
        context: Dict[str, Any],
    ) -> HealingDecision:
        """Verify exchange/DB state and invoke recovery automatically when verification fails."""
        if not self.verification_agent:
            return HealingDecision(True, "verification_skipped")

        verification_result = await self.verification_agent.run(
            {"execution_result": execution_result, "proposal": proposal, **context}
        )

        if verification_result.get("verification_passed", False):
            return HealingDecision(True, "verification_passed", metadata={"verification": verification_result})

        issue = {
            "type": "verification_failed",
            "details": verification_result.get("checks", verification_result),
        }
        recovery_result = await self.recover([issue], context)
        return HealingDecision(
            recovery_result.can_continue,
            "verification_failed_recovered" if recovery_result.can_continue else "verification_failed_recovery_failed",
            issues=[issue],
            actions=recovery_result.actions,
            metadata={"verification": verification_result, "recovery": recovery_result.to_dict()},
        )

    async def recover(self, issues: List[Dict[str, Any]], context: Dict[str, Any]) -> HealingDecision:
        """Run the recovery agent for detected issues and publish lifecycle events."""
        if not issues:
            return HealingDecision(True, "no_recovery_needed")

        await self._publish(RECOVERY_STARTED, {"issues": issues, "timestamp": datetime.utcnow().isoformat()})

        if not self.recovery_agent:
            decision = HealingDecision(False, "recovery_unavailable", issues=issues)
            self._last_recovery = decision.to_dict()
            await self._publish(RECOVERY_COMPLETED, decision.to_dict())
            return decision

        recovery_result = await self.recovery_agent.run({"issues": issues, **context})
        actions = recovery_result.get("actions_taken", [])
        can_continue = bool(recovery_result.get("success", False))
        decision = HealingDecision(
            can_continue,
            "recovered" if can_continue else "recovery_failed",
            issues=issues,
            actions=actions,
            metadata={"recovery": recovery_result},
        )
        self._last_recovery = decision.to_dict()
        await self._publish(RECOVERY_ACTION_TAKEN, decision.to_dict())
        await self._publish(RECOVERY_COMPLETED, decision.to_dict())
        return decision

    async def reconcile(self, context: Dict[str, Any]) -> HealingDecision:
        """Run reconciliation and convert sync mismatches into recoverable issues."""
        if not self.reconciliation_agent:
            return HealingDecision(True, "reconciliation_skipped")

        result = await self.reconciliation_agent.run(context)
        metadata = {"reconciliation": result}
        if result.get("is_synced", True):
            return HealingDecision(True, "reconciled", metadata=metadata)

        issues = []
        for key in ("orphaned_positions", "ghost_positions", "mismatches"):
            count = result.get(key, 0)
            if count:
                issues.append({"type": "position_sync_error", "category": key, "count": count})

        return HealingDecision(False, "reconciliation_issues_detected", issues=issues, metadata=metadata)

    async def run_watchdogs(self, context: Dict[str, Any]) -> HealingDecision:
        """
        Run all enabled watchdogs to detect system health issues.
        
        CRITICAL: This is a proactive health check that runs independently
        of trading cycles to catch issues before they cause failures.
        
        Watchdogs:
        - API Watchdog: Detect exchange API failure patterns
        - DB Watchdog: Detect stale transactions and connection issues
        - Memory Watchdog: Detect memory leaks
        - Queue Watchdog: Detect frozen workers or queue buildup
        
        Returns:
            HealingDecision with circuit breaker level recommendation
        """
        import psutil
        import sys
        
        issues: List[Dict[str, Any]] = []
        actions: List[Dict[str, Any]] = []
        max_severity = CircuitBreakerLevel.WARNING
        
        # Update timestamp
        self._watchdog_state["last_check"] = datetime.utcnow().isoformat()
        
        # Watchdog 1: API Health Check
        if self.api_watchdog_enabled and self.circuit_breaker:
            api_health = await self.circuit_breaker.check_system_health()
            api_failures = getattr(api_health, 'failure_count', 0)
            
            self._watchdog_state["api_failures"] = api_failures
            
            # Determine severity based on failure count
            if api_failures >= 10:
                severity = CircuitBreakerLevel.EMERGENCY
                issues.append({
                    "type": "api_watchdog",
                    "severity": severity.value,
                    "message": f"API failures critical: {api_failures} consecutive failures",
                    "recommendation": "Close all positions immediately"
                })
                actions.append({"action": "emergency_close_all", "reason": "api_failure_threshold"})
            elif api_failures >= 5:
                severity = CircuitBreakerLevel.CRITICAL
                issues.append({
                    "type": "api_watchdog",
                    "severity": severity.value,
                    "message": f"API failures high: {api_failures} consecutive failures",
                    "recommendation": "Stop new entries"
                })
                actions.append({"action": "block_new_entries", "reason": "api_failure_threshold"})
            elif api_failures >= 3:
                severity = CircuitBreakerLevel.DEGRADED
                issues.append({
                    "type": "api_watchdog",
                    "severity": severity.value,
                    "message": f"API failures elevated: {api_failures} consecutive failures",
                    "recommendation": "Reduce position sizes by 50%"
                })
                actions.append({"action": "reduce_position_size", "factor": 0.5})
            elif api_failures >= 1:
                severity = CircuitBreakerLevel.WARNING
                issues.append({
                    "type": "api_watchdog",
                    "severity": severity.value,
                    "message": f"API failures detected: {api_failures} failures",
                    "recommendation": "Monitor closely"
                })
            
            if severity.value > max_severity.value:
                max_severity = severity
        
        # Watchdog 2: Database Stale Transaction Check
        if self.db_watchdog_enabled:
            # Check for stale transactions (older than 5 minutes without completion)
            from sqlalchemy.ext.asyncio import AsyncSession
            from app.database.session import get_async_session
            from app.database.models import TradeProposals
            from sqlalchemy import select, func
            from datetime import timedelta
            
            try:
                async with get_async_session() as db_session:
                    # Find proposals stuck in pending state for > 5 minutes
                    cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                    stmt = (
                        select(func.count())
                        .where(TradeProposals.status == 'pending')
                        .where(TradeProposals.created_at < cutoff_time)
                    )
                    result = await db_session.execute(stmt)
                    stale_count = result.scalar() or 0
                    
                    self._watchdog_state["db_stale_transactions"] = stale_count
                    
                    if stale_count > 0:
                        severity = CircuitBreakerLevel.CRITICAL
                        issues.append({
                            "type": "db_watchdog",
                            "severity": severity.value,
                            "message": f"Found {stale_count} stale pending transactions",
                            "recommendation": "Investigate database locks and clean up stale records"
                        })
                        actions.append({
                            "action": "cleanup_stale_transactions",
                            "count": stale_count,
                            "cutoff_minutes": 5
                        })
                        
                        if severity.value > max_severity.value:
                            max_severity = severity
            except Exception as e:
                logger.error(f"DB watchdog check failed: {e}")
                issues.append({
                    "type": "db_watchdog",
                    "severity": CircuitBreakerLevel.CRITICAL.value,
                    "message": f"Database health check failed: {str(e)}",
                    "recommendation": "Check database connectivity"
                })
        
        # Watchdog 3: Memory Usage Check
        if self.memory_watchdog_enabled:
            import os
            
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            self._watchdog_state["memory_usage_mb"] = round(memory_mb, 2)
            
            # Get system total memory
            system_memory = psutil.virtual_memory()
            memory_percent = memory_info.rss / system_memory.total * 100
            
            self._watchdog_state["memory_usage_pct"] = round(memory_percent, 2)
            
            # Import metrics collector for recording
            try:
                from app.monitoring.prometheus_metrics import get_metrics_collector
                metrics = get_metrics_collector()
                metrics.update_watchdog_health(
                    watchdog_type="memory",
                    health_score=max(0, 1.0 - (memory_percent / 100.0))
                )
            except ImportError:
                pass  # Metrics not available in test environment
            
            if memory_percent > self.memory_critical_pct:
                severity = CircuitBreakerLevel.CRITICAL
                issues.append({
                    "type": "memory_watchdog",
                    "severity": severity.value,
                    "message": f"Memory usage critical: {memory_mb:.1f}MB ({memory_percent:.1f}% of system)",
                    "recommendation": "Restart application to prevent OOM"
                })
                actions.append({"action": "schedule_restart", "reason": "memory_critical"})
                
                # Auto-restart if enabled
                if self.memory_auto_restart_enabled:
                    logger.critical(f"🚨 CRITICAL: Memory usage {memory_percent:.1f}% exceeds threshold {self.memory_critical_pct}% - triggering auto-restart")
                    self._watchdog_state["auto_restart_triggered"] = True
                    
                    # Schedule restart after current operations complete
                    import asyncio
                    asyncio.create_task(self._schedule_auto_restart(delay_seconds=10))
                    
            elif memory_percent > self.memory_warning_pct:
                severity = CircuitBreakerLevel.DEGRADED
                issues.append({
                    "type": "memory_watchdog",
                    "severity": severity.value,
                    "message": f"Memory usage elevated: {memory_mb:.1f}MB ({memory_percent:.1f}% of system)",
                    "recommendation": "Monitor memory growth"
                })
            
            if severity.value > max_severity.value:
                max_severity = severity
        
        # Watchdog 4: Queue Depth Check (if applicable)
        if self.queue_watchdog_enabled:
            # This would check task queue depth in production systems
            # For now, we'll track it but implementation depends on your queue system
            queue_depth = self._watchdog_state.get("queue_depth", 0)
            
            if queue_depth > 100:
                severity = CircuitBreakerLevel.CRITICAL
                issues.append({
                    "type": "queue_watchdog",
                    "severity": severity.value,
                    "message": f"Task queue depth critical: {queue_depth} pending tasks",
                    "recommendation": "Scale workers or investigate bottlenecks"
                })
            elif queue_depth > 50:
                severity = CircuitBreakerLevel.DEGRADED
                issues.append({
                    "type": "queue_watchdog",
                    "severity": severity.value,
                    "message": f"Task queue depth elevated: {queue_depth} pending tasks",
                    "recommendation": "Monitor queue processing rate"
                })
            
            if severity.value > max_severity.value:
                max_severity = severity
        
        # Return decision with highest severity level
        can_continue = max_severity != CircuitBreakerLevel.EMERGENCY
        status = f"watchdog_{max_severity.value.lower()}" if issues else "watchdog_healthy"
        
        return HealingDecision(
            can_continue=can_continue,
            status=status,
            issues=issues,
            actions=actions,
            circuit_breaker_level=max_severity if issues else None,
            metadata={"watchdog_state": self._watchdog_state.copy()}
        )

    def should_pause_for_anomalies(self, anomalies: List[Dict[str, Any]]) -> bool:
        """Return True when anomaly severities require trading to pause."""
        return any(anomaly.get("severity") in self.critical_anomaly_severities for anomaly in anomalies)

    async def get_health_report(self) -> Dict[str, Any]:
        """Return consolidated engine telemetry suitable for an API response."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "anomaly_detection": {
                "baselines": self.anomaly_detector.get_baseline_stats(),
                "alerts_triggered": dict(self.anomaly_detector.alert_counts),
            },
            "deduplication": await self.dedup_engine.get_stats(),
            "last_recovery": self._last_recovery,
            "watchdogs": {
                "enabled": {
                    "api": self.api_watchdog_enabled,
                    "database": self.db_watchdog_enabled,
                    "memory": self.memory_watchdog_enabled,
                    "queue": self.queue_watchdog_enabled,
                },
                "state": self._watchdog_state.copy(),
            },
        }
        if self.circuit_breaker:
            report["circuit_breaker"] = self._serialize_health_state(
                await self.circuit_breaker.check_system_health()
            )
        return report

    def _calculate_slippage(self, proposal: Dict[str, Any], execution_result: Dict[str, Any]) -> Optional[float]:
        expected_price = proposal.get("entry_price")
        filled_price = execution_result.get("filled_price", execution_result.get("price", expected_price))
        if not expected_price or not filled_price:
            return None
        return abs(filled_price - expected_price) / expected_price * 100

    def _serialize_health_state(self, health_state: Any) -> Any:
        if isinstance(health_state, dict):
            return health_state
        if hasattr(health_state, "to_dict"):
            return health_state.to_dict()
        return {
            key: getattr(health_state, key)
            for key in ("can_trade", "reason", "state")
            if hasattr(health_state, key)
        }

    def _normalize_issue(self, issue: Any, default_type: str) -> Dict[str, Any]:
        if isinstance(issue, dict):
            return issue
        return {"type": default_type, "message": str(issue)}

    async def _publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self.event_bus:
            return
        try:
            publish_result = self.event_bus.publish(event_type, payload)
            if inspect.isawaitable(publish_result):
                await publish_result
        except Exception as exc:
            logger.warning("Failed to publish self-healing event %s: %s", event_type, exc)
    
    async def _schedule_auto_restart(self, delay_seconds: int = 10) -> None:
        """
        Schedule automatic application restart after delay.
        
        This allows current operations to complete before restarting.
        Uses os.execv to replace the current process with a new instance.
        
        Args:
            delay_seconds: Seconds to wait before restarting (default: 10)
        """
        import os
        import sys
        import asyncio
        
        logger.warning(f"⚠️  Auto-restart scheduled in {delay_seconds} seconds due to critical memory usage")
        
        # Wait for delay
        await asyncio.sleep(delay_seconds)
        
        # Log restart
        logger.critical("🔄 Initiating automatic restart...")
        
        # Send final notification if notifier available
        if self.notifier:
            try:
                await self.notifier.send_message(
                    "🚨 <b>CRITICAL:</b> Auto-restart triggered due to memory pressure.\n"
                    f"Memory usage exceeded {self.memory_critical_pct}% threshold.\n"
                    "Application will restart automatically."
                )
            except Exception as e:
                logger.error(f"Failed to send restart notification: {e}")
        
        # Get current executable and arguments
        python_executable = sys.executable
        script_path = sys.argv[0] if sys.argv else "-m app.main"
        
        # If running as module, reconstruct command
        if "-m" in sys.argv:
            args = [python_executable, "-m", "app.main"]
        else:
            args = [python_executable, script_path] + sys.argv[1:]
        
        logger.info(f"Restarting with: {' '.join(args)}")
        
        # Replace current process
        os.execv(python_executable, args)
