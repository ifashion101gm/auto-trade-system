"""
Paper Trading Validator — Phase 2 validation harness.

Runs a batch of synthetic XAUUSDT signals through the full
StrategyManager → AIFilter pipeline and measures:
  - Regime consistency (same input → same output)
  - Token estimate per call
  - AI call latency (p50 / p95 / p99)
  - Avoid-rate (% of signals blocked)
  - Confidence adjustment distribution

Does NOT place real orders. Safe to run against live Anthropic API.
"""
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from app.analytics.daily_ai_report import DailyAIReport
from app.logging_config import get_logger
from app.strategy.ai_filter.ai_filter import AIFilter, Regime
from app.strategy.signal_proposal import SignalProposal

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Synthetic signal fixtures covering all market states
# ---------------------------------------------------------------------------

_SIGNAL_FIXTURES: List[Dict[str, Any]] = [
    # London open — supportive
    {"side": "LONG",  "confidence": 0.78, "session": "london_open",  "dxy_trend": "down",  "volume_state": "high",   "liquidity_state": "heavy",  "news_events": 0, "volatility_regime": "stable"},
    # NY open — supportive
    {"side": "LONG",  "confidence": 0.75, "session": "ny_open",      "dxy_trend": "down",  "volume_state": "high",   "liquidity_state": "heavy",  "news_events": 0, "volatility_regime": "stable"},
    # Dead session — hostile
    {"side": "LONG",  "confidence": 0.70, "session": "dead",         "dxy_trend": "up",    "volume_state": "low",    "liquidity_state": "thin",   "news_events": 0, "volatility_regime": "volatile"},
    # News event — avoid
    {"side": "SHORT", "confidence": 0.80, "session": "ny_open",      "dxy_trend": "flat",  "volume_state": "normal", "liquidity_state": "normal", "news_events": 1, "volatility_regime": "stable"},
    # Rollover — thin liquidity
    {"side": "SHORT", "confidence": 0.72, "session": "dead",         "dxy_trend": "flat",  "volume_state": "low",    "liquidity_state": "thin",   "news_events": 0, "volatility_regime": "volatile"},
    # London open SHORT — DXY up (hostile for gold short? neutral)
    {"side": "SHORT", "confidence": 0.76, "session": "london_open",  "dxy_trend": "up",    "volume_state": "normal", "liquidity_state": "heavy",  "news_events": 0, "volatility_regime": "stable"},
    # NY open — neutral
    {"side": "LONG",  "confidence": 0.65, "session": "ny_open",      "dxy_trend": "flat",  "volume_state": "normal", "liquidity_state": "normal", "news_events": 0, "volatility_regime": "stable"},
    # High volatility breakout
    {"side": "LONG",  "confidence": 0.82, "session": "london_open",  "dxy_trend": "down",  "volume_state": "high",   "liquidity_state": "heavy",  "news_events": 0, "volatility_regime": "volatile"},
    # Thin liquidity SHORT
    {"side": "SHORT", "confidence": 0.68, "session": "dead",         "dxy_trend": "up",    "volume_state": "low",    "liquidity_state": "thin",   "news_events": 0, "volatility_regime": "stable"},
    # NY close — normal
    {"side": "LONG",  "confidence": 0.71, "session": "ny_close",     "dxy_trend": "flat",  "volume_state": "normal", "liquidity_state": "normal", "news_events": 0, "volatility_regime": "stable"},
]


@dataclass
class ValidationResult:
    fixture_idx: int
    side: str
    base_confidence: float
    adjusted_confidence: Optional[float]
    regime: str
    latency_ms: float
    passed: bool          # True = signal survived filter
    token_estimate: int   # rough: len(prompt_json) / 4


@dataclass
class ValidationReport:
    total_signals: int = 0
    passed: int = 0
    avoided: int = 0
    results: List[ValidationResult] = field(default_factory=list)
    latencies_ms: List[float] = field(default_factory=list)
    regime_counts: Dict[str, int] = field(default_factory=dict)
    consistency_failures: int = 0

    # Computed after run
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    avg_token_estimate: float = 0.0
    avoid_rate: float = 0.0
    pass_rate: float = 0.0

    def compute(self) -> None:
        if self.latencies_ms:
            sorted_lat = sorted(self.latencies_ms)
            n = len(sorted_lat)
            self.p50_ms = sorted_lat[int(n * 0.50)]
            self.p95_ms = sorted_lat[min(int(n * 0.95), n - 1)]
            self.p99_ms = sorted_lat[min(int(n * 0.99), n - 1)]
        self.avoid_rate = self.avoided / self.total_signals if self.total_signals else 0.0
        self.pass_rate = self.passed / self.total_signals if self.total_signals else 0.0
        if self.results:
            self.avg_token_estimate = statistics.mean(r.token_estimate for r in self.results)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_signals": self.total_signals,
            "passed": self.passed,
            "avoided": self.avoided,
            "pass_rate": round(self.pass_rate, 4),
            "avoid_rate": round(self.avoid_rate, 4),
            "latency_p50_ms": round(self.p50_ms, 1),
            "latency_p95_ms": round(self.p95_ms, 1),
            "latency_p99_ms": round(self.p99_ms, 1),
            "avg_token_estimate": round(self.avg_token_estimate, 1),
            "regime_counts": self.regime_counts,
            "consistency_failures": self.consistency_failures,
            "targets": {
                "p95_ms_target": 600,
                "p95_ms_ok": self.p95_ms < 600,
                "token_target": 160,
                "token_ok": self.avg_token_estimate < 160,
                "avoid_rate_target": ">0%",
                "consistency_ok": self.consistency_failures == 0,
            },
        }


class PaperTradingValidator:
    """
    Runs synthetic signals through AIFilter and measures Phase 2 success criteria.

    Args:
        ai_filter: AIFilter instance (uses live Anthropic API by default).
                   Pass a mock for offline testing.
        daily_report: Optional DailyAIReport to accumulate stats.
        repetitions: How many times to repeat each fixture (for consistency check).
    """

    def __init__(
        self,
        ai_filter: Optional[AIFilter] = None,
        daily_report: Optional[DailyAIReport] = None,
        repetitions: int = 2,
    ):
        self.ai_filter = ai_filter or AIFilter()
        self.daily_report = daily_report or DailyAIReport()
        self.repetitions = repetitions

    def _make_signal(self, fixture: Dict[str, Any]) -> SignalProposal:
        return SignalProposal(
            symbol="XAUUSDT",
            side=fixture["side"],
            entry_price=2350.0,
            stop_loss=2330.0,
            take_profit=2390.0,
            quantity=0.01,
            confidence=fixture["confidence"],
            strategy_name="gold_opening_reversal",
        )

    def _make_context(self, fixture: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "session": fixture["session"],
            "dxy_trend": fixture["dxy_trend"],
            "news_events": fixture["news_events"],
            "volume_state": fixture["volume_state"],
            "liquidity_state": fixture["liquidity_state"],
            "volatility_regime": fixture["volatility_regime"],
        }

    async def _run_single(
        self, fixture: Dict[str, Any], fixture_idx: int
    ) -> ValidationResult:
        signal = self._make_signal(fixture)
        context = self._make_context(fixture)
        base_conf = signal.confidence

        # Estimate tokens from prompt length
        prompt_json = self.ai_filter._build_regime_prompt(signal, context)
        token_estimate = max(1, len(prompt_json) // 4) + 80  # +80 for system prompt

        t0 = time.perf_counter()
        result = await self.ai_filter.validate_signal(signal, context)
        latency_ms = (time.perf_counter() - t0) * 1000

        regime = signal.metadata.get("regime", "avoid") if result is None else result.metadata.get("regime", "neutral")
        passed = result is not None
        adj_conf = result.confidence if result else None

        if passed:
            self.daily_report.record_signal_executed(
                regime=regime,
                base_confidence=base_conf,
                adjusted_confidence=adj_conf,
                multiplier=signal.metadata.get("multiplier", 1.0) if result else 0.0,
            )
        else:
            self.daily_report.record_avoid(regime=regime)

        return ValidationResult(
            fixture_idx=fixture_idx,
            side=fixture["side"],
            base_confidence=base_conf,
            adjusted_confidence=adj_conf,
            regime=regime,
            latency_ms=latency_ms,
            passed=passed,
            token_estimate=token_estimate,
        )

    async def run(self, fixtures: Optional[List[Dict]] = None) -> ValidationReport:
        """
        Run all fixtures (repeated `repetitions` times) through the AI filter.

        Returns a ValidationReport with latency, token, and consistency metrics.
        """
        fixtures = fixtures or _SIGNAL_FIXTURES
        report = ValidationReport()

        # Run each fixture `repetitions` times to check consistency
        first_pass_regimes: Dict[int, str] = {}

        for rep in range(self.repetitions):
            for idx, fixture in enumerate(fixtures):
                # Reset filter state between runs to avoid decay interference
                self.ai_filter.consecutive_signals = {"LONG": 0, "SHORT": 0}
                self.ai_filter.last_signal_side = None

                result = await self._run_single(fixture, idx)
                report.total_signals += 1
                report.results.append(result)
                report.latencies_ms.append(result.latency_ms)
                report.regime_counts[result.regime] = report.regime_counts.get(result.regime, 0) + 1

                if result.passed:
                    report.passed += 1
                else:
                    report.avoided += 1

                # Consistency check: same fixture should produce same regime across reps
                if rep == 0:
                    first_pass_regimes[idx] = result.regime
                elif result.regime != first_pass_regimes.get(idx):
                    report.consistency_failures += 1
                    logger.warning(
                        "⚠️  Consistency failure fixture=%d: rep0=%s rep%d=%s",
                        idx, first_pass_regimes.get(idx), rep, result.regime,
                    )

        report.compute()
        self._log_report(report)
        return report

    def _log_report(self, report: ValidationReport) -> None:
        s = report.summary()
        logger.info("=" * 60)
        logger.info("📋 Paper Trading Validation Report")
        logger.info("  Signals: %d  Passed: %d  Avoided: %d", s["total_signals"], s["passed"], s["avoided"])
        logger.info("  Pass rate: %.1f%%  Avoid rate: %.1f%%", s["pass_rate"] * 100, s["avoid_rate"] * 100)
        logger.info("  Latency  p50=%.0fms  p95=%.0fms  p99=%.0fms", s["latency_p50_ms"], s["latency_p95_ms"], s["latency_p99_ms"])
        logger.info("  Avg token estimate: %.0f  (target <160)", s["avg_token_estimate"])
        logger.info("  Regime counts: %s", s["regime_counts"])
        logger.info("  Consistency failures: %d", s["consistency_failures"])
        t = s["targets"]
        logger.info("  ✅ p95 <600ms: %s | ✅ tokens <160: %s | ✅ consistent: %s",
                    t["p95_ms_ok"], t["token_ok"], t["consistency_ok"])
        logger.info("=" * 60)
