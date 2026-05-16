"""Track AI regime classifier effectiveness per trade."""
from datetime import datetime
from typing import Dict, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)


class AIEdgeTracker:
    """Log and query AI filter performance by regime."""

    def log_signal_executed(
        self,
        regime: str,
        base_confidence: float,
        adjusted_confidence: float,
        multiplier: float,
        trade_id: Optional[str] = None,
    ) -> None:
        logger.info(
            "AI signal executed: trade_id=%s regime=%s conf=%.2f→%.2f multiplier=%.2f",
            trade_id, regime, base_confidence, adjusted_confidence, multiplier,
        )

    def log_trade_close(self, trade_id: str, pnl: float, regime: str) -> None:
        """Record trade outcome for edge tracking.

        TODO: UPDATE trades SET pnl=?, regime=? WHERE id=?
        """
        logger.info("Trade closed: trade_id=%s pnl=%.4f regime=%s", trade_id, pnl, regime)

    def get_regime_stats(self, regime: str) -> Dict:
        """Return win-rate / avg-pnl for a regime.

        TODO: Query Postgres:
            SELECT COUNT(*), SUM(pnl>0)/COUNT(*) win_rate, AVG(pnl), STDDEV(pnl)
            FROM trades WHERE regime = :regime
        """
        return {}
