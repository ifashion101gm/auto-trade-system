# Implementation Status: AI Regime Filter Optimization

**Last Updated:** May 16, 2026  
**Phase:** 1 (Core Optimization + Reordering)  
**Owner:** AI Infrastructure Team  
**Status:** READY FOR IMPLEMENTATION

---

## Executive Summary

Converting Claude from "confidence adjuster" to "regime classifier" for XAUUSDT trading. Expected improvements: 73% token reduction (520→160), 70% latency reduction (2000ms→600ms), and 30-50% fewer AI calls.

**Timeline:** Week 1 (~12 hours), Week 2 (~4 hours analytics), Week 3+ (advanced)

---

## Current State (Baseline)

### What Works ✓
- Strategy engine generates signals (gold_opening_reversal.py)
- Risk engine validates positions
- Anthropic API key in config.py
- Infrastructure: Redis, Postgres, self-healing watchdogs

### What's Broken ✗
- AI filter is **wired but disabled** (`self.router = None` in ai_filter.py)
- Architecture: Signal → AI → Risk (backwards; should be Signal → Risk → AI)
- Prompt: Verbose (~520 tokens), uses confidence adjustment (additive, unstable)
- Missing: Liquidity state, hard timeout, confidence decay
- Analytics: No tracking of AI effectiveness per regime
- No "avoid" regime (critical for gold; avoiding bad trades > finding good ones)

### Current Token Profile
- System prompt embedded in every call: ~180 tokens
- User context (verbose): ~140 tokens
- Reasoning output (wasted in production): ~20-40 tokens
- **Total:** ~520 tokens per call ❌

---

## Implementation Plan: Phase 1 (Week 1, ~12 hours)

### Task 1: Reorder Architecture (2 hours)
**File:** `app/runtime/execution_engine.py`

Current flow:
```
Signal → AI Filter → Risk Validation → Execution
```

New flow:
```
Signal → Risk Validation → AI Filter → Execution Gate
```

**What to change:**
- Move `risk_engine.validate()` call BEFORE `ai_filter.validate_signal()`
- Add comment: "Risk engine filters invalid trades first; AI only classifies valid signals"
- Expected result: 30-50% fewer AI calls (don't waste tokens on invalid trades)

**Owner:** Execution Infrastructure  
**Acceptance:** Confirmed in code review that risk validation runs before AI

---

### Task 2: Activate Anthropic Client (1.5 hours)
**File:** `app/strategy/ai_filter/ai_filter.py`, `__init__` method

Current (broken):
```python
self.router = None  # ← DISABLED
```

New (activated):
```python
self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
self.model = "claude-sonnet-4-20250514"
self.system_prompt = self._build_system_prompt()
```

**What to add:**
1. Import: `import anthropic`
2. Initialize `self.client` with API key from settings
3. Set `self.model` to latest Sonnet 4 (currently claude-sonnet-4-20250514)
4. Build system prompt once and store in `self.system_prompt` (reused for all calls)

**Owner:** AI Integration  
**Acceptance:** `anthropic.Anthropic()` initializes without errors; API key validated

---

### Task 3: Build System Prompt (1 hour)
**File:** `app/strategy/ai_filter/ai_filter.py`, add new method `_build_system_prompt()`

**Implementation:**
```python
def _build_system_prompt(self) -> str:
    return """You classify XAUUSDT market conditions into regimes.

Evaluate ONLY:
- Session alignment (is signal appropriate for active session?)
- DXY alignment (is USD strength supporting signal direction?)
- News safety (major economic events within 45min?)
- Liquidity quality (is the liquidity regime solid?)
- Volume confirmation (is volume supporting the move?)

Return ONLY valid JSON. No explanations. No reasoning.
Response format: {"regime":"supportive|neutral|hostile|avoid","multiplier":1.1|1.0|0.85|0.0}"""
```

**Owner:** Prompt Engineering  
**Acceptance:** System prompt returns expected string; no syntax errors

---

### Task 4: Build Compressed User Prompt (2 hours)
**File:** `app/strategy/ai_filter/ai_filter.py`, replace `_build_validation_prompt()` with `_build_regime_prompt()`

**Implementation:**
```python
def _build_regime_prompt(self, signal, market_context) -> str:
    """Build compact regime classification prompt."""
    return json.dumps({
        "sig": signal.side.upper(),
        "conf": round(signal.confidence, 2),
        "strat": signal.strategy_name,
        "m": {
            "s": self._session_to_code(market_context.get("session")),
            "d": self._dxy_trend_to_code(market_context.get("dxy_trend")),
            "n": market_context.get("news_events", 0),
            "v": self._volume_to_code(market_context.get("volume_state")),
            "l": market_context.get("liquidity_state", "normal"),
            "vol": market_context.get("volatility_regime", "stable")
        }
    })

def _session_to_code(self, session: str) -> str:
    mapping = {
        "london_open": "LO",
        "london_close": "LC",
        "ny_open": "NO",
        "ny_close": "NC",
        "dead": "D"
    }
    return mapping.get(session, "D")

def _dxy_trend_to_code(self, trend: str) -> str:
    mapping = {"up": "UP", "down": "DN", "flat": "F"}
    return mapping.get(trend.lower(), "F")

def _volume_to_code(self, volume: str) -> str:
    mapping = {"low": "L", "normal": "N", "high": "H"}
    return mapping.get(volume.lower(), "N")
```

**Owner:** Prompt Engineering  
**Acceptance:** Generates valid JSON; all schema fields populated; <150 tokens

---

### Task 5: Add Hard Timeout & Fallback (1.5 hours)
**File:** `app/strategy/ai_filter/ai_filter.py`, update `validate_signal()` method

**Implementation:**
```python
async def validate_signal(self, signal, market_context) -> Optional[SignalProposal]:
    """Validate signal with hard timeout and fallback."""
    try:
        # Hard timeout: 1.2 seconds max
        response = await asyncio.wait_for(
            self._call_claude_regime(signal, market_context),
            timeout=1.2
        )
        regime_data = json.loads(response)
        regime = regime_data.get("regime", "neutral")
        multiplier = regime_data.get("multiplier", 1.0)
        
    except asyncio.TimeoutError:
        logger.warning("AI timeout; falling back to neutral regime")
        regime = "neutral"
        multiplier = 1.0
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"AI parse error: {e}; falling back to neutral")
        regime = "neutral"
        multiplier = 1.0
    
    # Apply regime multiplier
    adjusted_confidence = signal.confidence * multiplier
    
    # Apply confidence decay (consecutive signals)
    decay_factor = math.exp(-0.15 * self.consecutive_signals.get(signal.side, 0))
    adjusted_confidence *= decay_factor
    
    # Enforce confidence floor
    adjusted_confidence = max(adjusted_confidence, 0.30)
    adjusted_confidence = min(adjusted_confidence, 1.0)
    
    signal.confidence = adjusted_confidence
    signal.metadata["regime"] = regime
    signal.metadata["multiplier"] = multiplier
    
    return signal if regime != "avoid" else None

async def _call_claude_regime(self, signal, market_context):
    """Call Claude for regime classification."""
    user_prompt = self._build_regime_prompt(signal, market_context)
    response = self.client.messages.create(
        model=self.model,
        max_tokens=100,
        messages=[{"role": "user", "content": user_prompt}],
        system=self.system_prompt,
        temperature=0  # Deterministic
    )
    return response.content[0].text
```

**Owner:** Timeout/Error Handling  
**Acceptance:** Timeout test triggers fallback; parse errors logged; execution continues

---

### Task 6: Add Liquidity State to Market Context (1.5 hours)
**File:** `app/runtime/news_guard.py`, add method `compute_liquidity_state()`

**Implementation:**
```python
def compute_liquidity_state(self, current_time_utc: datetime) -> str:
    """Determine gold liquidity regime based on time of day."""
    hour = current_time_utc.hour
    
    # Thin liquidity: before London, after NY lunch, during rollover
    if hour in [0, 1, 2, 3, 4, 5, 6, 7]:  # Before London opens (7:50)
        return "thin"
    elif hour in [12, 13]:  # NY lunch
        return "thin"
    elif hour in [20, 21, 22]:  # Rollover period
        return "thin"
    
    # Heavy liquidity: London mid-session, NY open
    elif hour in [8, 9, 10]:  # London mid
        return "heavy"
    elif hour in [14, 15, 16]:  # NY open/mid
        return "heavy"
    
    # Normal: everything else
    else:
        return "normal"
```

Add to market context dict passed to AI filter:
```python
market_context["liquidity_state"] = news_guard.compute_liquidity_state(datetime.now(timezone.utc))
```

**Owner:** Market Context  
**Acceptance:** Returns correct liquidity enum; integrated into market_context

---

### Task 7: Track Consecutive Signals (1 hour)
**File:** `app/strategy/ai_filter/ai_filter.py`, add tracking logic

**Implementation:**
```python
def __init__(self, ...):
    # ... existing init code ...
    self.consecutive_signals = {"LONG": 0, "SHORT": 0}
    self.last_signal_side = None

def _update_signal_tracking(self, signal_side: str):
    """Track consecutive same-direction signals for decay."""
    if signal_side == self.last_signal_side:
        self.consecutive_signals[signal_side] += 1
    else:
        self.consecutive_signals[signal_side] = 1
        self.last_signal_side = signal_side

def _reset_signal_tracking(self, signal_side: str):
    """Reset tracking after trade execution."""
    self.consecutive_signals[signal_side] = 0
```

**Owner:** Signal Tracking  
**Acceptance:** Consecutive counter increments correctly; resets on direction change

---

### Task 8: Implement AI Effectiveness Analytics (1.5 hours)
**File:** Create `app/analytics/ai_edge_tracker.py` (NEW FILE)

**Implementation:**
```python
"""Track AI regime classifier effectiveness."""
import json
from datetime import datetime
from typing import Dict, List
from app.logging_config import get_logger

logger = get_logger(__name__)

class AIEdgeTracker:
    """Track AI filter performance by regime."""
    
    def log_signal_executed(self, regime: str, base_confidence: float, 
                           adjusted_confidence: float, multiplier: float):
        """Log signal execution with AI adjustment."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "regime": regime,
            "base_confidence": base_confidence,
            "adjusted_confidence": adjusted_confidence,
            "multiplier": multiplier,
            "pnl": None  # Will be filled post-trade
        }
        # Log to Postgres (insert into trades table)
        logger.info(f"AI signal: regime={regime}, conf={base_confidence}→{adjusted_confidence}")
    
    def log_trade_close(self, trade_id: str, pnl: float, regime: str):
        """Log trade outcome for edge tracking."""
        # Update Postgres: UPDATE trades SET pnl=?, regime=? WHERE id=?
        logger.info(f"Trade {trade_id} closed: pnl={pnl}, regime={regime}")
    
    def get_regime_stats(self, regime: str) -> Dict:
        """Get win rate, sharpe, avg_win/loss for regime."""
        # Query Postgres:
        # SELECT COUNT(*) trades, 
        #        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)/COUNT(*) win_rate,
        #        AVG(pnl) avg_pnl,
        #        STDDEV(pnl) std_pnl
        # FROM trades WHERE regime = ?
        return {}
```

**Owner:** Analytics  
**Acceptance:** Logger output shows signals and trades; queries can retrieve stats

---

### Task 9: Add Regime Enum Helpers (30 min)
**File:** `app/strategy/ai_filter/ai_filter.py`, add constants

**Implementation:**
```python
from enum import Enum

class Regime(str, Enum):
    """Market regime classification."""
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    HOSTILE = "hostile"
    AVOID = "avoid"

REGIME_MULTIPLIERS = {
    Regime.SUPPORTIVE: 1.1,
    Regime.NEUTRAL: 1.0,
    Regime.HOSTILE: 0.85,
    Regime.AVOID: 0.0
}
```

**Owner:** Code Structure  
**Acceptance:** Enums used consistently throughout ai_filter.py

---

### Task 10: Write Unit Tests (2 hours)
**File:** `tests/unit/test_ai_filter_regime.py` (NEW FILE)

**Test Cases:**
1. `test_system_prompt_generation()` — Verify prompt returns expected string
2. `test_regime_prompt_compression()` — Verify user prompt <150 tokens, valid JSON
3. `test_hard_timeout_fallback()` — Trigger timeout, verify fallback to neutral
4. `test_confidence_multiplier()` — Apply regime 1.1, verify confidence scaled correctly
5. `test_confidence_decay()` — Generate 3 consecutive signals, verify decay curve
6. `test_confidence_floor()` — Signal conf=0.05 + avoid regime, verify final ≥0.30
7. `test_avoid_regime_returns_none()` — Avoid regime should reject signal
8. `test_malformed_json_fallback()` — Invalid Claude response → neutral regime

**Owner:** QA  
**Acceptance:** All 8 tests passing; coverage >90%

---

## Testing & Validation (Week 1, Phase 1.5)

### Unit Tests
- [ ] Prompt generation (system + user)
- [ ] Regime classification (all 4 regimes)
- [ ] Timeout fallback
- [ ] Confidence multiplier math
- [ ] Confidence decay formula
- [ ] Confidence floor enforcement
- [ ] Error handling (malformed JSON, API errors)

### Integration Tests
- [ ] Signal → Risk → AI → Execution order confirmed
- [ ] Market context includes liquidity_state
- [ ] AI call count reduced by 30-50% vs. before
- [ ] Tokens per call ≤160 (measure via API logs)
- [ ] Latency p50 <300ms, p95 <600ms, p99 <1200ms

### Manual Validation
- [ ] 50 test signals across all market states
- [ ] Verify regime assignment makes sense per input
- [ ] Verify confidence adjustment is multiplicative (no inflation)
- [ ] Verify timeout falls back gracefully
- [ ] Verify "avoid" regime stops trades appropriately

**Success Criteria:**
- All tests passing
- Token usage confirmed <160 tokens
- Latency <600ms p95
- Regime consistency 100% (same input = same regime)
- Zero blocking timeouts

---

## Phase 1.5: Analytics Layer (Week 1-2, ~4 hours)

### Task: Implement Daily AI Effectiveness Report

**File:** `app/analytics/daily_ai_report.py` (NEW FILE)

Query trades by regime; calculate:
- win_rate per regime
- avg_win / avg_loss per regime
- sharpe ratio per regime
- total pnl per regime

Alert if any regime underperforms baseline by >3%.

**Owner:** Analytics  
**Acceptance:** Report generated daily; email sent with stats

---

## File Summary

| File | Status | Changes |
|------|--------|---------|
| `app/runtime/execution_engine.py` | TODO | Reorder: Risk → AI (not AI → Risk) |
| `app/strategy/ai_filter/ai_filter.py` | TODO | Activate Anthropic, add regime methods, timeout, decay |
| `app/runtime/news_guard.py` | TODO | Add compute_liquidity_state() |
| `app/analytics/ai_edge_tracker.py` | NEW | Create AI effectiveness tracking |
| `tests/unit/test_ai_filter_regime.py` | NEW | Write 8 test cases |
| `gold_ai_upgrade_plan.html` | TODO | Update "Upgrade 1" section with new approach |

---

## Blockers & Risks

### No Blockers
- Anthropic API key already in config.py ✓
- Market context infrastructure exists ✓
- Postgres for analytics ready ✓

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Timeout blocks execution | Hard timeout with neutral fallback (1.2s max) |
| Regime instability | Test with temperature=0; lock system prompt version |
| Malformed JSON | Strict validation; fall back to neutral on parse error |
| AI edge collapses | Daily effectiveness tracking; ability to disable AI filter |
| Confidence decay too aggressive | Conservative k=0.15; 0.30 confidence floor |

---

## Success Metrics (Post-Launch)

| Metric | Target | How to Measure |
|--------|--------|---|
| Token usage | ≤160 per call (-73%) | Anthropic API logs on 100 real signals |
| Latency p95 | <600ms (-70%) | Measure end-to-end validation time |
| AI call volume | -30-50% vs. before | Count calls pre/post reordering |
| Regime consistency | 100% | Run 50 identical signals; verify match |
| Avoid regime edge | 50%+ loss reduction | Compare: trades with avoid vs. without |
| Supportive regime edge | +3% win rate | Compare: AI vs. rule-based over 100 trades |
| Timeout incidents | <1% of calls | Monitor timeout counter |

---

## How to Contribute

### For New Team Members

1. **Pick a task** from Phase 1 (Tasks 1-10 above)
2. **Claim it**: Comment in Discord #ai-trading with task number + name
3. **Work**: Follow implementation details in task description
4. **Test**: Run unit tests locally; verify all tests pass
5. **PR**: Open PR with task name; link to this doc
6. **Review**: Peer review required before merge

### Code Review Checklist
- [ ] Code follows existing style (see app/strategy/indicators.py)
- [ ] Unit tests added and passing
- [ ] Docstrings present and clear
- [ ] No hardcoded values (use config or constants)
- [ ] Logging added for debugging
- [ ] PR description links to this status doc

### Questions?
- **Technical**: Ask in Discord #ai-trading
- **Architecture**: Tag @AI-Infrastructure-Lead
- **Prompt tuning**: Tag @Prompt-Engineering

---

## Rollout Plan

### Week 1 (May 16-22)
- [ ] Tasks 1-10 complete
- [ ] Unit tests 100% passing
- [ ] Integration tests passed
- [ ] PR merged to main
- [ ] Deploy to staging environment

### Week 1.5 (May 23-24)
- [ ] Analytics layer live
- [ ] Daily AI effectiveness report running
- [ ] Monitoring alerts configured

### Week 2 (May 27 onwards)
- [ ] Paper trading 5 days (no real positions)
- [ ] Demo account validation (0.1% risk)
- [ ] Backtest 100+ signals with AI vs. without
- [ ] Go/no-go decision for live trading

### Week 3+ (Phase 2)
- [ ] Anthropic Prompt Caching (if volume >50 signals/day)
- [ ] Optional OHLCV inclusion for edge cases
- [ ] Dynamic multiplier tuning based on effectiveness
- [ ] Local regime classifier migration (reduce Claude dependency)

---

## Appendix: Regime Definition Reference

| Regime | Multiplier | When | Gold Trading Context |
|--------|-----------|------|---------|
| **supportive** | 1.1 | Session aligned, DXY supporting, news safe, high liquidity, volume confirms | Boost confidence 10% |
| **neutral** | 1.0 | Mixed signals, conflicting factors | No adjustment |
| **hostile** | 0.85 | Session misaligned OR DXY opposing OR low liquidity OR weak volume | Reduce confidence 15% |
| **avoid** | 0.0 | Dead liquidity, news compression, fake moves, rollover, extreme stress | SKIP this trade |

---

## Document Versioning

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-16 | AI Team | Initial implementation plan |

---

**Status:** READY FOR IMPLEMENTATION  
**Owner:** AI Infrastructure Team  
**Next Review:** 2026-05-20 (mid-phase checkpoint)
