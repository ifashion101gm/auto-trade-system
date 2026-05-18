"""
AI Filter — XAUUSDT trade signal execution gate (Enterprise v2).

Architecture: Signal → Risk Validation → AI Filter → Execution Gate
(Risk runs first to avoid wasting LLM tokens on already-rejected signals)

v2 changes:
- System prompt imported from app.llm.prompts (AI_FILTER_SYSTEM)
- User prompt built via build_ai_filter_context() for richer, compact JSON context
- Model: claude-haiku-4-5-20251001 (fast, cheap, deterministic JSON)
- Prompt-cache headers applied automatically via LLMClient
"""
import asyncio
import json
import math
import re
from enum import Enum
from typing import Dict, Any, Optional

from app.config import settings
from app.llm.openrouter_client import OpenRouterClient
from app.llm.prompts import AI_FILTER_SYSTEM, build_ai_filter_context
from app.strategy.signal_proposal import SignalProposal
from app.logging_config import get_logger

logger = get_logger(__name__)

# Import Prometheus metrics from main module
try:
    from app.main import LLM_TOKEN_USAGE_TOTAL, AI_CONFIDENCE_SCORES
except ImportError:
    # Fallback if metrics not available
    LLM_TOKEN_USAGE_TOTAL = None
    AI_CONFIDENCE_SCORES = None

# In-process counters (reset on restart; use AIEdgeTracker for persistence)
_parse_error_count: int = 0
_timeout_count: int = 0
_call_count: int = 0

_SCHEMA_RE = re.compile(r'\{[^{}]*"regime"[^{}]*\}', re.DOTALL)
_VALID_REGIMES = {"supportive", "neutral", "hostile", "avoid"}


class Regime(str, Enum):
    SUPPORTIVE = "supportive"
    NEUTRAL    = "neutral"
    HOSTILE    = "hostile"
    AVOID      = "avoid"


REGIME_MULTIPLIERS: Dict[Regime, float] = {
    Regime.SUPPORTIVE: 1.1,
    Regime.NEUTRAL:    1.0,
    Regime.HOSTILE:    0.85,
    Regime.AVOID:      0.0,
}

CONFIDENCE_FLOOR   = 0.30
CONFIDENCE_CEILING = 1.0
DECAY_K            = 0.15
AI_TIMEOUT_SECONDS = getattr(settings, "AI_FILTER_TIMEOUT_SECONDS", 1.5)


class AIFilter:
    """
    Regime classifier: validates XAUUSDT signals via OpenRouter
    (anthropic/claude-sonnet-4-20250514).

    All calls go through OpenRouterClient which provides:
    - Cost tracking + spend-cap enforcement (SpendTracker)
    - Provider fallback (OpenRouter → direct OpenAI → heuristic)
    - Unified API key management (OPENROUTER_API_KEY)
    """

    def __init__(self, min_confidence_threshold: float = 0.6,
                 openrouter_client: Optional[OpenRouterClient] = None):
        self.min_confidence_threshold = min_confidence_threshold
        try:
            self._client = openrouter_client or OpenRouterClient()
            self._available = True
        except Exception as e:
            logger.warning("AIFilter: OpenRouterClient unavailable (%s) — rule-based fallback only", e)
            self._client = None
            self._available = False

        self.system_prompt = self._build_system_prompt()
        self.consecutive_signals: Dict[str, int] = {"LONG": 0, "SHORT": 0}
        self.last_signal_side: Optional[str] = None
        logger.info(
            "✅ AIFilter initialised (gateway=openrouter model=anthropic/claude-sonnet-4-20250514 available=%s)",
            self._available,
        )

    # ── Prompt builders ──────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        # Enterprise system prompt — imported from prompts.py (static → cached by Anthropic)
        return AI_FILTER_SYSTEM

    def _build_regime_prompt(self, signal: SignalProposal, market_context: Dict[str, Any]) -> str:
        # Build compact, structured context using the enterprise template helper
        news_flag = bool(market_context.get("news_events", 0))
        return build_ai_filter_context(
            side=signal.side.upper(),
            confidence=signal.confidence,
            strategy=signal.strategy_name,
            session_code=self._session_to_code(market_context.get("session")),
            dxy_code=self._dxy_trend_to_code(market_context.get("dxy_trend", "flat")),
            news_flag=news_flag,
            volume_code=self._volume_to_code(market_context.get("volume_state", "normal")),
            liquidity_state=market_context.get("liquidity_state", "normal"),
            spread_pct=float(market_context.get("spread_pct", 0.05)),
            vol_regime=market_context.get("volatility_regime", "stable"),
        )

    def _session_to_code(self, session: Optional[str]) -> str:
        return {"london_open": "LO", "london_close": "LC",
                "ny_open": "NO", "ny_close": "NC", "dead": "D"}.get(session or "dead", "D")

    def _dxy_trend_to_code(self, trend: str) -> str:
        return {"up": "UP", "down": "DN", "flat": "F"}.get(trend.lower(), "F")

    def _volume_to_code(self, volume: str) -> str:
        return {"low": "L", "normal": "N", "high": "H"}.get(volume.lower(), "N")

    # ── OpenRouter call ───────────────────────────────────────────────────────

    async def _call_openrouter_regime(
        self, signal: SignalProposal, market_context: Dict[str, Any]
    ) -> str:
        """Call OpenRouter classify_regime; returns raw JSON string."""
        user_prompt = self._build_regime_prompt(signal, market_context)
        return await self._client.classify_regime(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
        )

    # ── Signal tracking ───────────────────────────────────────────────────────

    def _update_signal_tracking(self, signal_side: str) -> None:
        if signal_side == self.last_signal_side:
            self.consecutive_signals[signal_side] = self.consecutive_signals.get(signal_side, 0) + 1
        else:
            self.consecutive_signals[signal_side] = 1
            self.last_signal_side = signal_side

    def reset_signal_tracking(self, signal_side: str) -> None:
        """Call after trade execution to reset decay counter."""
        self.consecutive_signals[signal_side] = 0

    # ── Main entry point ──────────────────────────────────────────────────────

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
        regime     = Regime.NEUTRAL
        multiplier = REGIME_MULTIPLIERS[Regime.NEUTRAL]

        if self._available:
            global _parse_error_count, _timeout_count, _call_count
            _call_count += 1
            raw: Optional[str] = None
            try:
                raw = await asyncio.wait_for(
                    self._call_openrouter_regime(signal, market_context),
                    timeout=AI_TIMEOUT_SECONDS,
                )
                parsed = self._parse_regime_response(raw)
                if parsed is None:
                    raise ValueError(f"schema validation failed; raw={raw!r}")
                regime     = Regime(parsed["regime"])
                multiplier = REGIME_MULTIPLIERS.get(regime, 1.0)
                logger.info("AI regime: %s (multiplier=%.2f)", regime.value, multiplier)

            except asyncio.TimeoutError:
                _timeout_count += 1
                logger.warning(
                    "AI timeout (>%.1fs); falling back to neutral [timeouts=%d/%d]",
                    AI_TIMEOUT_SECONDS, _timeout_count, _call_count,
                )
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                _parse_error_count += 1
                logger.error(
                    "AI parse error: %s; raw=%r [parse_errors=%d/%d]",
                    e, raw, _parse_error_count, _call_count,
                )
        else:
            logger.debug("AIFilter: no client — rule-based fallback")
            return self._rule_based_fallback(signal, market_context)

        if regime == Regime.AVOID:
            logger.info("Signal rejected: regime=avoid")
            signal.metadata["regime"]     = regime.value
            signal.metadata["multiplier"] = 0.0
            return None

        # Apply regime multiplier
        adjusted = base_confidence * multiplier

        # Apply consecutive-signal decay
        self._update_signal_tracking(signal.side.upper())
        consecutive = self.consecutive_signals.get(signal.side.upper(), 1)
        decay       = math.exp(-DECAY_K * (consecutive - 1))
        adjusted   *= decay

        # Clamp
        adjusted = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, adjusted))

        signal.confidence              = round(adjusted, 4)
        signal.metadata["regime"]      = regime.value
        signal.metadata["multiplier"]  = multiplier
        signal.metadata["base_confidence"]    = base_confidence
        signal.metadata["consecutive_signals"] = consecutive

        # Update Prometheus metrics
        if AI_CONFIDENCE_SCORES:
            AI_CONFIDENCE_SCORES.labels(agent_type="ai_filter").observe(adjusted)

        logger.info(
            "Signal validated: conf %.2f → %.2f (regime=%s decay=%.3f)",
            base_confidence, signal.confidence, regime.value, decay,
        )
        return signal

    # ── Response parser ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_regime_response(raw: str) -> Optional[Dict[str, Any]]:
        """
        Defensive JSON parse with regex fallback.
        1. Try json.loads on the full string.
        2. If that fails, extract the first {...} block containing "regime" and retry.
        3. Validate that regime is one of the 4 known values.
        Returns None if all attempts fail.
        """
        def _validate(data: Dict) -> Optional[Dict]:
            r = data.get("regime", "")
            if r in _VALID_REGIMES:
                return {"regime": r, "multiplier": float(data.get("multiplier", 1.0))}
            return None

        try:
            return _validate(json.loads(raw))
        except (json.JSONDecodeError, AttributeError):
            pass

        # Regex extraction: find first {...} block containing "regime"
        m = _SCHEMA_RE.search(raw or "")
        if m:
            try:
                return _validate(json.loads(m.group()))
            except (json.JSONDecodeError, ValueError):
                pass
        return None

    @staticmethod
    def get_counters() -> Dict[str, int]:
        """Return live parse_error / timeout / call counters."""
        return {
            "parse_errors": _parse_error_count,
            "timeouts": _timeout_count,
            "calls": _call_count,
        }

    # ── Rule-based fallback (no LLM available) ────────────────────────────────

    def _rule_based_fallback(
        self, signal: SignalProposal, market_context: Dict[str, Any]
    ) -> Optional[SignalProposal]:
        """Minimal rule-based validation when OpenRouter is unavailable."""
        liquidity = market_context.get("liquidity_state", "normal")
        news      = market_context.get("news_events", 0)
        session   = market_context.get("session", "dead")

        if news > 0 or liquidity == "thin" or session == "dead":
            regime, multiplier = Regime.HOSTILE, REGIME_MULTIPLIERS[Regime.HOSTILE]
        else:
            regime, multiplier = Regime.NEUTRAL, REGIME_MULTIPLIERS[Regime.NEUTRAL]

        adjusted = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, signal.confidence * multiplier))
        signal.confidence             = round(adjusted, 4)
        signal.metadata["regime"]     = regime.value
        signal.metadata["multiplier"] = multiplier
        signal.metadata["base_confidence"] = signal.confidence
        signal.metadata["rule_fallback"]   = True
        return signal
