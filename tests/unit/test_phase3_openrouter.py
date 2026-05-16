"""Unit tests for Phase 3: OpenRouter-backed AIFilter and micro-live guard."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.strategy.ai_filter.ai_filter import (
    AIFilter,
    CONFIDENCE_FLOOR,
    Regime,
    REGIME_MULTIPLIERS,
)
from app.strategy.signal_proposal import SignalProposal


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_signal(confidence: float = 0.75, side: str = "LONG") -> SignalProposal:
    return SignalProposal(
        symbol="XAUUSDT", side=side, entry_price=2350.0,
        stop_loss=2330.0, take_profit=2390.0, quantity=0.01,
        confidence=confidence, strategy_name="gold_opening_reversal",
    )


def _make_context(**overrides) -> dict:
    base = {
        "session": "london_open", "dxy_trend": "down",
        "news_events": 0, "volume_state": "high",
        "liquidity_state": "heavy", "volatility_regime": "stable",
    }
    base.update(overrides)
    return base


def _make_filter(regime: str = "neutral") -> AIFilter:
    """Return AIFilter with mocked OpenRouterClient."""
    multipliers = {"supportive": 1.1, "neutral": 1.0, "hostile": 0.85, "avoid": 0.0}

    async def mock_classify(system_prompt, user_prompt):
        return json.dumps({"regime": regime, "multiplier": multipliers[regime]})

    mock_client = MagicMock()
    mock_client.classify_regime = mock_classify

    with patch("app.strategy.ai_filter.ai_filter.OpenRouterClient", return_value=mock_client):
        f = AIFilter()
    return f


# ── Test 1: OpenRouter client is used (not direct Anthropic) ─────────────────

def test_ai_filter_uses_openrouter_client():
    with patch("app.strategy.ai_filter.ai_filter.OpenRouterClient") as MockOR:
        MockOR.return_value = MagicMock()
        f = AIFilter()
    assert f._client is not None
    MockOR.assert_called_once()


# ── Test 2: classify_regime called with correct prompts ──────────────────────

@pytest.mark.asyncio
async def test_classify_regime_called_with_system_and_user_prompt():
    calls = []

    async def capture(system_prompt, user_prompt):
        calls.append({"sys": system_prompt, "usr": user_prompt})
        return json.dumps({"regime": "neutral", "multiplier": 1.0})

    mock_client = MagicMock()
    mock_client.classify_regime = capture

    with patch("app.strategy.ai_filter.ai_filter.OpenRouterClient", return_value=mock_client):
        f = AIFilter()

    signal = _make_signal()
    await f.validate_signal(signal, _make_context())

    assert len(calls) == 1
    assert "supportive|neutral|hostile|avoid" in calls[0]["sys"]
    parsed = json.loads(calls[0]["usr"])
    assert "sig" in parsed and "m" in parsed


# ── Test 3: supportive regime boosts confidence ───────────────────────────────

@pytest.mark.asyncio
async def test_supportive_regime_boosts_confidence():
    f = _make_filter("supportive")
    signal = _make_signal(confidence=0.80)
    result = await f.validate_signal(signal, _make_context())
    assert result is not None
    assert result.confidence == round(0.80 * 1.1, 4)
    assert result.metadata["regime"] == "supportive"


# ── Test 4: avoid regime returns None ────────────────────────────────────────

@pytest.mark.asyncio
async def test_avoid_regime_returns_none():
    f = _make_filter("avoid")
    result = await f.validate_signal(_make_signal(), _make_context())
    assert result is None


# ── Test 5: timeout falls back to neutral ────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_falls_back_to_neutral():
    import asyncio
    mock_client = MagicMock()

    async def slow(**_):
        await asyncio.sleep(10)

    mock_client.classify_regime = slow

    with patch("app.strategy.ai_filter.ai_filter.OpenRouterClient", return_value=mock_client):
        f = AIFilter()

    result = await f.validate_signal(_make_signal(), _make_context())
    assert result is not None
    assert result.metadata["regime"] == Regime.NEUTRAL.value


# ── Test 6: rule-based fallback when client unavailable ──────────────────────

@pytest.mark.asyncio
async def test_rule_based_fallback_when_unavailable():
    with patch("app.strategy.ai_filter.ai_filter.OpenRouterClient", side_effect=Exception("no key")):
        f = AIFilter()

    assert not f._available
    # Dead session + thin liquidity → hostile
    result = await f.validate_signal(
        _make_signal(confidence=0.75),
        _make_context(session="dead", liquidity_state="thin"),
    )
    assert result is not None
    assert result.metadata["regime"] == "hostile"
    assert result.metadata.get("rule_fallback") is True


# ── Test 7: rule-based fallback blocks news events ───────────────────────────

@pytest.mark.asyncio
async def test_rule_based_fallback_news_event_hostile():
    with patch("app.strategy.ai_filter.ai_filter.OpenRouterClient", side_effect=Exception("no key")):
        f = AIFilter()

    result = await f.validate_signal(
        _make_signal(confidence=0.75),
        _make_context(news_events=1, session="london_open"),
    )
    assert result is not None
    assert result.metadata["regime"] == "hostile"


# ── Test 8: confidence floor enforced ────────────────────────────────────────

@pytest.mark.asyncio
async def test_confidence_floor_enforced():
    f = _make_filter("hostile")
    f.consecutive_signals["LONG"] = 20
    f.last_signal_side = "LONG"
    result = await f.validate_signal(_make_signal(confidence=0.65), _make_context())
    assert result is not None
    assert result.confidence >= CONFIDENCE_FLOOR


# ── Test 9: micro-live guard blocks execution when disabled ──────────────────

@pytest.mark.asyncio
async def test_micro_live_guard_blocks_when_disabled():
    from app.config import settings as real_settings
    with patch.object(real_settings, "MICRO_LIVE_ENABLED", False):
        from app.execution import trading_service as ts_module

        class _StubService:
            exchange_name = "bybit"
            use_testnet = True
            execution_mode = "semi-auto"
            allowed_symbols = ["XAUUSDT"]
            symbol_locks: dict = {}
            current_state = MagicMock()
            state_history: list = []

            def _validate_symbol_allowed(self, symbol):
                return True

            async def _transition_to(self, state):
                pass

        svc = _StubService()
        result = await ts_module.LiveTradingService.execute_trading_cycle(
            svc, symbol="XAUUSDT"
        )

    assert result["status"] == "micro_live_disabled"


# ── Test 10: model name in MODEL_MAPPING is correct ──────────────────────────

def test_openrouter_model_mapping_has_claude_sonnet():
    from app.llm.openrouter_client import OpenRouterClient
    mapping = OpenRouterClient.MODEL_MAPPING
    assert "regime_classification" in mapping
    assert mapping["regime_classification"]["model"] == "anthropic/claude-sonnet-4-20250514"
    assert mapping["regime_classification"]["max_tokens"] == 100
    assert mapping["regime_classification"]["temperature"] == 0
