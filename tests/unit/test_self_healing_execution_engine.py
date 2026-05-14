"""Unit tests for the self-healing execution engine."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.execution.self_healing_engine import SelfHealingExecutionEngine


def test_preflight_blocks_when_circuit_breaker_disallows_trading():
    async def scenario():
        circuit_breaker = AsyncMock()
        circuit_breaker.check_system_health.return_value = SimpleNamespace(
            can_trade=False,
            reason="API failure rate too high",
            state="open",
        )
        monitoring_agent = AsyncMock()
        monitoring_agent.run.return_value = {"can_continue_trading": True, "issues": []}

        engine = SelfHealingExecutionEngine(
            monitoring_agent=monitoring_agent,
            circuit_breaker=circuit_breaker,
            event_bus=None,
        )

        decision = await engine.run_preflight({"user_id": "test"})

        assert decision.can_continue is False
        assert decision.status == "blocked_by_self_healing"
        assert decision.issues[0]["type"] == "circuit_breaker_open"
        assert decision.metadata["circuit_breaker"]["reason"] == "API failure rate too high"

    asyncio.run(scenario())


def test_guard_signal_rejects_duplicate_signal():
    async def scenario():
        engine = SelfHealingExecutionEngine(event_bus=None)
        proposal = {
            "symbol": "BTC/USDT",
            "side": "BUY",
            "entry_price": 50000.0,
            "quantity": 0.01,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            "leverage": 1,
        }

        first = await engine.guard_signal(proposal)
        second = await engine.guard_signal(proposal)

        assert first.can_continue is True
        assert first.status == "signal_accepted"
        assert second.can_continue is False
        assert second.status == "duplicate_signal_rejected"
        assert second.issues[0]["type"] == "duplicate_signal"

    asyncio.run(scenario())


def test_execute_with_observation_records_order_and_metrics():
    async def scenario():
        circuit_breaker = AsyncMock()
        engine = SelfHealingExecutionEngine(circuit_breaker=circuit_breaker, event_bus=None)
        proposal = {"symbol": "ETH/USDT", "side": "BUY", "entry_price": 3000.0}

        async def operation():
            return {
                "status": "executed",
                "order_id": "order-123",
                "filled_price": 3003.0,
                "price": 3003.0,
            }

        result = await engine.execute_with_observation(operation, proposal=proposal)

        assert result["_self_healing_latency_ms"] >= 0
        assert result["_self_healing_anomalies"] == []
        assert await engine.dedup_engine.is_duplicate_order("order-123") is True
        assert engine.anomaly_detector.order_results[-1] is True
        circuit_breaker.record_api_call.assert_awaited_once()
        circuit_breaker.record_fill_slippage.assert_awaited_once()

    asyncio.run(scenario())


def test_verification_failure_triggers_recovery_agent():
    async def scenario():
        verification_agent = AsyncMock()
        verification_agent.run.return_value = {
            "verification_passed": False,
            "checks": {"exchange_order": "missing"},
        }
        recovery_agent = AsyncMock()
        recovery_agent.run.return_value = {
            "success": True,
            "actions_taken": [{"action": "full_recovery", "success": True}],
        }
        engine = SelfHealingExecutionEngine(
            verification_agent=verification_agent,
            recovery_agent=recovery_agent,
            event_bus=None,
        )

        decision = await engine.verify_and_recover(
            execution_result={"order_id": "missing-order"},
            proposal={"symbol": "BTC/USDT"},
            context={"user_id": "test"},
        )

        assert decision.can_continue is True
        assert decision.status == "verification_failed_recovered"
        assert decision.issues[0]["type"] == "verification_failed"
        recovery_agent.run.assert_awaited_once()

    asyncio.run(scenario())
