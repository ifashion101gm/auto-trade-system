# AI Regime Filter: Implementation Checklist

**Print this. Check items as you complete them. Share with team daily.**

---

## 📋 PHASE 1 COMPLETION (85% → 100%)

### ✅ Already Complete (No Action Needed)

- [x] Regime classifier core logic (4 regimes, multipliers)
- [x] OpenRouter integration (via existing gateway)
- [x] Hard timeout (1.2s with fallback)
- [x] Confidence decay formula (exponential)
- [x] Confidence floor/ceiling (0.30-1.0)
- [x] Rule-based fallback
- [x] News Guard event types
- [x] Analytics structure
- [x] Regime enums + constants

### 🔄 IN PROGRESS (Next 3 Days)

#### TODAY (May 16) — Priority 1 & 2

- [ ] **Priority 1: Wire Liquidity State** (30 min)
  - [ ] Add `compute_liquidity_state()` method to `app/runtime/news_guard.py`
    ```
    - Before London (0-7 UTC): thin
    - London mid (8-10 UTC): heavy
    - NY lunch (13-14 UTC): thin
    - NY open (14-17 UTC): heavy
    - Rollover (22-24 UTC): thin
    - Everything else: normal
    ```
  - [ ] Wire to `app/execution/agents/signal_agent.py`
    ```
    market_data["liquidity_state"] = news_guard.compute_liquidity_state()
    ```
  - [ ] Test: Run sample signal, verify liquidity_state in logs
  - [ ] **Owner:** @Execution-Platform

- [ ] **Priority 2: Expand Unit Tests** (1.5 hours)
  - [ ] Copy test suite from `CONTINUATION_PLAN_AI_REGIME_FILTER.md`
  - [ ] Create/update `tests/unit/test_ai_filter_regime.py`
  - [ ] Test cases:
    - [ ] System prompt structure
    - [ ] Schema compression (<150 tokens)
    - [ ] Confidence multiplier math
    - [ ] Confidence decay formula (e^(-0.15n))
    - [ ] Confidence floor enforcement
    - [ ] Liquidity state handling
    - [ ] Avoid regime returns None
    - [ ] Signal tracking
    - [ ] Timeout fallback
    - [ ] Malformed JSON fallback
  - [ ] Run: `pytest tests/unit/test_ai_filter_regime.py -v`
  - [ ] Result: **ALL GREEN** ✅
  - [ ] **Owner:** @QA-Engineer

#### TOMORROW (May 17) — Priority 3

- [ ] **Priority 3: Connect Analytics to Postgres** (2 hours)
  - [ ] Create Postgres migration script
    ```sql
    ALTER TABLE trades ADD COLUMN regime VARCHAR(20);
    ALTER TABLE trades ADD COLUMN base_confidence FLOAT;
    ALTER TABLE trades ADD COLUMN adjusted_confidence FLOAT;
    ALTER TABLE trades ADD COLUMN ai_multiplier FLOAT;
    ```
  - [ ] Run migration: `alembic upgrade head`
  - [ ] Update `app/analytics/ai_edge_tracker.py`
    - [ ] Implement `log_trade_close()` with Postgres UPDATE
    - [ ] Implement `get_regime_stats()` with Postgres SELECT
  - [ ] Implement `app/analytics/daily_ai_report.py`
    - [ ] Generate daily report (06:00 UTC)
    - [ ] Calculate win_rate per regime
    - [ ] Alert if underperforming
  - [ ] Test: `pytest tests/analytics/test_daily_report.py -v`
  - [ ] **Owner:** @Analytics-Team

#### FRIDAY (May 18) — Priority 4 (Measurement Gate)

- [ ] **Priority 4: Measurement & Validation** (1-2 hours)
  - [ ] **Token Audit**
    - [ ] Run 100 real signals through AIFilter
    - [ ] Check OpenRouter API logs
    - [ ] Measure: avg, p95, p99 tokens
    - [ ] **Target:** ≤160 avg, <300 p95
    - [ ] **Result:** ✅ / ❌
  
  - [ ] **Latency Audit**
    - [ ] Run 100 signals through validate_signal()
    - [ ] Measure: p50, p95, p99 milliseconds
    - [ ] **Target:** <300ms p50, <600ms p95, <1200ms p99
    - [ ] **Result:** ✅ / ❌
  
  - [ ] **Regime Consistency**
    - [ ] Run identical signal 50 times
    - [ ] Verify same regime every time
    - [ ] **Target:** 100% consistent
    - [ ] **Result:** ✅ / ❌
  
  - [ ] **Decay Formula Validation**
    - [ ] Generate 10 consecutive signals
    - [ ] Verify e^(-0.15 × (n-1)) decay curve
    - [ ] **Target:** Monotonic decrease
    - [ ] **Result:** ✅ / ❌
  
  - [ ] **Liquidity State Impact**
    - [ ] Test thin/normal/heavy inputs
    - [ ] Verify different regimes for same signal
    - [ ] **Target:** thin changes regime vs. heavy
    - [ ] **Result:** ✅ / ❌

### 🚪 GATE DECISION (Friday EOD, May 18)

**All Success Criteria Met?**

- [ ] Tokens: ≤160 avg ✅
- [ ] Latency p95: <600ms ✅
- [ ] Regime consistency: 100% ✅
- [ ] Decay formula: Valid ✅
- [ ] Liquidity impact: Working ✅
- [ ] Unit tests: All green ✅
- [ ] Analytics: Connected to Postgres ✅

**Decision:**
- [ ] **GO** → Proceed to paper trading (May 23)
- [ ] **NO-GO** → Extend by 3-5 days (identify blockers)

**Gate Owner:** @Project-Manager  
**Gate Meeting:** Friday 15:00 UTC (30 min)

---

## 📊 PHASE 2: PAPER TRADING (May 23-27)

Once gate is GREEN:

- [ ] Deploy to paper trading environment
- [ ] Run with 0.1% risk per signal (safe mode)
- [ ] Collect metrics:
  - [ ] Win rate per regime
  - [ ] Avg slippage
  - [ ] Timeout incidents
  - [ ] Avoid regime loss reduction
- [ ] Mid-week review (May 25)
- [ ] 100+ trades per regime (sample size)
- [ ] **Result:** Green light for demo?

---

## 📈 PHASE 3: DEMO VALIDATION (May 28-30)

Once paper trading passes:

- [ ] Deploy to demo account (Bybit testnet)
- [ ] Run with 0.5% risk per signal
- [ ] Backtest: AI vs. rule-based
- [ ] Measure win rate improvement
- [ ] **Target:** +3-5% vs. rule-based
- [ ] **Result:** Ready for live?

---

## 🚀 PHASE 4: LIVE TRADING (May 30+)

Once demo passes:

- [ ] Deploy to live with 0.5% risk per signal
- [ ] Monitor daily AI report
- [ ] Track: regimes, win_rates, sharpes
- [ ] Daily standup: #ai-trading
- [ ] Weekly review with leadership

---

## 🎯 SUCCESS CRITERIA (Must Have ALL)

| Metric | Target | Status |
|--------|--------|--------|
| Token usage | ≤160 avg | ⏳ Friday |
| Latency p95 | <600ms | ⏳ Friday |
| Regime consistency | 100% | ⏳ Friday |
| Unit tests | All green | ⏳ Today |
| Analytics connected | Postgres live | ⏳ Tomorrow |
| Paper trade win rate | >52% | ⏳ May 27 |
| Demo test result | +3-5% vs. rule | ⏳ May 30 |
| Live trading profitability | Positive | ⏳ June 30 |

---

## 👥 TEAM ASSIGNMENTS

| Task | Owner | Slack | Deadline |
|------|-------|-------|----------|
| Liquidity state wiring | @Execution-Platform | #ai-trading | Today EOD |
| Unit test expansion | @QA-Engineer | #ai-trading | Today EOD |
| Analytics to Postgres | @Analytics-Team | #ai-trading | Tomorrow EOD |
| Measurement audits | @AI-Infrastructure-Lead | #ai-trading | Friday EOD |
| Gate decision | @Project-Manager | #ai-trading | Friday 15:00 UTC |
| Paper trading deploy | @DevOps-Team | #ai-trading | May 23 |
| Daily monitoring | @Trading-Ops | #ai-trading | Ongoing |

---

## ⚠️ BLOCKERS & ESCALATION

### If Blocked:

1. **Check:** Is the blocker listed below?
2. **Try:** Suggested fix
3. **If stuck:** Slack @Project-Manager + @AI-Infrastructure-Lead
4. **Do not:** Skip gate decision (will delay paper trading)

### Common Blockers

| Blocker | Suggested Fix | Escalate |
|---------|---------------|----------|
| Liquidity state not showing in logs | Check if market_context passed correctly | @Execution-Platform |
| Unit tests failing | Run individual test to debug | @QA-Engineer |
| Postgres connection error | Check migration ran; verify DSN | @Analytics-Team |
| Token count >350 | Check OpenRouter logs; investigate schema | @AI-Infrastructure-Lead |
| Latency p95 >1000ms | Check OpenRouter load; try local fallback | @AI-Infrastructure-Lead |

---

## 📞 DAILY STANDUP (10:00 UTC)

**Format:** 5 min, #ai-trading Slack

**Report:**
- Today's completion: "✅ Liquidity wired, tests passing"
- Tomorrow's work: "Unit test expansion, analytics connection"
- Blockers: "None" or "Issue: XYZ, needs @Owner help"

**Who:** All team members working on this project

**Frequency:** Every weekday (May 16-May 20)

---

## 📄 KEY DOCUMENTS

**Read in order:**
1. [EXECUTIVE_SUMMARY_AI_REGIME_FILTER.md](EXECUTIVE_SUMMARY_AI_REGIME_FILTER.md) — For leadership
2. [IMPLEMENTATION_STATUS_UPDATE_MAY16.md](IMPLEMENTATION_STATUS_UPDATE_MAY16.md) — Full context
3. [CONTINUATION_PLAN_AI_REGIME_FILTER.md](CONTINUATION_PLAN_AI_REGIME_FILTER.md) — Detailed tasks
4. **THIS FILE** — Daily checklist

---

## 🎉 SUCCESS = Paper Trading by May 23

If ALL checkboxes ✅ by Friday EOD:
- Gate decision: **GO** ✅
- Paper trading starts: **May 23** 🚀
- Live trading: **May 30+** (pending validation)
- Revenue impact: **+$180K+/year** 💰

---

## 📝 Notes Section

**For team to fill in:**

### Day 1 (Today) Progress
```
Completed:
- 

Blockers:
- 

Next:
- 
```

### Day 2 (Tomorrow) Progress
```
Completed:
- 

Blockers:
- 

Next:
- 
```

### Day 3 (Friday) Progress
```
Completed:
- 

Blockers:
- 

Gate Decision: GO / NO-GO
Reason:
```

---

## 🔗 Quick Links

- AI Filter Source: `app/strategy/ai_filter/ai_filter.py`
- News Guard: `app/runtime/news_guard.py`
- Signal Agent: `app/execution/agents/signal_agent.py`
- Analytics: `app/analytics/ai_edge_tracker.py`
- Tests: `tests/unit/test_ai_filter_regime.py`
- Daily Report: `app/analytics/daily_ai_report.py`

---

**Last Updated:** May 16, 2026  
**Status:** READY TO EXECUTE  
**Next Update:** Daily standup (10:00 UTC)

**Print this. Laminate it. Put it on your desk. Reference it daily.**

