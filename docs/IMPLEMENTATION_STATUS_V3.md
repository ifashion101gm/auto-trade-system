# Implementation Status — Live Tracker
**Auto Trade System v3.0 — Institutional Upgrade**

> This document is the single source of truth for anyone joining execution.
> Update your row when you pick up a task. Update status when done.
> Last sync: 2026-05-16

---

## How to Use This Document

1. Find an unassigned task below
2. Add your name to the **Owner** column
3. Change status to `🔄 In Progress`
4. Open a PR referencing the task ID (e.g. `A1`, `B3`)
5. Mark `✅ Done` when merged and tested

**Status legend:**

| Symbol | Meaning |
|---|---|
| ✅ Done | Merged, tested, production-ready |
| 🔄 In Progress | Actively being worked on |
| 🟡 Partial | Skeleton/stub exists, needs completion |
| ⬜ Not Started | Available to pick up |
| 🔴 Blocked | Waiting on dependency |

---

## Current System Baseline (what already exists)

> Read this before picking up any task. Do not rebuild what's already there.

| Component | File | State | Notes |
|---|---|---|---|
| Kill Switch | `app/infra/kill_switch.py` | ✅ Done | Persist to disk, Telegram alert, engage/disengage |
| System Circuit Breaker | `app/infra/circuit_breaker.py` | ✅ Done | API failures, slippage, WS health, spread, position sync |
| Risk Circuit Breaker | `app/risk/circuit_breaker.py` | ✅ Done | Consecutive losses, drawdown, latency, WS disconnects |
| AI Filter (Regime Classifier) | `app/strategy/ai_filter/ai_filter.py` | ✅ Done | OpenRouter, regime multipliers, decay, timeout, fallback |
| AI Edge Tracker | `app/analytics/ai_edge_tracker.py` | ✅ Done | Per-regime win rate / avg PnL from Postgres |
| Replay Engine | `app/replay/replay_engine.py` | 🟡 Partial | JSONL file replay exists; HTTP endpoint missing |
| Shadow Mode Engine | `app/shadow_mode/execution_engine.py` | ✅ Done | Full shadow trade lifecycle, divergence, accuracy score |
| Paper Trading Validator | `app/paper_trading/paper_trading_validator.py` | ✅ Done | Synthetic fixtures, latency p50/p95/p99, token estimate |
| Self-Healing Agents | `app/execution/agents/` | ✅ Done | Signal, Execution, Verification, Monitoring, Recovery, Reconciliation |
| News Guard | `app/runtime/news_guard.py` | ✅ Done | Economic event calendar, safety window |
| Prometheus Metrics | `app/monitoring/` | ✅ Done | Metrics collection + Grafana dashboards |
| Telegram Notifications | `app/notifications/` | ✅ Done | Trade events, kill switch, circuit breaker alerts |
| Bybit pybit Integration | `app/infra/pybit_demo_client.py` | ✅ Done | Demo trading, V5 API, XAUUSDT linear perps |

---

## Phase A — Mandatory (block live capital until complete)

### A1 — Market State Filter
**Priority:** 🔴 Critical  
**File:** `app/strategy/market_state_filter.py` *(create new)*  
**Depends on:** nothing  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- Pre-AI gate that rejects trades on bad microstructure
- Checks: spread width, WS lag, rolling slippage avg, exchange status, orderbook depth
- Gold-specific time-based rejections: London open first 3 min, NY lunch, rollover window, pre-news compression
- Returns `MarketStateResult(allowed: bool, reason: str)`
- Must run BEFORE `AIFilter.validate_signal()`

**Acceptance criteria:**
- [ ] All 5 microstructure checks implemented
- [ ] Gold session rejection table enforced
- [ ] Unit tests cover each rejection condition
- [ ] Integrated into signal pipeline before AI call

---

### A2 — Exchange Health Scoring
**Priority:** 🔴 Critical  
**File:** `app/infra/exchange_health.py` *(create new)*  
**Depends on:** existing `app/infra/circuit_breaker.py` (can reuse metrics)  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- Weighted health score from: api_latency, ws_stability, rejected_orders, slippage, orderbook_quality
- Three states: `healthy` / `degraded` / `critical`
- `degraded` → `position_size *= 0.5`
- `critical` → `skip_trade()`
- Expose `"eh"` field for AI payload injection

**Acceptance criteria:**
- [ ] `get_health_state() -> Literal["healthy", "degraded", "critical"]`
- [ ] Position size multiplier applied in execution path
- [ ] `eh` field added to `_build_regime_prompt()` in `ai_filter.py`
- [ ] Unit tests for each state transition

---

### A3 — Kill Switch Auto-Triggers
**Priority:** 🔴 Critical  
**File:** `app/infra/kill_switch.py` *(extend existing)*  
**Depends on:** existing `KillSwitch` class  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- `DailyLossMonitor`: engage kill switch when `daily_drawdown <= -3%`
- `ConsecutiveLossLock`: `cooldown(hours=2)` after 5 consecutive losses
- `AIFailureLock`: disable AI classifier after 5 malformed responses (use `AIFilter.get_counters()`)
- `WSInstabilityLock`: engage kill switch after threshold WS disconnects

**Note:** `KillSwitch.engage()` already works. You are wiring the auto-trigger logic only.

**Acceptance criteria:**
- [ ] Daily loss trigger tested with mock PnL feed
- [ ] Consecutive loss cooldown releases after 2h
- [ ] AI failure lock falls back to rule-based (not full stop)
- [ ] All triggers send Telegram alert via existing notifier

---

### A4 — Slippage Intelligence Tracker
**Priority:** 🟠 High  
**File:** `app/analytics/slippage_tracker.py` *(create new)*  
**Depends on:** `app/infra/circuit_breaker.py` already tracks `recent_slippages`  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- Per-dimension slippage tracking: session / volatility_regime / exchange / regime
- Rolling averages with configurable window (default 50 trades)
- `get_slippage_report() -> Dict` for dashboard
- Feed into Market State Filter (A1) for pre-trade rejection

**Note:** `SystemCircuitBreaker.record_fill_slippage()` already exists. Extend, don't duplicate.

**Acceptance criteria:**
- [ ] Slippage tracked per session (LO, NO, LC, NC, dead)
- [ ] Slippage tracked per regime (supportive, neutral, hostile)
- [ ] `get_slippage_report()` returns per-dimension averages
- [ ] Integrated with Market State Filter threshold check

---

### A5 — Replay HTTP Endpoint
**Priority:** 🟠 High  
**File:** `app/api/replay.py` *(create new)*  
**Depends on:** existing `app/replay/replay_engine.py`, event store  
**Owner:** —  
**Status:** 🟡 Partial (engine exists, endpoint missing)

**What to build:**
- `GET /replay/{trade_id}` FastAPI endpoint
- Reconstructs: signal → market context → AI classification → execution timeline
- Reads from event store / trade journal by `trade_id`
- Returns structured JSON timeline for debugging

**Acceptance criteria:**
- [ ] Endpoint returns 404 for unknown trade_id
- [ ] Returns full timeline: signal_received → ai_classified → order_sent → fill_confirmed
- [ ] Includes AI regime, multiplier, confidence at time of trade
- [ ] Registered in `app/main.py` router

---

## Phase B — Deterministic Orchestration

### B1 — Rename ai_filter → regime_classifier
**Priority:** 🟡 Medium  
**Files:** `app/strategy/ai_filter/` → `app/strategy/regime_classifier/`  
**Depends on:** nothing (pure rename + import update)  
**Owner:** —  
**Status:** ⬜ Not Started

**What to do:**
- Rename directory and class: `AIFilter` → `RegimeClassifier`
- Update all imports across codebase
- Update references in `planOptimizeValidationPrompt.prompt.md` and plan docs

**Acceptance criteria:**
- [ ] `grep -r "ai_filter" app/` returns zero results
- [ ] All tests pass after rename
- [ ] No circular imports introduced

---

### B2 — Regime Persistence
**Priority:** 🟡 Medium  
**File:** `app/strategy/regime_classifier/regime_classifier.py` *(extend)*  
**Depends on:** B1  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- Rolling buffer of last 5 regime classifications
- Weighted average: `[0.35, 0.25, 0.20, 0.12, 0.08]`
- `get_persistent_regime() -> Regime` used instead of raw per-call result
- Reduces noise from candle-by-candle regime flipping

**Acceptance criteria:**
- [ ] Buffer initializes to `neutral` on startup
- [ ] Weighted average tested with known input sequences
- [ ] Persistent regime exposed in signal metadata

---

### B3 — Confidence Bands
**Priority:** 🟡 Medium  
**File:** `app/strategy/regime_classifier/regime_classifier.py` *(extend)*  
**Depends on:** B1  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
```python
confidence_band = {"low": mid * 0.92, "mid": adjusted, "high": mid * 1.08}
```
- Use `mid` for execution threshold
- Use `low` / `high` for position sizing bounds
- Add to signal metadata

**Acceptance criteria:**
- [ ] Band values present in `signal.metadata["confidence_band"]`
- [ ] Position sizing uses `low` bound for conservative sizing

---

### B4 — Position Scaling by Regime
**Priority:** 🟠 High  
**File:** `app/execution/execution_service.py` *(extend)*  
**Depends on:** regime metadata in signal  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- Replace binary execute/reject with regime-scaled sizing
- `supportive → 1.0x`, `neutral → 0.6x`, `hostile → 0.3x`, `avoid → 0x`
- Combine with exchange health multiplier from A2

**Acceptance criteria:**
- [ ] Size multiplier applied before order submission
- [ ] `avoid` regime results in zero size (no order)
- [ ] Combined formula: `size * regime_multiplier * health_multiplier`
- [ ] Unit tests for each regime × health combination

---

### B5 — Multi-Timeframe Alignment Precompute
**Priority:** 🟡 Medium  
**File:** `app/strategies/gold_opening_reversal.py` *(extend)*  
**Depends on:** indicator data for 5m and 1h  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- Compute `tf` field before AI call: `AA` / `DD` / `MX`
- `AA` = 5m and 1h both bullish
- `DD` = 5m and 1h both bearish
- `MX` = mixed
- Inject into market context dict for `_build_regime_prompt()`

**Acceptance criteria:**
- [ ] `tf` field present in all AI payloads
- [ ] Logic uses existing `app/strategy/indicators.py` EMA/trend data
- [ ] Unit tests for all 4 alignment combinations

---

### B6 — Statistical Circuit Breakers
**Priority:** 🟠 High  
**File:** `app/risk/circuit_breaker.py` *(extend existing)*  
**Depends on:** trade history in Postgres  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- Rolling 50-trade win rate check: `< 42%` → reduce size 50%
- Rolling Sharpe check: `< 0` → pause strategy
- PnL standard deviation spike detection → emergency stop
- Query from `AIEdgeTracker.get_regime_stats()` or direct Postgres

**Acceptance criteria:**
- [ ] Win rate check runs after each trade close
- [ ] Sharpe calculation uses rolling 50-trade window
- [ ] StdDev spike defined as `> 3x rolling average stddev`
- [ ] All triggers log reason and send Telegram alert

---

## Phase C — Scaling & Optimization

### C1 — AI Cost-to-Edge Net Tracking
**Priority:** 🟡 Medium  
**File:** `app/analytics/ai_edge_tracker.py` *(extend existing)*  
**Depends on:** `app/llm/spend_tracker.py` (already exists)  
**Owner:** —  
**Status:** ⬜ Not Started

**What to build:**
- `get_net_ai_edge() -> Dict`: `ai_profit_delta - ai_cost_month`
- Compare regime win rates with vs. without AI (rule-based fallback as baseline)
- Monthly report via `DailyAIReport`

**Acceptance criteria:**
- [ ] Net edge calculation uses actual spend from `SpendTracker`
- [ ] Baseline comparison uses rule-based fallback win rate
- [ ] Report available at `GET /analytics/ai-edge`

---

### C2 — Shadow → Live Hard Gate
**Priority:** 🟠 High  
**File:** `app/shadow_mode/execution_engine.py` *(extend existing)*  
**Depends on:** `get_validation_status()` already exists  
**Owner:** —  
**Status:** 🟡 Partial (validation logic exists, gate enforcement missing)

**What to build:**
- Hard gate in startup/deployment path that reads `get_validation_status()`
- Block live mode if `validation_passed == False`
- Minimum criteria: 200 trades, win rate ≥ 55%, Sharpe ≥ 1.5, drawdown ≤ 10%, accuracy ≥ 90%
- CLI command: `python manage.py check-shadow-gate`

**Acceptance criteria:**
- [ ] Live mode startup fails with clear message if gate not passed
- [ ] Gate criteria configurable via settings
- [ ] Gate status exposed at `GET /health/shadow-gate`

---

### C3 — Local ML Classifier (future)
**Priority:** ⚪ Low (future)  
**File:** `app/strategy/regime_classifier/ml_classifier.py` *(future)*  
**Depends on:** 500+ labeled regime outcomes from live trading  
**Owner:** —  
**Status:** ⬜ Not Started — do not start until 500 labeled trades available

**What to build (when ready):**
- XGBoost or LightGBM regime classifier
- Same interface as `RegimeClassifier.validate_signal()`
- A/B test against Claude for 30 days before switching

---

## Integration Checklist (before Stage 4 — Micro Capital)

- [ ] **A1** Market State Filter integrated in signal pipeline
- [ ] **A2** Exchange Health Scoring driving position size
- [ ] **A3** Kill Switch auto-triggers wired and tested
- [ ] **A4** Slippage tracker feeding Market State Filter
- [ ] **A5** Replay endpoint live and tested
- [ ] **B4** Position scaling by regime active
- [ ] **B6** Statistical circuit breakers active
- [ ] **C2** Shadow gate enforced (≥200 trades, criteria met)
- [ ] All Telegram alerts firing correctly
- [ ] Prometheus metrics for new modules added
- [ ] All new modules have unit tests with ≥80% coverage

---

## File Map — New vs Extended

| Task | File | Action |
|---|---|---|
| A1 | `app/strategy/market_state_filter.py` | CREATE |
| A2 | `app/infra/exchange_health.py` | CREATE |
| A3 | `app/infra/kill_switch.py` | EXTEND |
| A4 | `app/analytics/slippage_tracker.py` | CREATE |
| A5 | `app/api/replay.py` | CREATE |
| B1 | `app/strategy/ai_filter/` → `app/strategy/regime_classifier/` | RENAME |
| B2 | `app/strategy/regime_classifier/regime_classifier.py` | EXTEND |
| B3 | `app/strategy/regime_classifier/regime_classifier.py` | EXTEND |
| B4 | `app/execution/execution_service.py` | EXTEND |
| B5 | `app/strategies/gold_opening_reversal.py` | EXTEND |
| B6 | `app/risk/circuit_breaker.py` | EXTEND |
| C1 | `app/analytics/ai_edge_tracker.py` | EXTEND |
| C2 | `app/shadow_mode/execution_engine.py` | EXTEND |

---

## Project Readiness Score

| Layer | Current | Target | Blocking Live? |
|---|---|---|---|
| Strategy design | 9/10 | 9/10 | No |
| AI architecture | 9/10 | 9/10 | No |
| Risk structure | 8/10 | 9/10 | No |
| Execution safety | 5/10 | 9/10 | **Yes** |
| Failure handling | 5/10 | 9/10 | **Yes** |
| Monitoring | 7/10 | 9/10 | No |
| Replay/debugging | 3/10 | 8/10 | No |
| Statistical validation | 6/10 | 9/10 | **Yes** |
| Institutional robustness | 6/10 | 9/10 | **Yes** |
| Live readiness | 7/10 | 9/10 | — |

**Blocking tasks:** A1, A2, A3, B4, B6, C2

---

## Questions / Decisions Log

| Date | Question | Decision | Owner |
|---|---|---|---|
| 2026-05-16 | Rename ai_filter now or after Phase A? | After Phase A to avoid blocking A tasks | — |
| 2026-05-16 | Use existing SystemCircuitBreaker or new ExchangeHealth class? | New class (A2) — different responsibility | — |
| — | — | — | — |

---

*Maintained by: project lead | Update frequency: per PR merge*
