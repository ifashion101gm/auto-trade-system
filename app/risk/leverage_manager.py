"""
Leverage Manager

Provides dynamic leverage recommendations combining session-aware defaults
with volatility-based scaling and hard caps from configuration.
"""
from typing import Optional
import math

from app.config import settings
from app.runtime.session_scheduler import SessionScheduler
from app.logging_config import get_logger

logger = get_logger(__name__)


class LeverageManager:
    """Recommend leverage based on session and market volatility.

    Algorithm (simple, safe default):
    - Start with session-recommended leverage (from SessionScheduler).
    - Scale down by volatility: recommended = base / (1 + vol_pct / vol_ref)
    - Apply floor and enforce `settings.RISK_MAX_LEVERAGE` and min 1.
    """

    def __init__(self, session_scheduler: Optional[SessionScheduler] = None):
        self.session_scheduler = session_scheduler or SessionScheduler()
        # Reference volatility (e.g., 1% means normal volatility)
        self.volatility_reference = getattr(settings, 'LEVERAGE_VOL_REF_PCT', 0.01)
        self.max_leverage = getattr(settings, 'RISK_MAX_LEVERAGE', 5)

    def recommend_leverage(self, symbol: str = '', vol_pct: Optional[float] = None) -> int:
        """Return recommended leverage (int).

        Args:
            symbol: Symbol (unused in default algorithm, present for extension)
            vol_pct: Observed volatility as decimal (e.g., 0.02 for 2%). If None,
                     fall back to session-only recommendation.
        """
        base = self.session_scheduler.get_recommended_leverage()

        if vol_pct is None:
            recommended = base
        else:
            try:
                scale = 1.0 + (vol_pct / max(self.volatility_reference, 1e-6))
                recommended = base / scale
            except Exception:
                recommended = base

        # Enforce bounds
        recommended = int(max(1, math.floor(recommended)))
        if recommended > self.max_leverage:
            recommended = int(self.max_leverage)

        logger.debug(
            f"LeverageManager: symbol={symbol} vol={vol_pct} base={base} -> {recommended} (max={self.max_leverage})"
        )

        return recommended
