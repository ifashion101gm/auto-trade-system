"""Unit tests for Phase 2: DailyAIReport and PaperTradingValidator."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analytics.daily_ai_report import DailyAIReport, RegimeStats
from app.paper_trading.paper_trading_validator import (
    PaperTradingValidator,
    ValidationReport,
    _SIGNAL_FIXTURES,
)
from app.strategy.ai_filter.ai_filter import AIFilter, Regime


# ── RegimeStats ──────────────────────────────────────────────────────────────

def test_regime_stats_win_rate():
    s = RegimeStats()
    s.record_signal()
    s.record_close(10.0)
    s.record_close(-5.0)
    assert s.win_rate == 0.5
    assert s.avg_pnl == 2.5
    assert s.trades_closed == 2


def test_regime_stats_empty():
    s = RegimeStats()
    assert s.win_rate == 0.0
    assert s.avg_pnl == 0.0
    assert s.std_pnl == 0.0


# ── DailyAIReport ────────────────────────────────────────────────────────────

def test_daily_report_accumulates_signals():
    report = DailyAIReport()
    report.record_signal_executed("supportive", 0.75, 0.82, 1.1, trade_id="t1")
    report.record_signal_executed("neutral",    0.70, 0.70, 1.0, trade_id="t2")
    report.record_avoid("avoid")
    result = report.generate()
    assert result["summary"]["total_signals"] == 2
    assert result["summary"]["total_avoided"] == 1
    assert "supportive" in result["by_regime"]
    assert "neutral" in result["by_regime"]


def test_daily_report_trade_close_updates_stats():
    report = DailyAIReport()
    report.record_signal_executed("supportive", 0.75, 0.82, 1.1, trade_id="t1")
    report.record_trade_closed("t1", pnl=15.0, regime="supportive")
    result = report.generate()
    assert result["by_regime"]["supportive"]["trades_closed"] == 1
    assert result["by_regime"]["supportive"]["wins"] == 1
    assert result["by_regime"]["supportive"]["total_pnl"] == 15.0


def test_daily_report_alert_on_underperforming_regime():
    report = DailyAIReport()
    # 10 supportive wins
    for i in range(10):
        report.record_signal_executed("supportive", 0.75, 0.82, 1.1)
        report.record_trade_closed(f"s{i}", pnl=10.0, regime="supportive")
    # 5 hostile losses — win_rate 0% vs baseline ~67%
    for i in range(5):
        report.record_signal_executed("hostile", 0.70, 0.60, 0.85)
        report.record_trade_closed(f"h{i}", pnl=-5.0, regime="hostile")
    result = report.generate()
    assert len(result["alerts"]) > 0
    assert "hostile" in result["alerts"][0]


def test_daily_report_no_alert_when_insufficient_trades():
    report = DailyAIReport()
    # Only 3 hostile trades — below the 5-trade threshold for alerts
    for i in range(3):
        report.record_signal_executed("hostile", 0.70, 0.60, 0.85)
        report.record_trade_closed(f"h{i}", pnl=-5.0, regime="hostile")
    result = report.generate()
    assert result["alerts"] == []


# ── PaperTradingValidator (mocked AI) ────────────────────────────────────────

def _make_mock_filter(regime: str = "neutral"):
    """Return an AIFilter whose _call_openrouter_regime always returns given regime."""
    multipliers = {"supportive": 1.1, "neutral": 1.0, "hostile": 0.85, "avoid": 0.0}

    async def mock_call(*_, **__):
        return json.dumps({"regime": regime, "multiplier": multipliers[regime]})

    with patch("app.strategy.ai_filter.ai_filter.OpenRouterClient"):
        f = AIFilter()

    f._call_openrouter_regime = mock_call
    return f


@pytest.mark.asyncio
async def test_validator_all_neutral_pass():
    ai_filter = _make_mock_filter("neutral")
    validator = PaperTradingValidator(ai_filter=ai_filter, repetitions=1)
    report = await validator.run()
    assert report.passed == len(_SIGNAL_FIXTURES)
    assert report.avoided == 0
    assert report.pass_rate == 1.0


@pytest.mark.asyncio
async def test_validator_all_avoid_blocked():
    ai_filter = _make_mock_filter("avoid")
    validator = PaperTradingValidator(ai_filter=ai_filter, repetitions=1)
    report = await validator.run()
    assert report.avoided == len(_SIGNAL_FIXTURES)
    assert report.passed == 0
    assert report.avoid_rate == 1.0


@pytest.mark.asyncio
async def test_validator_consistency_no_failures():
    ai_filter = _make_mock_filter("supportive")
    validator = PaperTradingValidator(ai_filter=ai_filter, repetitions=2)
    report = await validator.run()
    # Same mock always returns supportive → zero consistency failures
    assert report.consistency_failures == 0


@pytest.mark.asyncio
async def test_validator_token_estimate_under_160():
    ai_filter = _make_mock_filter("neutral")
    validator = PaperTradingValidator(ai_filter=ai_filter, repetitions=1)
    report = await validator.run()
    assert report.avg_token_estimate < 160, f"Token estimate too high: {report.avg_token_estimate}"


@pytest.mark.asyncio
async def test_validator_report_summary_keys():
    ai_filter = _make_mock_filter("neutral")
    validator = PaperTradingValidator(ai_filter=ai_filter, repetitions=1)
    report = await validator.run()
    summary = report.summary()
    for key in ("total_signals", "passed", "avoided", "pass_rate", "avoid_rate",
                "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
                "avg_token_estimate", "regime_counts", "consistency_failures", "targets"):
        assert key in summary, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_validator_daily_report_integration():
    """Validator should feed DailyAIReport; generate() should reflect signal counts."""
    ai_filter = _make_mock_filter("supportive")
    daily = DailyAIReport()
    validator = PaperTradingValidator(ai_filter=ai_filter, daily_report=daily, repetitions=1)
    await validator.run()
    result = daily.generate()
    assert result["summary"]["total_signals"] == len(_SIGNAL_FIXTURES)
