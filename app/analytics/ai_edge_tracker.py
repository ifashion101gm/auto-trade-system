"""Track AI regime classifier effectiveness per trade via Postgres."""
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger

logger = get_logger(__name__)


class AIEdgeTracker:
    """Log and query AI filter performance by regime using Postgres."""

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self._db: Optional[AsyncSession] = db_session

    def set_session(self, db_session: AsyncSession) -> None:
        self._db = db_session

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

    async def log_trade_close(self, trade_id: str, pnl: float, regime: str) -> None:
        """Persist trade outcome (pnl + regime) to paper_trades."""
        logger.info("Trade closed: trade_id=%s pnl=%.4f regime=%s", trade_id, pnl, regime)
        if self._db is None:
            return
        try:
            await self._db.execute(
                text(
                    "UPDATE paper_trades SET regime = :regime "
                    "WHERE id = :trade_id"
                ),
                {"regime": regime, "trade_id": trade_id},
            )
            await self._db.commit()
        except Exception as exc:
            logger.error("AIEdgeTracker.log_trade_close failed: %s", exc)

    async def get_regime_stats(self, regime: str) -> Dict:
        """Return win-rate / avg-pnl for a regime from Postgres."""
        if self._db is None:
            return {}
        try:
            result = await self._db.execute(
                text(
                    "SELECT COUNT(*) AS total, "
                    "SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) AS wins, "
                    "AVG(profit) AS avg_pnl, "
                    "STDDEV(profit) AS std_pnl "
                    "FROM paper_trades "
                    "WHERE regime = :regime AND profit IS NOT NULL"
                ),
                {"regime": regime},
            )
            row = result.mappings().one_or_none()
            if not row or not row["total"]:
                return {}
            total = row["total"] or 0
            wins = row["wins"] or 0
            return {
                "regime": regime,
                "total": total,
                "wins": wins,
                "win_rate": round(wins / total, 4) if total else 0.0,
                "avg_pnl": round(float(row["avg_pnl"] or 0), 4),
                "std_pnl": round(float(row["std_pnl"] or 0), 4),
            }
        except Exception as exc:
            logger.error("AIEdgeTracker.get_regime_stats failed: %s", exc)
            return {}
