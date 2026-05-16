# Institutional-Grade Architecture Upgrade Plan
**Auto Trade System — v2.0 → v3.0 (Production Deployment Ready)**

---

## Executive Summary

> Your system is already far above most retail AI-trading architectures.
> The remaining gap is not "more AI."
> The remaining gap is **production-grade survivability, deterministic execution, observability, and capital protection.**

| Current State | Target State |
|---|---|
| Advanced experimental AI-assisted trading engine | Project-ready institutional execution framework for live deployment |

---

## Architecture Evolution

### Current Flow (v2.0)
```
Signal
  ↓
Risk Validation
  ↓
AI Regime Filter (ai_filter.py)
  ↓
Confidence Decay
  ↓
Execution
  ↓
Analytics
```

### Target Flow (v3.0 — Institutional)
```
Market Data
    ↓
Feature Engine
    ↓
Strategy Engine
    ↓
Risk Validation
    ↓
Market State Filter          ← pre-AI gate (NEW)
    ↓
AI Regime Classifier         ← renamed from ai_filter
    ↓
Execution Readiness Gate     ← most critical missing layer (NEW)
    ↓
Execution Engine
    ↓
Trade Journal + Telemetry
    ↓
Performance Attribution
    ↓
Adaptive Learning Layer
```

---

## 5 Missing Layers for Live Deployment

| # | Layer | Gap |
|---|---|---|
| 1 | Execution Safety | spread/slippage/orderbook checks missing pre-execution |
| 2 | Deterministic Orchestration | regime persistence, confidence bands, position scaling incomplete |
| 3 | Market Microstructure Awareness | gold-specific session rejection not enforced pre-AI |
| 4 | Failure Containment | kill switch exists but daily-loss / AI-failure auto-triggers missing |
| 5 | Statistical Validation | replay API endpoint, shadow→live gate criteria not enforced |

---

## Phase A — Mandatory (before any live capital)

### A1. Market State Filter

**File:** `app/strategy/market_state_filter.py` *(new)*  
**Purpose:** Reject trades on bad microstructure BEFORE calling Claude. Saves tokens, prevents bad fills.

```python
if spread > max_spread:              reject("spread_too_wide")
if websocket_lag_ms > 500:           reject("ws_lag")
if slippage_rolling_avg > threshold: reject("slippage_elevated")
if exchange_status != "healthy":     reject("exchange_degraded")
if orderbook_depth < minimum_depth:  reject("thin_book")
```

**Gold-specific rejection conditions:**

| Condition | Problem |
|---|---|
| Pre-news compression | fake breakout |
| London open first 3 min | liquidity traps |
| NY lunch (12:00–13:00 EST) | low follow-through |
| Rollover window | spread explosion |
| CPI / FOMC ±30 min | impossible fills |
| Weekend reopen | gap risk |

---

### A2. Exchange Health Scoring

**File:** `app/infra/exchange_health.py` *(new)*  
**Purpose:** Weighted health score drives position sizing and trade gating.

```python
exchange_health = weighted_score(
    api_latency,
    websocket_stability,
    rejected_orders,
    slippage,
    orderbook_quality
)
```

| State | Action |
|---|---|
| `healthy` | normal execution |
| `degraded` | `position_size *= 0.5` |
| `critical` | `skip_trade()` |

Add `"eh": "healthy|degraded|critical"` to AI payload.

---

### A3. Kill-Switch Auto-Triggers

**File:** `app/infra/kill_switch.py` *(extend existing)*  
**Purpose:** The `KillSwitch` class exists but lacks automatic daily-loss and AI-failure triggers.

```python
if daily_drawdown <= -0.03:          ks.engage("daily_loss_limit")
if consecutive_losses >= 5:          cooldown(hours=2)
if malformed_ai_responses > 5:       disable_ai_classifier()
if websocket_disconnects > threshold: ks.engage("ws_instability")
```

---

### A4. Slippage Intelligence

**File:** `app/analytics/slippage_tracker.py` *(new)*  
**Purpose:** Track expectancy AFTER execution friction. A good signal with terrible slippage is untradable.

```python
slippage = order.fill_price - signal.entry

# Track per dimension:
# session_slippage | volatility_slippage | exchange_slippage | regime_slippage
```

Example insight this enables:

| Regime | Win Rate | Slippage | Net Expectancy |
|---|---|---|---|
| supportive | high | terrible | negative |
| neutral | medium | excellent | positive |

---

### A5. Replay API Endpoint

**File:** `app/api/replay.py` *(new)* — extends existing `app/replay/replay_engine.py`  
**Purpose:** `GET /replay/{trade_id}` reconstructs signal → market context → AI classification → execution timeline for post-mortem debugging.

The `ReplayEngine` class exists (JSONL file replay). Missing: HTTP endpoint that reconstructs a specific trade from the event store by `trade_id`.

---

## Phase B — Deterministic Orchestration

### B1. Rename `ai_filter.py` → `regime_classifier.py`

**Why:** `filter` = subjective opinion. `classifier` = deterministic state machine. Matters for long-term scaling and team communication.

- `app/strategy/ai_filter/ai_filter.py` → `app/strategy/regime_classifier/regime_classifier.py`
- Update all imports

---

### B2. Regime Persistence (weighted memory)

**File:** `app/strategy/regime_classifier/regime_classifier.py` *(extend)*  
**Current weakness:** AI classifies independently each call. Markets have persistence.

```python
# Replace per-candle classification with weighted rolling average
current_regime = weighted_average(last_5_regimes)
# weights: [0.35, 0.25, 0.20, 0.12, 0.08]
```

---

### B3. Confidence Bands

**Current:** `confidence = 0.68` (false precision)  
**Better:**
```python
confidence_band = {"low": 0.62, "mid": 0.68, "high": 0.73}
```

Use `mid` for execution decisions, `low`/`high` for position sizing bounds.

---

### B4. Position Scaling by Regime

**File:** `app/execution/execution_service.py` *(extend)*  
**Replace binary execute/reject with scaled sizing:**

| Regime | Multiplier | Size |
|---|---|---|
| supportive | 1.1 | 1.0x |
| neutral | 1.0 | 0.6x |
| hostile | 0.85 | 0.3x |
| avoid | 0.0 | 0x |

Position sizing improvement > entry quality improvement.

---

### B5. Multi-Timeframe Regime Alignment

**File:** `app/strategies/gold_opening_reversal.py` *(extend)*  
**Precompute before AI call. Pass compressed form:**

```json
"tf": "AA"
```

| 5m | 1h | tf | Action |
|---|---|---|---|
| bullish | bullish | `AA` | supportive |
| bearish | bearish | `DD` | hostile |
| mixed | — | `MX` | neutral |

Claude should NOT infer this. Engine precomputes it.

---

### B6. Statistical Circuit Breakers

**File:** `app/risk/circuit_breaker.py` *(extend existing)*  
**The `CircuitBreaker` class exists but lacks rolling statistical triggers:**

```python
if rolling_winrate_50 < 0.42:    reduce_size(0.50)
if sharpe_rolling < 0:           pause_strategy()
if pnl_stddev_spike:             emergency_stop()
```

---

## Phase C — Scaling & Optimization

### C1. AI Cost-to-Edge Tracking

**File:** `app/analytics/ai_edge_tracker.py` *(extend existing)*  
**The `AIEdgeTracker` class exists. Add cost delta tracking:**

```python
net_ai_edge = ai_profit_delta - ai_cost_per_month
```

| Metric | Example |
|---|---|
| AI cost/month | $180 |
| PnL improvement | +$90 |
| Net effect | **NEGATIVE** |

---

### C2. Shadow Mode → Live Gate Enforcement

**File:** `app/shadow_mode/execution_engine.py` *(extend existing)*  
**`ShadowExecutionEngine` exists with `get_validation_status()`. Missing: hard gate that blocks live deployment until criteria met.**

Minimum criteria before Stage 4 (micro capital):
- ≥ 200 trades across all sessions
- Positive expectancy
- Stable Sharpe ≥ 1.5
- Max drawdown ≤ 10%
- Avg accuracy score ≥ 90%

---

### C3. Local ML Classifier (future evolution)

Replace or augment Claude with local XGBoost/LightGBM for regime classification:

| Attribute | Claude | XGBoost |
|---|---|---|
| Latency | 400–600ms | < 5ms |
| Cost | $0.003/call | $0 |
| Backtestable | No | Yes |
| Requires dataset | No | Yes (500+ labeled trades) |

Trigger: when you have 500+ labeled regime outcomes from live trading.

---

## Updated Production Prompt

### System Prompt
```
You classify XAUUSDT market regimes.

Evaluate ONLY:
- Session quality
- DXY alignment
- Liquidity quality
- Volatility state
- News risk
- Volume confirmation
- Multi-timeframe alignment

Return ONLY JSON. No explanations. No reasoning. No markdown.

{"r":"supportive|neutral|hostile|avoid","m":1.1|1.0|0.85|0.0}
```

### Deterministic AI Settings (mandatory)
```python
temperature = 0
top_p = 0
max_tokens = 20
```

### Final Optimized Payload
```json
{
  "sig": "LONG",
  "c": 0.68,
  "s": "OR",
  "m": {
    "ss": "LO",
    "dx": "UP",
    "n": 0,
    "v": "H",
    "l": "heavy",
    "vol": "exp",
    "tf": "AA",
    "eh": "healthy"
  }
}
```

**Schema key:**

| Key | Meaning | Values |
|---|---|---|
| `sig` | Signal side | LONG / SHORT |
| `c` | Base confidence | 0.0–1.0 |
| `s` | Strategy | OR=opening_reversal |
| `m.ss` | Session | LO, LC, NO, NC, dead |
| `m.dx` | DXY trend | UP, DN, FLAT |
| `m.n` | News events ≤45min | 0 / 1+ |
| `m.v` | Volume | L, N, H |
| `m.l` | Liquidity | thin / normal / heavy |
| `m.vol` | Volatility | comp / stable / exp |
| `m.tf` | TF alignment | AA / DD / MX |
| `m.eh` | Exchange health | healthy / degraded / critical |

---

## Final Confidence & Sizing Formula

```python
final_confidence = (
    base_confidence
    * regime_multiplier       # 1.1 / 1.0 / 0.85 / 0.0
    * decay_factor            # exp(-0.15 * consecutive_same_direction)
    * exchange_health_factor  # 1.0 / 0.7 / 0.0
    * liquidity_factor        # thin=0.7, normal=1.0, heavy=1.1
)

final_position_size = (
    base_position_size
    * regime_size_multiplier  # 1.0 / 0.6 / 0.3 / 0.0
    * health_size_multiplier  # 1.0 / 0.5 / 0.0
)
```

---

## Staged Deployment Path

| Stage | Description | Gate to Next |
|---|---|---|
| 1 — Replay | Historical deterministic testing | All edge cases pass |
| 2 — Paper Trading | Min 200 trades, all sessions, all regimes | Positive expectancy |
| 3 — Shadow Execution | Fake orders beside real market; compare fills/slippage/latency | Slippage within bounds |
| 4 — Micro Capital | 0.25% normal size | Stable Sharpe, low op failures |
| 5 — Gradual Scale | Increase only after statistical significance | Consistent positive expectancy |

---

## What Separates Retail Bots from Deployable Infrastructure

Not more indicators. Not more AI. Not more strategies.

1. Surviving abnormal conditions
2. Preventing catastrophic execution
3. Statistical discipline
4. Automatic self-protection
5. Controlled scaling

---

## Future Architecture Direction

| Old Model | New Model |
|---|---|
| AI predicts direction | AI classifies regimes |
| Large prompts | Compressed structured states |
| Centralized cloud AI | Local lightweight classifiers |
| Signal generation AI | Execution-quality AI |
| Static strategies | Adaptive probabilistic systems |

**Likely evolution:** Rules → ML (XGBoost/LightGBM) → AI anomaly layer only

---

*Version: 3.0-plan | Last updated: 2026-05-16 | Status: Planning*
