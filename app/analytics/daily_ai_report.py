"""
Daily AI effectiveness report — aggregates regime stats from the edge tracker.

Phase 2 implementation: in-memory accumulation with Postgres query stubs.
Postgres integration is wired via AIEdgeTracker once the trades table has
a `regime` column (Phase 3 migration task).
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.analytics.ai_edge_tracker import AIEdgeTracker
from app.logging_config import get_logger

logger = get_logger(__name__)

_REGIME_ORDER = ["supportive", "neutral", "hostile", "avoid"]


class RegimeStats:
    """Accumulates per-regime trade outcomes in memory."""

    def __init__(self):
        self.signals: int = 0          # signals that passed AI filter
        self.avoided: int = 0          # signals blocked by avoid regime
        self.trades_closed: int = 0
        self.wins: int = 0
        self.total_pnl: float = 0.0
        self.pnl_values: List[float] = []

    def record_signal(self) -> None:
        self.signals += 1

    def record_avoid(self) -> None:
        self.avoided += 1

    def record_close(self, pnl: float) -> None:
        self.trades_closed += 1
        self.total_pnl += pnl
        self.pnl_values.append(pnl)
        if pnl > 0:
            self.wins += 1

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades_closed if self.trades_closed else 0.0

    @property
    def avg_pnl(self) -> float:
        return self.total_pnl / self.trades_closed if self.trades_closed else 0.0

    @property
    def std_pnl(self) -> float:
        if len(self.pnl_values) < 2:
            return 0.0
        mean = self.avg_pnl
        variance = sum((x - mean) ** 2 for x in self.pnl_values) / len(self.pnl_values)
        return variance ** 0.5

    def to_dict(self) -> Dict:
        return {
            "signals": self.signals,
            "avoided": self.avoided,
            "trades_closed": self.trades_closed,
            "wins": self.wins,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": round(self.total_pnl, 4),
            "avg_pnl": round(self.avg_pnl, 4),
            "std_pnl": round(self.std_pnl, 4),
        }


class DailyAIReport:
    """
    Tracks and reports AI regime classifier effectiveness.

    Usage:
        report = DailyAIReport()
        report.record_signal_executed(regime="supportive", ...)
        report.record_trade_closed(trade_id="123", pnl=12.5, regime="supportive")
        summary = report.generate()
    """

    def __init__(self, edge_tracker: Optional[AIEdgeTracker] = None):
        self._tracker = edge_tracker or AIEdgeTracker()
        self._stats: Dict[str, RegimeStats] = defaultdict(RegimeStats)
        self._report_date = datetime.now(timezone.utc).date()

    def record_signal_executed(
        self,
        regime: str,
        base_confidence: float,
        adjusted_confidence: float,
        multiplier: float,
        trade_id: Optional[str] = None,
    ) -> None:
        """Call after a signal passes the AI filter and is sent to execution."""
        self._stats[regime].record_signal()
        self._tracker.log_signal_executed(
            regime=regime,
            base_confidence=base_confidence,
            adjusted_confidence=adjusted_confidence,
            multiplier=multiplier,
            trade_id=trade_id,
        )

    def record_avoid(self, regime: str = "avoid") -> None:
        """Call when AI filter returns None (avoid regime)."""
        self._stats[regime].record_avoid()

    def record_trade_closed(self, trade_id: str, pnl: float, regime: str) -> None:
        """Call when a trade closes to record outcome against its regime."""
        self._stats[regime].record_close(pnl)
        self._tracker.log_trade_close(trade_id=trade_id, pnl=pnl, regime=regime)

    def generate(self) -> Dict:
        """Generate daily effectiveness report."""
        total_signals = sum(s.signals for s in self._stats.values())
        total_avoided = sum(s.avoided for s in self._stats.values())
        total_closed = sum(s.trades_closed for s in self._stats.values())
        total_pnl = sum(s.total_pnl for s in self._stats.values())

        by_regime = {r: self._stats[r].to_dict() for r in _REGIME_ORDER if r in self._stats}

        # Alert if any regime underperforms baseline by >3%
        alerts = []
        baseline_win_rate = (
            sum(s.wins for s in self._stats.values()) / total_closed
            if total_closed else 0.0
        )
        for regime, stats in self._stats.items():
            if stats.trades_closed >= 5 and (baseline_win_rate - stats.win_rate) > 0.03:
                alerts.append(
                    f"Regime '{regime}' win_rate {stats.win_rate:.1%} is "
                    f">3% below baseline {baseline_win_rate:.1%}"
                )

        report = {
            "date": str(self._report_date),
            "summary": {
                "total_signals": total_signals,
                "total_avoided": total_avoided,
                "total_closed": total_closed,
                "total_pnl": round(total_pnl, 4),
                "overall_win_rate": round(baseline_win_rate, 4),
            },
            "by_regime": by_regime,
            "alerts": alerts,
        }

        self._log_report(report)
        return report

    def _log_report(self, report: Dict) -> None:
        s = report["summary"]
        logger.info(
            "📊 Daily AI Report [%s] | signals=%d avoided=%d closed=%d pnl=%.2f win_rate=%.1%%",
            report["date"], s["total_signals"], s["total_avoided"],
            s["total_closed"], s["total_pnl"], s["overall_win_rate"] * 100,
        )
        for regime, stats in report["by_regime"].items():
            logger.info(
                "  %-12s signals=%d closed=%d win=%.1f%% avg_pnl=%.4f",
                regime, stats["signals"], stats["trades_closed"],
                stats["win_rate"] * 100, stats["avg_pnl"],
            )
        for alert in report["alerts"]:
            logger.warning("⚠️  AI Report Alert: %s", alert)
