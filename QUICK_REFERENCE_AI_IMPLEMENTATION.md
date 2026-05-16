# Quick Reference: AI Regime Filter Implementation

**Print this or bookmark for easy access during implementation.**

---

## TL;DR: What We're Building

Transform Claude from "judge my signal quality" → "classify market regime"

- **Before:** Signal → AI (evaluates) → Risk (validates) → Execution
- **After:** Signal → Risk (validates) → AI (classifies) → Execution
- **Impact:** 73% fewer tokens, 70% faster, 30-50% fewer AI calls, institutional-grade

---

## The Four Regimes (Remember These!)

| Regime | Multiplier | When | Action |
|--------|-----------|------|--------|
| 🟢 supportive | 1.1 | Session OK + DXY OK + news OK + liquidity good | **Boost** |
| ⚪ neutral | 1.0 | Mixed signals | **No change** |
| 🔴 hostile | 0.85 | Session bad OR DXY bad OR liquidity thin | **Reduce** |
| ⛔ avoid | 0.0 | Dead liquidity, news crush, fake moves | **SKIP** |

---

## File Changes at a Glance

```
app/runtime/execution_engine.py          ← Reorder: Risk BEFORE AI
app/strategy/ai_filter/ai_filter.py      ← Main changes (activate, regime, timeout)
app/runtime/news_guard.py                ← Add liquidity_state()
app/analytics/ai_edge_tracker.py         ← NEW: track AI effectiveness
tests/unit/test_ai_filter_regime.py      ← NEW: 8 test cases
```

---

## Task Checklist (10 Total, ~12 hours)

- [ ] **1.** Reorder architecture (2h) — execution_engine.py
- [ ] **2.** Activate Anthropic client (1.5h) — ai_filter.py `__init__`
- [ ] **3.** Build system prompt (1h) — `_build_system_prompt()`
- [ ] **4.** Build user prompt (2h) — `_build_regime_prompt()`
- [ ] **5.** Add hard timeout (1.5h) — `_call_claude_regime()` + timeout wrapper
- [ ] **6.** Add liquidity state (1.5h) — news_guard.py
- [ ] **7.** Track consecutive signals (1h) — decay logic
- [ ] **8.** Analytics tracker (1.5h) — ai_edge_tracker.py
- [ ] **9.** Regime enums (0.5h) — constants
- [ ] **10.** Unit tests (2h) — test_ai_filter_regime.py

---

## System Prompt (Memorize This)

```
You classify XAUUSDT market conditions into regimes.

Evaluate ONLY:
- Session alignment
- DXY alignment
- News safety
- Liquidity quality
- Volume confirmation

Return ONLY valid JSON: {"regime":"supportive|neutral|hostile|avoid","multiplier":1.1|1.0|0.85|0.0}
```

**Production rule:** NO reasoning. No explanations. Just regime + multiplier.

---

## Compressed Schema (User Prompt)

```json
{
  "sig": "LONG",
  "conf": 0.68,
  "strat": "opening_reversal",
  "m": {
    "s": "LO",
    "d": "UP", 
    "n": 1,
    "v": "H",
    "l": "heavy",
    "vol": "exp"
  }
}
```

**Key:**
- s = session (LO/LC/NO/NC/D)
- d = DXY (UP/DN/F)
- n = news events
- v = volume (L/N/H)
- l = liquidity (thin/normal/heavy)
- vol = volatility (comp/stable/exp)

---

## Confidence Adjustment Formula

```python
# 1. Apply regime multiplier (multiplicative, not additive!)
adjusted = base_confidence * multiplier

# 2. Apply decay for consecutive signals
decay = e^(-0.15 * consecutive_count)
adjusted *= decay

# 3. Enforce floor (never eliminate signal)
adjusted = max(adjusted, 0.30)
adjusted = min(adjusted, 1.0)
```

---

## Hard Timeout Pattern

```python
try:
    response = await asyncio.wait_for(
        ai_call(),
        timeout=1.2  # Hard stop
    )
except asyncio.TimeoutError:
    # Fallback: neutral regime (multiplier=1.0)
    return (regime="neutral", multiplier=1.0)
```

**Key rule:** Execution NEVER blocks on AI. Always continue.

---

## Testing (8 Required Tests)

1. System prompt generates expected string
2. User prompt <150 tokens, valid JSON
3. Timeout triggers fallback (neutral regime)
4. Confidence multiplied correctly (not added)
5. Decay formula applied: e^(-0.15n)
6. Confidence floor enforced (>=0.30)
7. Avoid regime returns None (signal rejected)
8. Malformed JSON falls back to neutral

---

## Success Metrics (Post-Launch)

| Metric | Target | Check Method |
|--------|--------|---|
| **Tokens** | ≤160 (-73%) | API logs on 100 signals |
| **Latency p95** | <600ms (-70%) | Measure validate_signal() |
| **AI calls** | -30-50% | Count pre/post reorder |
| **Regime consistency** | 100% | 50 identical signals |
| **Avoid regime edge** | 50%+ loss reduction | Compare trades |
| **Supportive regime edge** | +3% win rate | 100 trades AI vs. baseline |

---

## Common Mistakes to Avoid

❌ **Don't:** Add reasoning to production prompt (wastes 20-40 tokens)  
✓ **Do:** Keep reasoning only for debug mode

❌ **Don't:** Use additive confidence adjustment (0.68 + 0.15 = 0.83)  
✓ **Do:** Use multiplicative (0.68 × 1.1 = 0.748)

❌ **Don't:** Call AI before risk validation (wastes tokens)  
✓ **Do:** Call risk validation first, then AI only on valid signals

❌ **Don't:** Block execution on AI timeout  
✓ **Do:** Hard timeout 1.2s, fallback to neutral, continue execution

❌ **Don't:** Let confidence inflate on consecutive signals  
✓ **Do:** Apply decay: e^(-0.15 × consecutive_count)

---

## How to Claim a Task

1. Go to Discord #ai-trading
2. Comment: "Claiming Task 5 (Hard Timeout)" 
3. Assign yourself in the implementation doc
4. Work locally; test on your machine
5. Open PR with task name + status doc link
6. After review → merge → move to next task

---

## Key Files to Study Before Starting

- `app/strategy/indicators.py` — Code style reference
- `app/runtime/news_guard.py` — How market context is built
- `app/strategy/signal_proposal.py` — Signal structure
- `tests/unit/test_signal_proposal.py` — How to write tests
- `plan-optimizeValidationPrompt.prompt.md` — Full context

---

## Decision Log

**Why regime multipliers instead of confidence adjustment?**  
→ Mathematically stable, preserves signal ordering, backtestable

**Why remove reasoning in production?**  
→ Saves 20-40 tokens, eliminates JSON malformation, no hallucinations

**Why hard timeout 1.2s?**  
→ Execution must never block; 1.2s covers 99th percentile + margin

**Why liquidity state?**  
→ Gold trades completely differently before London, after lunch, rollover

**Why four regimes (not three)?**  
→ "Avoid" is the most profitable — avoiding bad trades > finding good ones

---

## Rollout Timeline

- **Week 1:** Tasks 1-10 complete, tests passing, PR merged
- **Week 1.5:** Analytics live, daily reports running
- **Week 2:** Paper trading 5 days, demo validation
- **Week 3+:** Live trading + Phase 2 (prompt caching, local classifiers)

---

## Slack Channel

**#ai-trading** — Questions, blockers, status updates

**Owner:** @AI-Infrastructure-Lead  
**PM:** @Project-Manager  
**QA:** @QA-Engineer

---

**Last Updated:** 2026-05-16  
**Status:** READY FOR IMPLEMENTATION  
**Time Estimate:** 12 hours (Week 1)
