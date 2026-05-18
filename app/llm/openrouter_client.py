"""
LLM Client — Enterprise v2 (Anthropic Direct).

Provides all AI sub-agent inference using the Anthropic SDK directly.
Replaces the former OpenRouter gateway while keeping the same public interface.

Model tier strategy (cost vs. performance):
  T1 claude-haiku-4-5-20251001   — fast, cheap, deterministic JSON classification
                                   (~$0.80/$4.00 per 1M input/output tokens)
                                   Used for: regime classification, strategy selection, AI filter
  T2 claude-sonnet-4-6           — balanced reasoning and quality
                                   (~$3.00/$15.00 per 1M input/output tokens)
                                   Used for: risk assessment, smart-routing escalation

Prompt-caching savings (Anthropic ephemeral cache, 5-min TTL):
  Static system prompts are marked cache_control=ephemeral → ~90 % input-token cost reduction
  on repeated calls with the same system prompt (applies to Haiku and Sonnet).

Public interface (backward-compatible):
  classify_regime(system_prompt, user_prompt) → raw JSON str  [AI filter gate]
  detect_regime(market_data)                  → regime str    [orchestrator]
  select_strategy(market_data, regime)        → dict          [orchestrator]
  assess_risk(position, market_data)          → dict          [orchestrator]
  smart_routing_assessment(...)               → dict          [orchestrator escalation]
  test_connection()                           → bool
"""
from __future__ import annotations

import json
import time
import hashlib
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

import anthropic

from app.config import settings
from app.logging_config import get_logger
from app.llm.prompts import (
    PROMPTS_VERSION,
    REGIME_DETECTION_SYSTEM, build_regime_context,
    STRATEGY_SELECTION_SYSTEM, build_strategy_context,
    RISK_ASSESSMENT_SYSTEM,
    AI_FILTER_SYSTEM,
    SMART_ROUTING_SYSTEM, build_smart_routing_context,
)

logger = get_logger(__name__)

# ── Model IDs ─────────────────────────────────────────────────────────────────
_HAIKU = "claude-haiku-4-5-20251001"   # T1: fast / cheap
_SONNET = "claude-sonnet-4-6"          # T2: balanced quality/cost

# ── Cost estimates per 1M tokens (USD) ────────────────────────────────────────
_COST_TABLE: Dict[str, Dict[str, float]] = {
    _HAIKU:  {"input": 0.80,  "output": 4.00,  "cache_write": 1.00, "cache_read": 0.08},
    _SONNET: {"input": 3.00,  "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
}

_JSON_RE = re.compile(r'\{[^{}]+\}', re.DOTALL)


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """Try json.loads; fall back to first {...} block via regex."""
    try:
        return json.loads(raw.strip())
    except (json.JSONDecodeError, AttributeError):
        pass
    m = _JSON_RE.search(raw or "")
    if m:
        try:
            return json.loads(m.group())
        except (json.JSONDecodeError, ValueError):
            pass
    return None


class OpenRouterClient:
    """
    Anthropic-backed LLM client.

    Name kept as OpenRouterClient for backward compatibility with existing imports.
    Internally uses anthropic.AsyncAnthropic with prompt-cache headers.
    """

    # ── Tiered model config ───────────────────────────────────────────────────
    MODEL_MAPPING: Dict[str, Dict[str, Any]] = {
        # AI filter gate — deterministic JSON, hard 80-token cap
        "regime_classification": {
            "model": _HAIKU,
            "max_tokens": 80,
            "temperature": 0.0,
        },
        # Regime detection — Tier 1 fast classification
        "regime_detection": {
            "model": _HAIKU,
            "max_tokens": 150,
            "temperature": 0.0,
        },
        # Strategy selection — Tier 1 balanced
        "strategy_selection": {
            "model": _HAIKU,
            "max_tokens": 200,
            "temperature": 0.1,
        },
        # Risk assessment — Tier 2 (position sizing needs careful reasoning)
        "risk_assessment": {
            "model": _SONNET,
            "max_tokens": 300,
            "temperature": 0.0,
        },
        # Escalation / smart routing — Tier 2 premium
        "smart_routing": {
            "model": _SONNET,
            "max_tokens": 300,
            "temperature": 0.0,
        },
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "ANTHROPIC_API_KEY", None)
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        self._client = anthropic.AsyncAnthropic(api_key=self.api_key)

        # Cost / spend tracking
        self.daily_spend: float = 0.0
        self.weekly_spend: float = 0.0
        self.daily_token_count: int = 0
        self.last_reset_date = datetime.now(timezone.utc).date()
        self.spend_limits = {
            "daily":  getattr(settings, "LLM_DAILY_SPEND_LIMIT",  10.0),
            "weekly": getattr(settings, "LLM_WEEKLY_SPEND_LIMIT", 50.0),
        }

        # L1 in-process cache (market data can repeat within 60 s)
        self._l1_cache: Dict[str, Dict[str, Any]] = {}
        self._l1_cache_ttl: int = 60

        # Prompt caching toggle (Anthropic ephemeral cache)
        self._prompt_cache_enabled: bool = getattr(
            settings, "LLM_PROMPT_CACHE_ENABLED", True
        )

        logger.info(
            "✅ Anthropic LLM client ready | prompts_v=%s haiku=%s sonnet=%s cache=%s",
            PROMPTS_VERSION, _HAIKU, _SONNET, self._prompt_cache_enabled,
        )

    # ── Core request ──────────────────────────────────────────────────────────

    async def _call(
        self,
        model: str,
        system_prompt: str,
        user_content: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """
        Call Anthropic Messages API with optional prompt-cache headers.

        Returns the raw text of the first content block.
        Raises on non-retriable API errors.
        """
        self._reset_daily_counters_if_needed()

        # Build system block with optional cache_control
        system_block: Any
        if self._prompt_cache_enabled:
            system_block = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_block = system_prompt

        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_block,
            messages=[{"role": "user", "content": user_content}],
        )

        # Update cost tracking
        self._track_usage(model, response.usage)

        return response.content[0].text if response.content else ""

    def _reset_daily_counters_if_needed(self) -> None:
        today = datetime.now(timezone.utc).date()
        if today != self.last_reset_date:
            logger.info(
                "LLM cost reset: daily=$%.4f tokens=%d",
                self.daily_spend, self.daily_token_count,
            )
            self.daily_spend = 0.0
            self.daily_token_count = 0
            self.last_reset_date = today

    def _track_usage(self, model: str, usage: Any) -> None:
        try:
            costs = _COST_TABLE.get(model, {})
            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
            cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

            cost = (
                (input_tokens / 1_000_000) * costs.get("input", 0)
                + (output_tokens / 1_000_000) * costs.get("output", 0)
                + (cache_creation / 1_000_000) * costs.get("cache_write", 0)
                + (cache_read / 1_000_000) * costs.get("cache_read", 0)
            )
            self.daily_spend += cost
            self.weekly_spend += cost
            self.daily_token_count += input_tokens + output_tokens

            try:
                from app.main import LLM_TOKEN_USAGE_TOTAL
                if LLM_TOKEN_USAGE_TOTAL:
                    provider, model_name = "anthropic", model
                    LLM_TOKEN_USAGE_TOTAL.labels(
                        provider=provider, model=model_name
                    ).inc(input_tokens + output_tokens)
            except ImportError:
                pass
        except Exception as exc:
            logger.debug("Usage tracking error: %s", exc)

    # ── L1 cache helpers ──────────────────────────────────────────────────────

    def _cache_key(self, prefix: str, data: Any) -> str:
        return hashlib.md5(f"{prefix}:{json.dumps(data, sort_keys=True)}".encode()).hexdigest()

    def _l1_get(self, key: str) -> Optional[Any]:
        entry = self._l1_cache.get(key)
        if entry and time.time() < entry["expires_at"]:
            return entry["data"]
        return None

    def _l1_put(self, key: str, data: Any) -> None:
        self._l1_cache[key] = {"data": data, "expires_at": time.time() + self._l1_cache_ttl}

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC INTERFACE
    # ─────────────────────────────────────────────────────────────────────────

    async def classify_regime(self, system_prompt: str, user_prompt: str) -> str:
        """
        AI Filter gate — classify XAUUSDT market regime from a trade signal context.

        Called by AIFilter with its own pre-built prompts from prompts.py.
        Returns raw JSON string e.g. '{"regime":"neutral","multiplier":1.0}'.
        Falls back to neutral on any error.
        """
        cfg = self.MODEL_MAPPING["regime_classification"]
        try:
            raw = await self._call(
                model=cfg["model"],
                system_prompt=system_prompt,
                user_content=user_prompt,
                max_tokens=cfg["max_tokens"],
                temperature=cfg["temperature"],
            )
            logger.debug("classify_regime raw: %s", raw[:120])
            return raw.strip()
        except Exception as exc:
            logger.warning("classify_regime failed: %s — returning neutral fallback", exc)
            return '{"regime":"neutral","multiplier":1.0}'

    async def detect_regime(self, market_data: Dict[str, Any]) -> str:
        """
        Classify XAUUSDT market regime from indicator snapshot.

        Returns one of: low_vol_range | low_vol_trending | normal |
        normal_trending | high_vol_breakout | high_vol_reversal | avoid
        """
        cache_key = self._cache_key("regime", market_data)
        if (cached := self._l1_get(cache_key)) is not None:
            return cached

        cfg = self.MODEL_MAPPING["regime_detection"]
        user_prompt = build_regime_context(market_data)

        _VALID = {
            "low_vol_range", "low_vol_trending", "normal", "normal_trending",
            "high_vol_breakout", "high_vol_reversal", "avoid",
        }

        try:
            raw = await self._call(
                model=cfg["model"],
                system_prompt=REGIME_DETECTION_SYSTEM,
                user_content=user_prompt,
                max_tokens=cfg["max_tokens"],
                temperature=cfg["temperature"],
            )
            parsed = _extract_json(raw)
            if parsed:
                regime = str(parsed.get("regime", "normal")).lower()
            else:
                # Try plain text fallback
                regime = raw.strip().lower().split()[0] if raw.strip() else "normal"

            if regime not in _VALID:
                # Partial match
                for v in _VALID:
                    if v in regime:
                        regime = v
                        break
                else:
                    regime = "normal"

            self._l1_put(cache_key, regime)
            logger.info("detect_regime → %s", regime)
            return regime

        except Exception as exc:
            logger.warning("detect_regime failed: %s — heuristic fallback", exc)
            return self._heuristic_regime(market_data)

    async def select_strategy(
        self,
        market_data: Dict[str, Any],
        regime: str = "normal",
    ) -> Dict[str, Any]:
        """
        Select the optimal XAUUSDT trading strategy for the current regime.

        Returns dict with: strategy, confidence, entry_timing, stop_atr_mult,
        rr_ratio, leverage_cap, signal_side, rationale.
        """
        _VALID = {
            "gold_opening_reversal", "gold_breakout", "gold_momentum",
            "gold_mean_reversion", "no_trade",
        }
        cfg = self.MODEL_MAPPING["strategy_selection"]
        user_prompt = build_strategy_context(market_data, regime=regime)

        try:
            raw = await self._call(
                model=cfg["model"],
                system_prompt=STRATEGY_SELECTION_SYSTEM,
                user_content=user_prompt,
                max_tokens=cfg["max_tokens"],
                temperature=cfg["temperature"],
            )
            parsed = _extract_json(raw)
            if not parsed:
                raise ValueError(f"JSON parse failed: {raw[:80]!r}")

            strategy = str(parsed.get("strategy", "gold_momentum"))
            if strategy not in _VALID:
                strategy = "gold_momentum"

            result = {
                "strategy":      strategy,
                "confidence":    float(parsed.get("confidence", 0.65)),
                "entry_timing":  parsed.get("entry_timing", "immediate"),
                "stop_atr_mult": float(parsed.get("stop_atr_mult", 1.5)),
                "rr_ratio":      float(parsed.get("rr_ratio", 2.0)),
                "leverage_cap":  int(parsed.get("leverage_cap", 3)),
                "signal_side":   parsed.get("signal_side", "neutral"),
                "rationale":     parsed.get("rationale", ""),
                "parameters":    {},
            }
            logger.info(
                "select_strategy → %s (conf=%.2f side=%s)",
                result["strategy"], result["confidence"], result["signal_side"],
            )
            return result

        except Exception as exc:
            logger.warning("select_strategy failed: %s — heuristic fallback", exc)
            return self._heuristic_strategy(regime)

    async def assess_risk(
        self,
        position: Dict[str, Any],
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Assess risk for a proposed XAUUSDT position.

        Derives account state from position dict; uses Sonnet for careful
        Kelly-adjacent position sizing.
        """
        cfg = self.MODEL_MAPPING["risk_assessment"]

        indicators = (market_data or {}).get("indicators", {})
        price = float(
            (market_data or {}).get("price", position.get("entry_price", 2000)) or 2000
        )
        atr = float(indicators.get("atr", price * 0.001) or price * 0.001)

        user_prompt = build_risk_context(
            balance=float(position.get("account_balance", 500.0)),
            daily_pnl_pct=float(position.get("daily_pnl_pct", 0.0)),
            drawdown_pct=float(position.get("drawdown_pct", 0.0)),
            consec_losses=int(position.get("consecutive_losses", 0)),
            open_positions=int(position.get("open_positions", 0)),
            side=str(position.get("side", "long")),
            strategy=str(position.get("strategy", "gold_opening_reversal")),
            entry_price=price,
            confidence=float(position.get("confidence", 0.65)),
            stop_atr_mult=float(position.get("stop_atr_mult", 1.5)),
            rr_ratio=float(position.get("rr_ratio", 2.0)),
            atr=atr,
            spread_pct=float((market_data or {}).get("spread_pct", 0.05)),
            session=str((market_data or {}).get("session", "unknown")),
            regime=str((market_data or {}).get("regime", "normal")),
            volatility_pct=float(indicators.get("atr_pct", atr / price * 100)),
        )

        try:
            raw = await self._call(
                model=cfg["model"],
                system_prompt=RISK_ASSESSMENT_SYSTEM,
                user_content=user_prompt,
                max_tokens=cfg["max_tokens"],
                temperature=cfg["temperature"],
            )
            parsed = _extract_json(raw)
            if not parsed:
                raise ValueError(f"JSON parse failed: {raw[:80]!r}")

            approved = bool(parsed.get("approved", True))
            risk_score = int(parsed.get("risk_score", 40))
            if risk_score > 80:
                approved = False

            result = {
                "approved":             approved,
                "risk_score":           risk_score,
                "risk_level":           self._risk_level_from_score(risk_score),
                "position_notional_usd": float(parsed.get("position_notional_usd", 50.0)),
                "max_position_size":     float(parsed.get("position_notional_usd", 50.0)),
                "contracts":            float(parsed.get("contracts", 0.0)),
                "stop_loss":            float(parsed.get("stop_loss_pct", 0.02)),
                "stop_loss_pct":        float(parsed.get("stop_loss_pct", 0.02)),
                "take_profit_pct":      float(parsed.get("take_profit_pct", 0.04)),
                "leverage":             int(parsed.get("leverage", 2)),
                "leverage_recommendation": int(parsed.get("leverage", 2)),
                "reject_reason":        parsed.get("reject_reason", ""),
                "sizing_notes":         parsed.get("sizing_notes", ""),
            }
            logger.info(
                "assess_risk → approved=%s score=%d notional=$%.2f",
                result["approved"], result["risk_score"], result["position_notional_usd"],
            )
            return result

        except Exception as exc:
            logger.warning("assess_risk failed: %s — heuristic fallback", exc)
            return {
                "approved": True,
                "risk_score": 40,
                "risk_level": "medium",
                "position_notional_usd": 50.0,
                "max_position_size": 50.0,
                "contracts": 0.0,
                "stop_loss": 0.02,
                "stop_loss_pct": 0.02,
                "take_profit_pct": 0.04,
                "leverage": 2,
                "leverage_recommendation": 2,
                "reject_reason": "",
                "sizing_notes": "heuristic fallback",
            }

    async def smart_routing_assessment(
        self,
        market_data: Dict[str, Any],
        uncertainty_score: float,
        pnl_drawdown: float,
        drawdown_threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Escalation judge — called only when lower-tier agents disagree or
        uncertainty / drawdown crosses the configured threshold.

        Returns action dict with: action, confidence, position_size_usd,
        stop_loss_pct, tp_pct, reasoning, model_used.
        """
        cfg = self.MODEL_MAPPING["smart_routing"]
        indicators = market_data.get("indicators", {})
        price = float(market_data.get("price", market_data.get("current_price", 2000)) or 2000)

        escalation_threshold = getattr(
            settings, "AI_ESCALATION_UNCERTAINTY_THRESHOLD", 0.75
        )
        should_escalate = (
            uncertainty_score > escalation_threshold
            or pnl_drawdown > drawdown_threshold
        )
        reason = (
            f"uncertainty={uncertainty_score:.2f} drawdown={pnl_drawdown:.2%}"
            if should_escalate
            else "routine_check"
        )

        user_prompt = build_smart_routing_context(
            reason=reason,
            uncertainty=uncertainty_score,
            balance=float(market_data.get("account_balance", 500.0)),
            drawdown_pct=pnl_drawdown,
            consec_losses=int(market_data.get("consecutive_losses", 0)),
            price=price,
            session=str(market_data.get("session", "unknown")),
            regime=str(market_data.get("regime", "normal")),
            strategy=str(market_data.get("strategy", "unknown")),
            atr=float(indicators.get("atr", price * 0.001)),
            rsi=float(indicators.get("rsi", 50.0)),
            adx=float(indicators.get("adx", 20.0)),
        )

        try:
            raw = await self._call(
                model=cfg["model"],
                system_prompt=SMART_ROUTING_SYSTEM,
                user_content=user_prompt,
                max_tokens=cfg["max_tokens"],
                temperature=cfg["temperature"],
            )
            parsed = _extract_json(raw)
            if not parsed:
                raise ValueError(f"JSON parse failed: {raw[:80]!r}")

            action = str(parsed.get("action", "HOLD")).upper()
            if action not in {"BUY", "SELL", "HOLD"}:
                action = "HOLD"

            result = {
                "action":           action,
                "confidence":       float(parsed.get("confidence", 0.5)),
                "position_size_usd": float(parsed.get("position_size_usd", 50.0)),
                "stop_loss_pct":    float(parsed.get("stop_loss_pct", 0.02)),
                "tp_pct":           float(parsed.get("tp_pct", 0.04)),
                "reasoning":        parsed.get("reasoning", ""),
                "model_used":       cfg["model"],
                "escalated":        should_escalate,
            }
            logger.info(
                "smart_routing → %s (conf=%.2f escalated=%s)",
                action, result["confidence"], should_escalate,
            )
            return result

        except Exception as exc:
            logger.warning("smart_routing_assessment failed: %s — HOLD fallback", exc)
            return {
                "action": "HOLD",
                "confidence": 0.5,
                "position_size_usd": 50.0,
                "stop_loss_pct": 0.02,
                "tp_pct": 0.04,
                "reasoning": f"error fallback: {exc}",
                "model_used": "fallback",
                "escalated": False,
            }

    async def test_connection(self) -> bool:
        """Ping Anthropic API with a minimal request."""
        try:
            await self._client.messages.create(
                model=_HAIKU,
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
            logger.info("✅ Anthropic API connection OK")
            return True
        except Exception as exc:
            logger.error("❌ Anthropic API connection failed: %s", exc)
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Heuristic fallbacks (no LLM)
    # ─────────────────────────────────────────────────────────────────────────

    def _heuristic_regime(self, market_data: Dict[str, Any]) -> str:
        indicators = market_data.get("indicators", {})
        price = float(market_data.get("price", 1) or 1)
        atr = float(indicators.get("atr", 0) or 0)
        atr_pct = (atr / price * 100) if price > 0 else 0.0
        adx = float(indicators.get("adx", 20) or 20)
        rsi = float(indicators.get("rsi", 50) or 50)

        if market_data.get("news_events", 0) or market_data.get("spread_pct", 0.05) > 0.15:
            return "avoid"
        if atr_pct > 0.18 and (rsi >= 72 or rsi <= 28):
            return "high_vol_reversal"
        if atr_pct > 0.18:
            return "high_vol_breakout"
        if atr_pct < 0.08:
            return "low_vol_trending" if adx > 22 else "low_vol_range"
        if adx > 28:
            return "normal_trending"
        return "normal"

    def _heuristic_strategy(self, regime: str) -> Dict[str, Any]:
        _MAP = {
            "low_vol_range":      "gold_mean_reversion",
            "low_vol_trending":   "gold_momentum",
            "normal":             "gold_momentum",
            "normal_trending":    "gold_momentum",
            "high_vol_breakout":  "gold_breakout",
            "high_vol_reversal":  "gold_opening_reversal",
            "avoid":              "no_trade",
        }
        return {
            "strategy":      _MAP.get(regime, "gold_momentum"),
            "confidence":    0.60,
            "entry_timing":  "immediate",
            "stop_atr_mult": 1.5,
            "rr_ratio":      2.0,
            "leverage_cap":  3,
            "signal_side":   "neutral",
            "rationale":     "heuristic fallback",
            "parameters":    {},
        }

    @staticmethod
    def _risk_level_from_score(score: int) -> str:
        if score <= 30:
            return "low"
        if score <= 60:
            return "medium"
        if score <= 80:
            return "high"
        return "critical"

    # ─────────────────────────────────────────────────────────────────────────
    # Spend / status helpers (kept for dashboard compatibility)
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def spend_status(self) -> Dict[str, Any]:
        return {
            "daily_spend": round(self.daily_spend, 6),
            "weekly_spend": round(self.weekly_spend, 6),
            "daily_limit": self.spend_limits["daily"],
            "weekly_limit": self.spend_limits["weekly"],
            "daily_tokens": self.daily_token_count,
            "prompts_version": PROMPTS_VERSION,
        }
