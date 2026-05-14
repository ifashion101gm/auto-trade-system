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
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.execution.anomaly_detector import AnomalyDetector
from app.execution.dedup_engine import DuplicateProtectionEngine
from app.events.event_types import RECOVERY_ACTION_TAKEN, RECOVERY_COMPLETED, RECOVERY_STARTED

logger = logging.getLogger(__name__)


@dataclass
class HealingDecision:
    """Outcome returned by self-healing gates and recovery actions."""

    can_continue: bool
    status: str
    issues: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the decision for API responses and logs."""
        return {
            "can_continue": self.can_continue,
            "status": self.status,
            "issues": self.issues,
            "actions": self.actions,
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
