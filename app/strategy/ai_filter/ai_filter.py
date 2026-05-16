"""
AI Filter - Regime classifier for XAUUSDT signals using Claude.

Architecture: Signal → Risk Validation → AI Filter → Execution Gate
(Risk runs first to avoid wasting tokens on invalid signals)
"""
import asyncio
import json
import math
from enum import Enum
from typing import Dict, Any, Optional

import anthropic

from app.config import settings
from app.strategy.signal_proposal import SignalProposal
from app.logging_config import get_logger

logger = get_logger(__name__)


class Regime(str, Enum):
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    HOSTILE = "hostile"
    AVOID = "avoid"


REGIME_MULTIPLIERS = {
    Regime.SUPPORTIVE: 1.1,
    Regime.NEUTRAL: 1.0,
    Regime.HOSTILE: 0.85,
    Regime.AVOID: 0.0,
}

CONFIDENCE_FLOOR = 0.30
CONFIDENCE_CEILING = 1.0
DECAY_K = 0.15
AI_TIMEOUT_SECONDS = 1.2


class AIFilter:
    """Regime classifier: validates signals via Claude with hard timeout and fallback."""

    def __init__(self, min_confidence_threshold: float = 0.6):
        self.min_confidence_threshold = min_confidence_threshold
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"
        self.system_prompt = self._build_system_prompt()
        self.consecutive_signals: Dict[str, int] = {"LONG": 0, "SHORT": 0}
        self.last_signal_side: Optional[str] = None
        logger.info("✅ AIFilter initialized (regime classifier, model=%s)", self.model)

    def _build_system_prompt(self) -> str:
        return (
            "You classify XAUUSDT market conditions into regimes.\n\n"
            "Evaluate ONLY:\n"
            "- Session alignment (is signal appropriate for active session?)\n"
            "- DXY alignment (is USD strength supporting signal direction?)\n"
            "- News safety (major economic events within 45min?)\n"
            "- Liquidity quality (is the liquidity regime solid?)\n"
            "- Volume confirmation (is volume supporting the move?)\n\n"
            "Return ONLY valid JSON. No explanations. No reasoning.\n"
            'Response format: {"regime":"supportive|neutral|hostile|avoid","multiplier":1.1|1.0|0.85|0.0}'
        )

    def _build_regime_prompt(self, signal: SignalProposal, market_context: Dict[str, Any]) -> str:
        return json.dumps({
            "sig": signal.side.upper(),
            "conf": round(signal.confidence, 2),
            "strat": signal.strategy_name,
            "m": {
                "s": self._session_to_code(market_context.get("session")),
                "d": self._dxy_trend_to_code(market_context.get("dxy_trend", "flat")),
                "n": market_context.get("news_events", 0),
                "v": self._volume_to_code(market_context.get("volume_state", "normal")),
                "l": market_context.get("liquidity_state", "normal"),
                "vol": market_context.get("volatility_regime", "stable"),
            },
        })

    def _session_to_code(self, session: Optional[str]) -> str:
        return {"london_open": "LO", "london_close": "LC", "ny_open": "NO", "ny_close": "NC", "dead": "D"}.get(
            session or "dead", "D"
        )

    def _dxy_trend_to_code(self, trend: str) -> str:
        return {"up": "UP", "down": "DN", "flat": "F"}.get(trend.lower(), "F")

    def _volume_to_code(self, volume: str) -> str:
        return {"low": "L", "normal": "N", "high": "H"}.get(volume.lower(), "N")

    async def _call_claude_regime(self, signal: SignalProposal, market_context: Dict[str, Any]) -> str:
        user_prompt = self._build_regime_prompt(signal, market_context)
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[{"role": "user", "content": user_prompt}],
                system=self.system_prompt,
                temperature=0,
            ),
        )
        return response.content[0].text

    def _update_signal_tracking(self, signal_side: str) -> None:
        if signal_side == self.last_signal_side:
            self.consecutive_signals[signal_side] = self.consecutive_signals.get(signal_side, 0) + 1
        else:
            self.consecutive_signals[signal_side] = 1
            self.last_signal_side = signal_side

    def reset_signal_tracking(self, signal_side: str) -> None:
        """Call after trade execution to reset decay counter."""
        self.consecutive_signals[signal_side] = 0

    async def validate_signal(
        self, signal: SignalProposal, market_context: Dict[str, Any]
    ) -> Optional[SignalProposal]:
        """
        Classify market regime and adjust signal confidence.

        NOTE: Risk validation must run BEFORE calling this method.
        This filter only runs on signals that already passed risk checks.

        Returns adjusted signal, or None if regime is 'avoid'.
        """
        if signal.confidence < self.min_confidence_threshold:
            logger.info("Signal rejected pre-AI: confidence %.2f below threshold", signal.confidence)
            return None

        base_confidence = signal.confidence
        regime = Regime.NEUTRAL
        multiplier = REGIME_MULTIPLIERS[Regime.NEUTRAL]

        try:
            raw = await asyncio.wait_for(
                self._call_claude_regime(signal, market_context),
                timeout=AI_TIMEOUT_SECONDS,
            )
            data = json.loads(raw)
            regime = Regime(data.get("regime", "neutral"))
            multiplier = REGIME_MULTIPLIERS.get(regime, 1.0)
            logger.info("AI regime: %s (multiplier=%.2f)", regime.value, multiplier)

        except asyncio.TimeoutError:
            logger.warning("AI timeout (>%.1fs); falling back to neutral regime", AI_TIMEOUT_SECONDS)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error("AI parse error: %s; falling back to neutral regime", e)

        if regime == Regime.AVOID:
            logger.info("Signal rejected: regime=avoid")
            signal.metadata["regime"] = regime.value
            signal.metadata["multiplier"] = 0.0
            return None

        # Apply regime multiplier
        adjusted = base_confidence * multiplier

        # Apply consecutive-signal decay
        self._update_signal_tracking(signal.side.upper())
        consecutive = self.consecutive_signals.get(signal.side.upper(), 1)
        decay = math.exp(-DECAY_K * (consecutive - 1))
        adjusted *= decay

        # Clamp
        adjusted = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, adjusted))

        signal.confidence = round(adjusted, 4)
        signal.metadata["regime"] = regime.value
        signal.metadata["multiplier"] = multiplier
        signal.metadata["base_confidence"] = base_confidence
        signal.metadata["consecutive_signals"] = consecutive

        logger.info(
            "Signal validated: conf %.2f → %.2f (regime=%s, decay=%.3f)",
            base_confidence, signal.confidence, regime.value, decay,
        )
        return signal
