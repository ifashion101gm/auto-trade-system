# Current System Status vs. Institutional Upgrade Plan
**Auto Trade System — Honest Assessment for Bybit Live Deployment**

> This document maps every component against the plan.
> It distinguishes between "file exists" and "actually works end-to-end."
> Last updated: 2026-05-16

---

## The Core Problem in One Sentence

> The infrastructure is production-grade. The trading logic is a stub.

The system can connect to Bybit, manage risk, survive failures, and send alerts.
But the strategy that generates signals — `GoldOpeningReversalStrategy.detect_reversal_pattern()` —
contains a `# TODO` comment and returns only RSI > 70 / RSI < 30 as its entire signal logic.

**You cannot trade profitably on RSI alone. Everything else is ready. This is the gap.**

---

## Layer-by-Layer Status

### 1. Exchange Connectivity — ✅ READY

| Component | File | Status | Notes |
|---|---|---|---|
| Bybit Demo client | `app/infra/pybit_demo_client.py` | ✅ Working | `demo=True`, routes to `api-demo.bybit.com` |
| Market orders | `PybitDemoClient.create_market_order()` | ✅ Working | Handles qty rounding, leverage, error codes |
| Balance fetch | `PybitDemoClient.fetch_balance()` | ✅ Working | UNIFIED account, USDT balance |
| Position fetch | `PybitDemoClient.get_positions()` | ✅ Working | Linear perps, filters zero-size |
| Order cancel | `PybitDemoClient.cancel_order()` | ✅ Working | |
| Position close | `PybitDemoClient.close_position()` | ✅ Working | reduceOnly market order |
| Ticker fetch | `PybitDemoClient.fetch_ticker()` | ✅ Working | bid/ask/last price |
| Clock sync check | `validate_clock_sync()` | ✅ Working | Called on startup |
| Leverage set | `set_leverage()` on startup | ✅ Working | Set to `GOLD_MAX_LEVERAGE` (5x) |

**Bybit connection is solid. No work needed here.**

---

### 2. Risk Engine — ✅ READY (with one gap)

| Check | File | Status | Notes |
|---|---|---|---|
| Daily loss limit (-3%) | `RiskEngine.check_trade_approval()` | ✅ Working | Persists to `.risk_state.json`, survives restart |
| Max drawdown (15%) | `RiskEngine` | ✅ Working | Activates drawdown lock |
| Position size cap (1.5%) | `RiskEngine` | ✅ Working | Checks entry × qty × leverage vs balance |
| Leverage limit (5x) | `RiskEngine` + `LeverageManager` | ✅ Working | Dynamic session-aware recommendation |
| Consecutive loss cooldown | `RiskEngine` | ✅ Working | 5 min cooldown after 3 losses |
| Concurrent position limit | `RiskEngine` | ✅ Working | Queries DB for open trades |
| Kill switch check | `RiskEngine` → `KillSwitch` | ✅ Working | First check in approval flow |
| Emergency stop | `RiskEngine.emergency_stop()` | ✅ Working | Persists, Telegram alert |
| **Slippage check** | `RiskEngine.check_slippage_risk()` | 🟡 Partial | Fetches bid/ask but **not called in execution flow** |

**Gap:** `check_slippage_risk()` exists but `ExecutionService._check_risk()` does not call it. Spread check is passive only.

---

### 3. Execution Service — ✅ READY

| Step | Status | Notes |
|---|---|---|
| Circuit breaker health check | ✅ Working | Step 0 in `execute_trade()` |
| Request validation | ✅ Working | XAUUSDT-only enforcement, side/price/qty checks |
| Risk engine check | ✅ Working | Full `check_trade_approval()` called |
| Proposal record creation | ✅ Working | Idempotency check included |
| Order placement (3 retries, 10s timeout) | ✅ Working | `asyncio.wait_for` wrapping |
| Trade record creation | ✅ Working | `PaperTrades` model |
| Event bus publish | ✅ Working | `TRADE_EXECUTED` event |
| Telegram notification | ✅ Working | `send_trade_entry()` |
| Event store audit trail | ✅ Working | `ORDER_SUBMITTED`, `ORDER_FILLED`, `ORDER_REJECTED` |

**Execution pipeline is complete and production-grade.**

---

### 4. AI Regime Classifier — ✅ READY

| Feature | Status | Notes |
|---|---|---|
| OpenRouter client | ✅ Working | `anthropic/claude-sonnet-4-20250514` |
| Regime classification | ✅ Working | supportive / neutral / hostile / avoid |
| Regime multipliers | ✅ Working | 1.1 / 1.0 / 0.85 / 0.0 |
| Confidence decay | ✅ Working | `exp(-0.15 * consecutive)` |
| Hard timeout (1.2s) | ✅ Working | Falls back to neutral |
| Rule-based fallback | ✅ Working | Used when OpenRouter unavailable |
| Compressed payload | ✅ Working | `ss`, `dx`, `n`, `v`, `l`, `vol` fields |
| Parse error recovery | ✅ Working | Regex fallback for malformed JSON |
| AI edge tracking | ✅ Working | `AIEdgeTracker` logs per-regime win rate |
| **Exchange health field (`eh`)** | ⬜ Missing | Not yet injected into payload |
| **Multi-timeframe field (`tf`)** | ⬜ Missing | Not yet computed or injected |

---

### 5. Strategy Signal Generation — 🔴 CRITICAL GAP

This is the most important section.

| Component | File | Status | Notes |
|---|---|---|---|
| Session detection (London/NY) | `GoldOpeningReversalStrategy.is_trading_session()` | ✅ Working | UTC windows correct |
| ATR dynamic risk sizing | `dynamic_risk_sizing()` | ✅ Working | High/low ATR thresholds |
| SignalProposal generation | `generate_signal()` | ✅ Working | Correct structure, metadata |
| **Pattern detection** | `detect_reversal_pattern()` | 🔴 STUB | Contains `# TODO` — only RSI >70/<30 |
| **Indicator calculation** | `app/strategy/indicators.py` | 🟡 Exists | ATR, RSI, EMA, SMA available but not wired to strategy |
| **Market data feed** | No live feed wired | 🔴 Missing | Strategy never called with real OHLCV data |
| **Strategy runner loop** | No loop exists | 🔴 Missing | Nothing calls `generate_signal()` on a schedule |

**The strategy file exists and is well-structured. But `detect_reversal_pattern()` is a placeholder.**
**There is also no loop that feeds live market data into the strategy.**

---

### 6. Kill Switch & Circuit Breakers — ✅ READY

| Component | File | Status | Notes |
|---|---|---|---|
| Manual kill switch | `app/infra/kill_switch.py` | ✅ Working | Persist to disk, Telegram alert |
| Admin API engage/disengage | `app/main.py` | ✅ Working | `POST /admin/kill-switch/engage` |
| System circuit breaker | `app/infra/circuit_breaker.py` | ✅ Working | API failures, slippage, WS, spread, position sync |
| Risk circuit breaker | `app/risk/circuit_breaker.py` | ✅ Working | Consecutive losses, drawdown, latency, WS disconnects |
| **Daily loss auto-trigger** | `RiskEngine._activate_daily_loss_lock()` | ✅ Working | Engages kill switch automatically |
| **Consecutive loss cooldown** | `RiskEngine._check_cooldown_period()` | ✅ Working | 5 min after 3 losses |
| **AI failure lock** | ⬜ Missing | `AIFilter.get_counters()` exists but no auto-disable wired |
| **Statistical circuit breakers** | ⬜ Missing | Rolling win rate / Sharpe checks not implemented |

---

### 7. Self-Healing & Resilience — ✅ READY

| Component | Status | Notes |
|---|---|---|
| 6 specialized agents | ✅ Working | Signal, Execution, Verification, Monitoring, Recovery, Reconciliation |
| Watchdog orchestrator | ✅ Working | API, DB, memory, queue watchdogs |
| Resilience platform | ✅ Working | State machine, recovery executor, resilience manager |
| Task supervisor | ✅ Working | Auto-restart with exponential backoff |
| Reconciliation engine | ✅ Working | Exchange-DB sync every 120s, auto-repair |
| Startup recovery | ✅ Working | Recovers open positions on restart |
| Duplicate order protection | ✅ Working | SHA256 signal hashing in dedup engine |

---

### 8. Monitoring & Observability — ✅ READY

| Component | Status | Notes |
|---|---|---|
| Prometheus metrics | ✅ Working | `/metrics/prometheus` endpoint |
| Grafana dashboards | ✅ Working | Pre-configured in `monitoring/grafana/` |
| Telegram notifications | ✅ Working | Trade events, kill switch, circuit breaker |
| Event store audit trail | ✅ Working | All state transitions logged |
| Session scheduler | ✅ Working | London/NY session gating |
| News guard | ✅ Working | Economic event calendar |
| Health endpoints | ✅ Working | `/health`, `/health/deep` |

---

### 9. Shadow Mode & Paper Trading — ✅ READY (gate not enforced)

| Component | Status | Notes |
|---|---|---|
| Shadow execution engine | ✅ Working | Full lifecycle, divergence, accuracy score |
| Paper trading validator | ✅ Working | Synthetic fixtures, latency p50/p95/p99 |
| Validation criteria | ✅ Working | `get_validation_status()` checks 5 criteria |
| **Hard gate enforcement** | ⬜ Missing | Nothing blocks live mode if shadow criteria not met |

---

### 10. Plan Gaps (from Institutional Upgrade Plan)

| Task | Plan ID | Status | Priority |
|---|---|---|---|
| Market State Filter (pre-AI spread/lag/depth check) | A1 | ⬜ Not Started | 🔴 Critical |
| Exchange Health Scoring | A2 | ⬜ Not Started | 🔴 Critical |
| Kill Switch AI failure auto-trigger | A3 | ⬜ Not Started | 🟠 High |
| Slippage tracker (per-session/regime) | A4 | ⬜ Not Started | 🟠 High |
| Replay HTTP endpoint `/replay/{trade_id}` | A5 | 🟡 Partial | 🟡 Medium |
| Rename ai_filter → regime_classifier | B1 | ⬜ Not Started | 🟡 Low |
| Regime persistence (weighted 5-regime memory) | B2 | ⬜ Not Started | 🟡 Medium |
| Confidence bands (low/mid/high) | B3 | ⬜ Not Started | 🟡 Low |
| Position scaling by regime | B4 | ⬜ Not Started | 🟠 High |
| Multi-timeframe alignment (`tf` field) | B5 | ⬜ Not Started | 🟡 Medium |
| Statistical circuit breakers (rolling Sharpe/winrate) | B6 | ⬜ Not Started | 🟠 High |
| AI cost-to-edge net tracking | C1 | 🟡 Partial | 🟡 Medium |
| Shadow → live hard gate | C2 | 🟡 Partial | 🟠 High |

---

## What You Actually Need to Trade on Bybit

Separated into two tracks: **Demo trading now** vs **Live capital later**.

---

### Track 1 — Trade on Bybit Demo (can start this week)

These are the only things blocking demo trading with real signals:

#### 1. Implement `detect_reversal_pattern()` — 🔴 MUST DO FIRST

**File:** `app/strategies/gold_opening_reversal.py`

The current stub:
```python
def detect_reversal_pattern(self, market_data):
    # TODO: Implement actual pattern detection logic
    rsi = indicators.get('rsi', 50)
    if rsi < 30:
        return ('LONG', 0.70)
    elif rsi > 70:
        return ('SHORT', 0.70)
    return (None, 0.0)
```

Minimum viable implementation needs:
- Pin bar detection (wick > 2× body, close near opposite end)
- Engulfing candle check
- RSI divergence (price makes new low, RSI does not)
- Support/resistance proximity check using recent swing highs/lows
- Confidence scoring based on how many conditions align (not hardcoded 0.70)

All indicator data is already available in `app/strategy/indicators.py` (ATR, RSI, EMA, SMA, MACD).

---

#### 2. Build the Strategy Runner Loop — 🔴 MUST DO

**File:** `app/worker_gold_bot.py` (exists but needs wiring)

Nothing currently calls `generate_signal()` on a schedule. You need:

```python
# Every N seconds during active session:
# 1. Fetch OHLCV from Bybit (5m candles)
# 2. Calculate indicators (already in indicators.py)
# 3. Call strategy.generate_signal(market_data)
# 4. If signal: call AIFilter.validate_signal(signal, market_context)
# 5. If validated: call ExecutionService.execute_trade(request)
```

The Bybit client, AI filter, risk engine, and execution service are all ready.
The loop that connects them is missing.

---

#### 3. Wire Slippage Check into Execution — 🟠 SHOULD DO

**File:** `app/execution/execution_service.py`

`RiskEngine.check_slippage_risk()` exists but is never called in `_check_risk()`.
Add one call before order placement:

```python
slippage = await self.risk_engine.check_slippage_risk(request.symbol)
if not slippage['approved']:
    return ExecutionResult(success=False, error="Spread too wide")
```

---

#### 4. Add Exchange Health to AI Payload — 🟠 SHOULD DO

**File:** `app/strategy/ai_filter/ai_filter.py`

Add `"eh"` field to `_build_regime_prompt()`. Requires A2 (Exchange Health Scoring) or a simple inline check using the existing `SystemCircuitBreaker` state.

---

### Track 2 — Live Capital (after demo validation)

Do not touch live capital until all of these are done:

| # | What | Why |
|---|---|---|
| 1 | Shadow mode gate enforced (C2) | Prove 200+ trades with positive expectancy first |
| 2 | Market State Filter (A1) | Prevent entries during spread explosions, rollover, pre-news |
| 3 | Exchange Health Scoring (A2) | Reduce size or skip when Bybit is degraded |
| 4 | Position scaling by regime (B4) | Never full-size in neutral/hostile conditions |
| 5 | Statistical circuit breakers (B6) | Auto-detect strategy decay before it costs real money |
| 6 | Slippage tracker (A4) | Know your real execution cost per session |
| 7 | Replay endpoint (A5) | Debug any live loss properly |

---

## Honest Readiness Summary

```
Infrastructure (connectivity, risk, execution, monitoring):  ████████████  95% ready
Strategy (signal generation, pattern detection, data feed):  ████░░░░░░░░  30% ready
Institutional safety (pre-AI gates, health scoring, scaling): ██░░░░░░░░░░  20% ready
```

**The system will not lose money because of bad infrastructure.**
**The system will lose money because the strategy logic is a stub.**

Fix the strategy first. Everything else is already there waiting for it.

---

## Recommended Execution Order

```
Week 1:  Implement detect_reversal_pattern() with real pattern logic
Week 1:  Build strategy runner loop (fetch OHLCV → indicators → signal → AI → execute)
Week 1:  Wire slippage check into execution flow
Week 2:  Run on Bybit Demo, collect 50+ trades
Week 2:  Add exchange health scoring (A2), inject eh field into AI payload
Week 3:  Add Market State Filter (A1) — gold session rejection table
Week 3:  Add position scaling by regime (B4)
Week 4:  Run shadow mode for 200 trades, enforce gate (C2)
Week 5+: Micro capital on Bybit Live (0.25% size)
```

---

*Status: Accurate as of 2026-05-16 | Based on direct code inspection*
