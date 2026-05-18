"""
Enterprise Prompt Library — AI Auto-Trade System v2.

All LLM prompts live here: versioned, domain-specific, production-hardened.
Every prompt is tuned for XAUUSDT (Gold/USDT perpetual swap) on Bybit.

Design principles
─────────────────
  Role      : Establish the model as a narrow domain expert, not a general assistant.
  Task      : Define the exact output contract upfront (schema before context).
  Context   : Include XAUUSDT-specific priors so the model doesn't have to infer them.
  Output    : Strict JSON only — no prose, no markdown, no explanations.
  Caching   : System prompts are static strings → eligible for Anthropic prompt caching
              (saves ~90 % of input-token cost on repeated calls).

Usage
─────
  from app.llm.prompts import (
      REGIME_DETECTION_SYSTEM, build_regime_context,
      STRATEGY_SELECTION_SYSTEM, build_strategy_context,
      RISK_ASSESSMENT_SYSTEM, build_risk_context,
      AI_FILTER_SYSTEM, build_ai_filter_context,
      SMART_ROUTING_SYSTEM, build_smart_routing_context,
  )
"""

from __future__ import annotations

from typing import Any, Dict, Optional

PROMPTS_VERSION = "2.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# REGIME DETECTION
# ─────────────────────────────────────────────────────────────────────────────

REGIME_DETECTION_SYSTEM = """\
You are a quantitative regime analyst specialising in XAUUSDT (Gold/USDT linear perpetual on Bybit).

Your sole task: classify the current market regime from the indicator snapshot you receive.

XAUUSDT Regime Taxonomy — use exactly these labels:
  low_vol_range      ATR/Price < 0.08 %, 24 h range tight, consolidation → mean-reversion setups
  low_vol_trending   ATR < 0.10 % BUT ADX > 22, slow directional drift → light trend-following
  normal             ATR 0.10–0.18 %, balanced market → standard momentum/breakout setups
  normal_trending    ATR 0.10–0.18 % AND ADX > 28, clear directional bias → aggressive momentum
  high_vol_breakout  ATR > 0.18 %, ADX rising, price expanding from prior range → breakout entries
  high_vol_reversal  ATR > 0.18 %, RSI ≥ 75 or ≤ 25, exhaustion wick at session open → fade setups
  avoid              ANY of: news within 30 min | bid-ask spread > 0.15 % | volume < 60 % 24 h avg | dead session (Tokyo 00:00-07:49 UTC)

Session context (UTC):
  07:50–10:30  London Open   +15 % expected intra-session volatility
  13:20–16:30  NY Open       +20 % expected intra-session volatility
  14:00–16:00  Overlap       peak liquidity, trend acceleration possible
  00:00–07:49  Dead hours    thin liquidity → classify avoid unless high_vol event

DXY inverse correlation: gold moves inversely to USD.
  DXY rising trend  →  bearish gold bias (SHORT preferred)
  DXY falling trend →  bullish gold bias (LONG preferred)
  DXY flat          →  neutral bias

Output contract: strict JSON, no whitespace beyond the object, no prose.
Schema: {"regime":"<label>","confidence":0.0,"bias":"long|short|neutral","key_driver":"<15 words>"}"""


def build_regime_context(market_data: Dict[str, Any]) -> str:
    """Serialize market_data into the regime-detection user prompt."""
    indicators = market_data.get("indicators", {})
    price = float(market_data.get("price", market_data.get("current_price", 0)) or 0)
    atr = float(indicators.get("atr", 0) or 0)
    atr_pct = round((atr / price * 100) if price > 0 else 0.0, 4)

    return (
        "{"
        f'"symbol":"XAUUSDT",'
        f'"price":{price},'
        f'"session":"{market_data.get("session","unknown")}",'
        f'"indicators":{{'
        f'"atr_pct":{atr_pct},'
        f'"adx":{float(indicators.get("adx", 20) or 20)},'
        f'"rsi_14":{float(indicators.get("rsi", 50) or 50)},'
        f'"macd_hist":{float(indicators.get("macd_histogram", indicators.get("macd", 0)) or 0)},'
        f'"bb_width_pct":{float(indicators.get("bb_width_pct", indicators.get("bb_width", 0)) or 0)},'
        f'"volume_ratio_24h":{float(indicators.get("volume_ratio", 1.0) or 1.0)}'
        f'}},'
        f'"market_context":{{'
        f'"dxy_trend":"{market_data.get("dxy_trend","flat")}",'
        f'"spread_pct":{float(market_data.get("spread_pct", 0.05) or 0.05)},'
        f'"news_within_30min":{str(int(market_data.get("news_events", 0)) > 0).lower()},'
        f'"price_change_1h_pct":{float(market_data.get("price_change_1h_pct", 0) or 0)}'
        f"}}"
        "}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY SELECTION
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_SELECTION_SYSTEM = """\
You are a XAUUSDT execution strategist. Given a confirmed market regime you select the optimal trading strategy.

Available strategies:
  gold_opening_reversal   Session-open fade. Requires: session=london_open|ny_open, RSI divergence, ATR 0.12–0.25 %
  gold_breakout           Range expansion. Requires: high_vol regime, price outside 20-period BB, volume > 120 % avg
  gold_momentum           Trend following. Requires: ADX > 28, price above/below 50-EMA, MACD histogram aligned
  gold_mean_reversion     Range oscillation. Requires: low_vol_range, price at BB extreme, RSI overbought/oversold
  no_trade                No valid setup — use when regime=avoid OR confidence < 0.60

For each strategy specify:
  entry_timing            "immediate" | "wait_retest" | "wait_breakout_confirm"
  stop_atr_multiplier     1.0–2.5 (higher for volatile regimes)
  rr_ratio                minimum 1.5:1 (reward:risk); prefer ≥ 2.0
  leverage_cap            1–5 (use 1–3 during validation phase, never exceed 5)

Output contract: strict JSON only.
Schema: {"strategy":"<name>","confidence":0.0,"entry_timing":"<timing>","stop_atr_mult":1.5,"rr_ratio":2.0,"leverage_cap":3,"signal_side":"long|short|neutral","rationale":"<20 words>"}"""


def build_strategy_context(
    market_data: Dict[str, Any],
    regime: str = "normal",
    regime_bias: str = "neutral",
    regime_confidence: float = 0.7,
    recent_pnl: Optional[list] = None,
    consec_losses: int = 0,
    session_win_rate: float = 0.5,
) -> str:
    """Serialize regime + market_data into the strategy-selection user prompt."""
    indicators = market_data.get("indicators", {})
    price = float(market_data.get("price", market_data.get("current_price", 0)) or 0)
    atr = float(indicators.get("atr", 0) or 0)
    pnl_str = str(recent_pnl or [])

    return (
        "{"
        f'"regime":"{regime}",'
        f'"regime_bias":"{regime_bias}",'
        f'"regime_confidence":{round(regime_confidence, 3)},'
        f'"symbol":"XAUUSDT",'
        f'"price":{price},'
        f'"session":"{market_data.get("session","unknown")}",'
        f'"indicators":{{'
        f'"rsi_14":{float(indicators.get("rsi", 50) or 50)},'
        f'"adx":{float(indicators.get("adx", 20) or 20)},'
        f'"macd_histogram":{float(indicators.get("macd_histogram", indicators.get("macd", 0)) or 0)},'
        f'"atr":{atr},'
        f'"bb_upper":{float(indicators.get("bb_upper", price * 1.005) or price * 1.005)},'
        f'"bb_lower":{float(indicators.get("bb_lower", price * 0.995) or price * 0.995)},'
        f'"bb_mid":{float(indicators.get("bb_mid", price) or price)},'
        f'"ema_20":{float(indicators.get("ema_20", price) or price)},'
        f'"ema_50":{float(indicators.get("ema_50", price) or price)},'
        f'"volume_ratio":{float(indicators.get("volume_ratio", 1.0) or 1.0)}'
        f'}},'
        f'"recent_performance":{{'
        f'"last_3_trades_pnl":{pnl_str},'
        f'"consecutive_losses":{consec_losses},'
        f'"session_win_rate":{round(session_win_rate, 3)}'
        f"}}"
        "}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# RISK ASSESSMENT
# ─────────────────────────────────────────────────────────────────────────────

RISK_ASSESSMENT_SYSTEM = """\
You are the risk officer for an algorithmic XAUUSDT futures desk. Capital preservation is your primary mandate.

Hard limits — NEVER override:
  Max position notional  = 1.5 % of account balance
  Max leverage           = 5× demo / 3× live
  Daily loss limit       = 2 % of account
  Consecutive losses ≥ 3 → cooldown 2 h, reject new positions
  Bid-ask spread > 0.15 % → reject (execution cost too high)

Kelly-adjacent position sizing:
  risk_amount          = balance × risk_pct_per_trade   (default 0.5 %)
  stop_distance_pct    = atr × stop_atr_mult / price × 100
  position_notional    = risk_amount / (stop_distance_pct / 100)
  position_notional    = min(position_notional, balance × 0.015)
  contracts            = position_notional / entry_price

Risk score rubric (0–100):
   0–30   Low risk  → approve at full size
  31–60   Medium    → approve, reduce size to 75 %
  61–80   High      → approve, reduce size to 50 %
  81–100  Critical  → reject

Output contract: strict JSON only.
Schema: {"approved":true,"risk_score":0,"position_notional_usd":0.0,"contracts":0.0,"stop_loss_pct":0.0,"take_profit_pct":0.0,"leverage":1,"reject_reason":"","sizing_notes":"<10 words>"}"""


def build_risk_context(
    balance: float,
    daily_pnl_pct: float,
    drawdown_pct: float,
    consec_losses: int,
    open_positions: int,
    side: str,
    strategy: str,
    entry_price: float,
    confidence: float,
    stop_atr_mult: float,
    rr_ratio: float,
    atr: float,
    spread_pct: float,
    session: str,
    regime: str,
    volatility_pct: float,
) -> str:
    """Serialize account + proposal state into the risk-assessment user prompt."""
    return (
        "{"
        f'"account":{{'
        f'"balance_usd":{round(balance, 2)},'
        f'"daily_pnl_pct":{round(daily_pnl_pct, 4)},'
        f'"drawdown_pct":{round(drawdown_pct, 4)},'
        f'"consecutive_losses":{consec_losses},'
        f'"open_positions":{open_positions}'
        f'}},'
        f'"proposal":{{'
        f'"symbol":"XAUUSDT",'
        f'"side":"{side}",'
        f'"strategy":"{strategy}",'
        f'"entry_price":{round(entry_price, 2)},'
        f'"confidence":{round(confidence, 3)},'
        f'"stop_atr_mult":{stop_atr_mult},'
        f'"rr_ratio":{rr_ratio},'
        f'"atr":{round(atr, 4)}'
        f'}},'
        f'"market":{{'
        f'"spread_pct":{round(spread_pct, 4)},'
        f'"session":"{session}",'
        f'"regime":"{regime}",'
        f'"volatility_pct":{round(volatility_pct, 4)}'
        f"}}"
        "}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# AI FILTER (REGIME GATE)
# ─────────────────────────────────────────────────────────────────────────────

AI_FILTER_SYSTEM = """\
You are the execution gate for a XAUUSDT algorithmic trading system.

You receive a pending trade signal and live market context. Decide whether macro, session, and liquidity conditions SUPPORT, are NEUTRAL toward, are HOSTILE to, or require AVOIDING the proposed direction.

Evaluation criteria (score each YES/NO):
  1. Session alignment   Is this session historically productive for the proposed setup type?
  2. DXY alignment       Does USD direction confirm the signal? (inverse: DXY rising → short gold aligned)
  3. News safety         No high-impact USD/XAU events scheduled within 45 minutes?
  4. Liquidity quality   Is the session liquid enough? (fail: Tokyo 00:00–07:49 UTC)
  5. Volume confirmation Current volume ≥ 80 % of 24 h average?

Regime assignment:
  supportive  (×1.10)  All 5 criteria YES
  neutral     (×1.00)  3–4 criteria YES
  hostile     (×0.85)  1–2 criteria YES  → sizing reduced automatically
  avoid       (×0.00)  0 criteria YES  OR  news_events_45min=true  OR  spread_pct > 0.20  OR  session=dead

CRITICAL: Output ONLY the JSON object. No text before or after. No markdown.
Format: {"regime":"supportive|neutral|hostile|avoid","multiplier":1.1|1.0|0.85|0.0}"""


def build_ai_filter_context(
    side: str,
    confidence: float,
    strategy: str,
    session_code: str,
    dxy_code: str,
    news_flag: bool,
    volume_code: str,
    liquidity_state: str,
    spread_pct: float = 0.05,
    vol_regime: str = "stable",
) -> str:
    """Serialize signal + market context into the AI-filter user prompt."""
    return (
        "{"
        f'"signal":{{"side":"{side}","confidence":{round(confidence, 3)},"strategy":"{strategy}"}},'
        f'"session":"{session_code}",'
        f'"dxy_trend":"{dxy_code}",'
        f'"news_events_45min":{str(news_flag).lower()},'
        f'"volume_state":"{volume_code}",'
        f'"liquidity_state":"{liquidity_state}",'
        f'"spread_pct":{round(spread_pct, 4)},'
        f'"volatility_regime":"{vol_regime}"'
        "}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# SMART ROUTING (ESCALATION JUDGE)
# ─────────────────────────────────────────────────────────────────────────────

SMART_ROUTING_SYSTEM = """\
You are the supreme decision authority for a XAUUSDT algorithmic trading system.

You are invoked only when lower-tier agents disagree or uncertainty is critically high. Your judgment is final and overrides all sub-agent outputs.

Decision framework:
  HOLD if: uncertainty > 0.80  OR  drawdown > 4 %  OR  consecutive_losses ≥ 3
  HOLD if: regime agent and strategy agent produce conflicting directional signals
  BUY/SELL only if: regime + strategy + risk all aligned AND confidence > 0.70
  Always require minimum 2:1 reward-to-risk; 3:1 preferred

Position sizing: use the risk officer formula from the system context.
Maximum single-trade notional = 1.5 % of account balance (hard limit).

Output contract: strict JSON only.
Schema: {"action":"BUY|SELL|HOLD","confidence":0.0,"position_size_usd":0.0,"stop_loss_pct":0.0,"tp_pct":0.0,"reasoning":"<25 words>"}"""


def build_smart_routing_context(
    reason: str,
    uncertainty: float,
    balance: float,
    drawdown_pct: float,
    consec_losses: int,
    price: float,
    session: str,
    regime: str,
    strategy: str,
    atr: float,
    rsi: float,
    adx: float,
    last_pnl: float = 0.0,
    session_wr: float = 0.5,
) -> str:
    """Serialize escalation context into the smart-routing user prompt."""
    return (
        "{"
        f'"escalation_reason":"{reason}",'
        f'"uncertainty_score":{round(uncertainty, 3)},'
        f'"account":{{'
        f'"balance":{round(balance, 2)},'
        f'"drawdown_pct":{round(drawdown_pct, 4)},'
        f'"consecutive_losses":{consec_losses}'
        f'}},'
        f'"market":{{'
        f'"price":{round(price, 2)},'
        f'"session":"{session}",'
        f'"regime_tier1":"{regime}",'
        f'"strategy_tier1":"{strategy}",'
        f'"atr":{round(atr, 4)},'
        f'"rsi":{round(rsi, 2)},'
        f'"adx":{round(adx, 2)}'
        f'}},'
        f'"recent_context":{{'
        f'"last_trade_pnl":{round(last_pnl, 4)},'
        f'"session_win_rate":{round(session_wr, 3)}'
        f"}}"
        "}"
    )
