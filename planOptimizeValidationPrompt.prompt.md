# Plan: Project-Ready Institutional Execution Framework

## Assessment

> Your system is already far above most retail AI-trading architectures.
> The remaining gap is not "more AI."
> The remaining gap is **production-grade survivability, deterministic execution, observability, and capital protection**.

**Current state:** "Advanced experimental AI-assisted trading engine"  
**Target state:** "Project-ready institutional execution framework for live deployment"

---

## Architecture Evolution

### Current Optimized Flow
```
Signal → Risk Validation → AI Regime Filter → Confidence Decay → Execution → Analytics
```

### Institutional-Grade Target Flow
```
Market Data
    ↓
Feature Engine
    ↓
Strategy Engine
    ↓
Risk Validation
    ↓
Market State Filter          ← NEW (pre-AI gate)
    ↓
AI Regime Classifier         ← renamed from ai_filter
    ↓
Execution Readiness Gate     ← NEW (most critical missing layer)
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

## Project Readiness Score

| Layer                    | Current | Target |
|--------------------------|---------|--------|
| Strategy design          | 9/10    | 9/10   |
| AI architecture          | 9/10    | 9/10   |
| Risk structure           | 8/10    | 9/10   |
| Execution safety         | 5/10    | 9/10   |
| Failure handling         | 5/10    | 9/10   |
| Monitoring               | 7/10    | 9/10   |
| Replay/debugging         | 3/10    | 8/10   |
| Statistical validation   | 6/10    | 9/10   |
| Institutional robustness | 6/10    | 9/10   |
| Live readiness           | 7/10    | 9/10   |

---

## 5 Missing Layers for Live Deployment

1. **Execution safety** — spread, slippage, orderbook, exchange health checks
2. **Deterministic orchestration** — regime persistence, confidence bands, position scaling
3. **Market microstructure awareness** — session-specific rejection, gold-specific conditions
4. **Failure containment** — kill switches, circuit breakers, AI failure locks
5. **Statistical validation** — replay engine, shadow mode, staged capital scaling

---

## Phase A — MANDATORY (implement before any live capital)

### Module 1: Market State Filter (pre-AI gate)

Runs BEFORE Claude. Prevents wasting tokens on statistically bad conditions.

```python
# app/strategy/market_state_filter.py
if spread > max_spread:             reject_trade("spread")
if websocket_lag_ms > 500:          reject_trade("ws_lag")
if slippage_rolling_avg > threshold: reject_trade("slippage")
if exchange_status != "healthy":    reject_trade("exchange")
if orderbook_depth < minimum_depth: reject_trade("depth")
```

**Gold-specific rejection conditions:**

| Condition              | Problem                  |
|------------------------|--------------------------|
| Pre-news compression   | fake breakout            |
| London open first 3min | liquidity traps          |
| NY lunch               | low follow-through       |
| Rollover               | spread explosion         |
| CPI/FOMC               | impossible fills         |
| Weekend reopen         | gaps                     |

---

### Module 2: Exchange Health Scoring

```python
# app/infra/exchange_health.py
exchange_health = weighted_score(
    api_latency,
    websocket_stability,
    rejected_orders,
    slippage,
    orderbook_quality
)
```

| State    | Action                        |
|----------|-------------------------------|
| healthy  | normal execution              |
| degraded | `position_size *= 0.5`        |
| critical | `skip_trade()`                |

Add `"eh": "healthy|degraded|critical"` to AI payload.

---

### Module 3: Kill-Switch Layer

```python
# app/risk/kill_switch.py
if daily_drawdown <= -0.03:         disable_trading("daily_loss_limit")
if consecutive_losses >= 5:         cooldown(hours=2)
if malformed_ai_responses > 5:      disable_ai_classifier()
if websocket_disconnects > threshold: disable_trading("ws_instability")
```

---

### Module 4: Slippage Intelligence

```python
# app/analytics/slippage_tracker.py
slippage = order.fill_price - signal.entry

# Track per dimension:
# - session_slippage
# - volatility_slippage
# - exchange_slippage
# - regime_slippage
```

Track expectancy AFTER execution friction, not before. A "good trade" with terrible slippage is untradable.

---

### Module 5: Replay Engine

```python
# GET /replay/{trade_id}
# Reconstructs: signal → market context → AI classification → execution timeline
```

Required for debugging live losses. Without deterministic replay, post-mortem analysis is guesswork.

---

## Phase B — Deterministic Orchestration

### Module 6: Rename `ai_filter.py` → `regime_classifier.py`

- `filter` = subjective opinion
- `classifier` = deterministic state machine

This matters architecturally and for long-term scaling.

---

### Module 7: Regime Persistence (weighted memory)

Instead of independent per-candle classification:

```python
# app/strategy/regime_classifier.py
current_regime = weighted_average(last_5_regimes)
```

Markets transition gradually. Per-candle regime flipping introduces noise.

---

### Module 8: Confidence Bands (not single value)

```python
confidence_band = {"low": 0.62, "mid": 0.68, "high": 0.73}
```

Single-precision confidence values create false certainty. Markets are probabilistic.

---

### Module 9: Position Scaling by Regime

```python
# Replace binary execute/reject with scaled sizing:
# supportive → 1.0x size
# neutral    → 0.6x size
# hostile    → 0.3x size
# avoid      → 0x
```

Position sizing improvement > entry quality improvement. Most profitability gains come from scaling into high-quality conditions, not predicting direction better.

---

### Module 10: Multi-Timeframe Regime Alignment

Precompute before AI call. Pass compressed form:

```json
"tf": "AA"   // AA=aligned bullish, DD=aligned bearish, MX=mixed
```

| 5m      | 1h      | tf value | Action     |
|---------|---------|----------|------------|
| bullish | bullish | AA       | supportive |
| bearish | bearish | DD       | hostile    |
| bullish | bearish | MX       | neutral    |

Claude should NOT infer this. Engine precomputes it.

---

### Module 11: Statistical Circuit Breakers

```python
# app/risk/circuit_breaker.py
if rolling_winrate_50 < 0.42:   reduce_size(0.5)
if sharpe_rolling < 0:          pause_strategy()
if pnl_stddev_spike:            emergency_stop()
```

Strategies decay. Markets evolve. System must detect degradation automatically.

---

## Phase C — Scaling & Optimization

### Module 12: AI Cost-to-Edge Tracking

```python
# app/analytics/ai_cost_tracker.py
net_ai_edge = ai_profit_delta - ai_cost_per_month
```

| Metric          | Example  |
|-----------------|----------|
| AI cost/month   | $180     |
| PnL improvement | +$90     |
| Net effect      | NEGATIVE |

Track this. Many AI trading systems fail here silently.

---

### Module 13: Shadow Mode + Staged Deployment

| Stage | Description                                      | Gate to next stage              |
|-------|--------------------------------------------------|---------------------------------|
| 1     | Replay — historical deterministic testing        | All edge cases pass             |
| 2     | Paper trading — min 200 trades, all sessions     | Positive expectancy             |
| 3     | Shadow execution — fake orders beside real market | Slippage/latency within bounds  |
| 4     | Micro capital — 0.25% normal size                | Stable Sharpe, low op failures  |
| 5     | Gradual scale — increase only after validation   | Statistical significance        |

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
temperature=0
top_p=0
max_tokens=20
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
- `sig` — Signal side (LONG|SHORT)
- `c` — Base confidence (0.0–1.0)
- `s` — Strategy (OR=opening_reversal)
- `m.ss` — Session (LO, LC, NO, NC, dead)
- `m.dx` — DXY trend (UP, DN, FLAT)
- `m.n` — News events within 45min (0=none, 1+=present)
- `m.v` — Volume (L, N, H)
- `m.l` — Liquidity (thin|normal|heavy)
- `m.vol` — Volatility (comp|stable|exp)
- `m.tf` — Timeframe alignment (AA|DD|MX)
- `m.eh` — Exchange health (healthy|degraded|critical)

---

## Final Confidence & Sizing Formula

```python
final_confidence = (
    base_confidence
    * regime_multiplier       # 1.1 / 1.0 / 0.85 / 0.0
    * decay_factor            # e^(-0.15 * consecutive_same_direction)
    * exchange_health_factor  # 1.0 / 0.7 / 0.0
    * liquidity_factor        # thin=0.7, normal=1.0, heavy=1.1
)

final_position_size = (
    base_position_size
    * regime_size_multiplier  # 1.0 / 0.6 / 0.3 / 0.0
    * health_size_multiplier  # 1.0 / 0.5 / 0.0
)
```

### Regime Table

| Regime     | Multiplier | Size |
|------------|------------|------|
| supportive | 1.1        | 1.0x |
| neutral    | 1.0        | 0.6x |
| hostile    | 0.85       | 0.3x |
| avoid      | 0.0        | 0x   |

---

## Relevant Files

| File | Change |
|------|--------|
| `app/strategy/ai_filter/ai_filter.py` | Rename → `regime_classifier.py`; add regime persistence, confidence bands |
| `app/strategy/market_state_filter.py` | NEW — pre-AI spread/lag/depth/exchange checks |
| `app/infra/exchange_health.py` | NEW — weighted health scoring (healthy/degraded/critical) |
| `app/risk/kill_switch.py` | NEW — daily loss, consecutive loss, AI failure, WS disconnect locks |
| `app/risk/circuit_breaker.py` | NEW — rolling winrate, Sharpe, PnL stddev auto-stops |
| `app/analytics/slippage_tracker.py` | NEW — per-session/regime/exchange slippage tracking |
| `app/analytics/ai_cost_tracker.py` | NEW — net AI edge = profit delta − API cost |
| `app/api/replay.py` | NEW — `GET /replay/{trade_id}` deterministic reconstruction |
| `app/strategies/gold_opening_reversal.py` | Add multi-timeframe alignment precompute |
| `gold_ai_upgrade_plan.html` | Update architecture diagram and regime table |

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

| Old Model                  | New Model                          |
|----------------------------|------------------------------------|
| AI predicts direction      | AI classifies regimes              |
| Large prompts              | Compressed structured states       |
| Centralized cloud AI       | Local lightweight classifiers      |
| Signal generation AI       | Execution-quality AI               |
| Static strategies          | Adaptive probabilistic systems     |

**Likely evolution path:** Rules → ML (XGBoost/LightGBM) → AI anomaly layer only

---

## Monetization Potential

This architecture can evolve into:
1. AI trade infrastructure SaaS
2. Regime API service
3. Execution-quality analytics platform
4. Gold-specific execution engine
5. Multi-exchange smart routing engine
6. Institutional replay debugger
7. AI risk-control middleware

Positioning: **"AI-assisted execution intelligence for gold/futures traders"** — far more valuable than "AI trading signals."
