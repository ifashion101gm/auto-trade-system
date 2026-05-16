"""Unit tests for AI regime filter (Phase 1)."""
import asyncio
import json
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.strategy.ai_filter.ai_filter import (
    AIFilter,
    CONFIDENCE_FLOOR,
    DECAY_K,
    Regime,
    REGIME_MULTIPLIERS,
)
from app.strategy.signal_proposal import SignalProposal


def _make_signal(confidence: float = 0.75, side: str = "LONG") -> SignalProposal:
    return SignalProposal(
        symbol="XAUUSDT",
        side=side,
        entry_price=2350.0,
        stop_loss=2330.0,
        take_profit=2390.0,
        quantity=0.01,
        confidence=confidence,
        strategy_name="gold_opening_reversal",
    )


def _make_context() -> dict:
    return {
        "session": "london_open",
        "dxy_trend": "down",
        "news_events": 0,
        "volume_state": "high",
        "liquidity_state": "heavy",
        "volatility_regime": "stable",
    }


@pytest.fixture
def ai_filter():
    with patch("app.strategy.ai_filter.ai_filter.OpenRouterClient"):
        f = AIFilter()
        return f


# ── Test 1: system prompt ────────────────────────────────────────────────────

def test_system_prompt_generation(ai_filter):
    prompt = ai_filter.system_prompt
    assert "supportive|neutral|hostile|avoid" in prompt
    assert "multiplier" in prompt
    assert "JSON" in prompt


# ── Test 2: regime prompt compression ────────────────────────────────────────

def test_regime_prompt_compression(ai_filter):
    signal = _make_signal()
    ctx = _make_context()
    prompt = ai_filter._build_regime_prompt(signal, ctx)
    data = json.loads(prompt)          # must be valid JSON
    assert "sig" in data
    assert "m" in data
    assert data["m"]["s"] == "LO"      # london_open → LO
    assert data["m"]["d"] == "DN"      # down → DN
    # Token estimate: len(prompt) / 4 < 150
    assert len(prompt) / 4 < 150, f"Prompt too long: {len(prompt)} chars"


# ── Test 3: hard timeout fallback ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hard_timeout_fallback(ai_filter):
    async def slow_call(*_):
        await asyncio.sleep(10)

    with patch.object(ai_filter, "_call_openrouter_regime", side_effect=slow_call):
        signal = _make_signal()
        result = await ai_filter.validate_signal(signal, _make_context())

    # Should not raise; should return signal with neutral regime
    assert result is not None
    assert result.metadata["regime"] == Regime.NEUTRAL.value
    assert result.metadata["multiplier"] == 1.0


# ── Test 4: confidence multiplier ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confidence_multiplier(ai_filter):
    base = 0.80
    signal = _make_signal(confidence=base)

    async def mock_call(*_):
        return json.dumps({"regime": "supportive", "multiplier": 1.1})

    with patch.object(ai_filter, "_call_openrouter_regime", side_effect=mock_call):
        result = await ai_filter.validate_signal(signal, _make_context())

    assert result is not None
    # First signal → no decay (consecutive=1, decay=exp(0)=1.0)
    expected = round(base * 1.1, 4)
    assert result.confidence == expected


# ── Test 5: confidence decay ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confidence_decay(ai_filter):
    async def mock_neutral(*_):
        return json.dumps({"regime": "neutral", "multiplier": 1.0})

    confidences = []
    for _ in range(3):
        signal = _make_signal(confidence=0.75, side="LONG")
        with patch.object(ai_filter, "_call_openrouter_regime", side_effect=mock_neutral):
            result = await ai_filter.validate_signal(signal, _make_context())
        confidences.append(result.confidence)

    # Each successive signal should be lower (decay applied)
    assert confidences[0] >= confidences[1] >= confidences[2]


# ── Test 6: confidence floor ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confidence_floor(ai_filter):
    signal = _make_signal(confidence=0.65)

    async def mock_hostile(*_):
        return json.dumps({"regime": "hostile", "multiplier": 0.85})

    # Pump consecutive count high to force heavy decay
    ai_filter.consecutive_signals["LONG"] = 20
    ai_filter.last_signal_side = "LONG"

    with patch.object(ai_filter, "_call_openrouter_regime", side_effect=mock_hostile):
        result = await ai_filter.validate_signal(signal, _make_context())

    assert result is not None
    assert result.confidence >= CONFIDENCE_FLOOR


# ── Test 7: avoid regime returns None ────────────────────────────────────────

@pytest.mark.asyncio
async def test_avoid_regime_returns_none(ai_filter):
    signal = _make_signal()

    async def mock_avoid(*_):
        return json.dumps({"regime": "avoid", "multiplier": 0.0})

    with patch.object(ai_filter, "_call_openrouter_regime", side_effect=mock_avoid):
        result = await ai_filter.validate_signal(signal, _make_context())

    assert result is None


# ── Test 8: malformed JSON fallback ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_malformed_json_fallback(ai_filter):
    signal = _make_signal()

    async def mock_bad(*_):
        return "not valid json {{{"

    with patch.object(ai_filter, "_call_openrouter_regime", side_effect=mock_bad):
        result = await ai_filter.validate_signal(signal, _make_context())

    assert result is not None
    assert result.metadata["regime"] == Regime.NEUTRAL.value
