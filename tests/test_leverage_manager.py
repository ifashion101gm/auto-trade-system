import pytest

from app.risk.leverage_manager import LeverageManager
from app.runtime.session_scheduler import SessionScheduler, TradingSession


class DummyScheduler(SessionScheduler):
    def __init__(self, session):
        super().__init__()
        self._session = session

    def get_current_session(self):
        return self._session

    def get_recommended_leverage(self):
        # Map sessions to simple base values
        if self._session == TradingSession.LONDON_NY_OVERLAP:
            return 5
        elif self._session in [TradingSession.LONDON_OPEN, TradingSession.NY_OPEN]:
            return 3
        else:
            return 1


def test_recommend_leverage_session_only():
    sched = DummyScheduler(TradingSession.LONDON_NY_OVERLAP)
    mgr = LeverageManager(session_scheduler=sched)

    assert mgr.recommend_leverage(symbol='XAUUSDT', vol_pct=None) == 5


def test_recommend_leverage_high_volatility():
    sched = DummyScheduler(TradingSession.LONDON_NY_OVERLAP)
    mgr = LeverageManager(session_scheduler=sched)

    # High volatility (10%) should reduce leverage
    lev = mgr.recommend_leverage(symbol='XAUUSDT', vol_pct=0.10)
    assert lev < 5 and lev >= 1


def test_recommend_leverage_respects_max():
    sched = DummyScheduler(TradingSession.LONDON_OPEN)
    mgr = LeverageManager(session_scheduler=sched)

    # If max in settings is low, ensure we respect it
    mgr.max_leverage = 2
    assert mgr.recommend_leverage(vol_pct=0.0) <= 2
