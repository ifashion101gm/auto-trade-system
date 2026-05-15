import asyncio
import json

from app.infra.kill_switch import KillSwitch
from app.risk.risk_engine import RiskEngine
from app.risk.leverage_manager import LeverageManager


def test_kill_switch_blocks_trade(tmp_path):
    ks_file = tmp_path / 'ks.json'
    ks = KillSwitch(persist_path=str(ks_file))
    ks.engage(actor='unittest', reason='test block')

    re = RiskEngine(db_session=None, kill_switch=ks)

    proposal = {
        'symbol': 'XAUUSDT',
        'entry_price': 100,
        'quantity': 0.1,
        'leverage': 1
    }

    decision = asyncio.run(re.check_trade_approval(proposal))
    assert not decision.approved
    assert any('KILL SWITCH' in v.upper() for v in decision.violations)


def test_daily_loss_lock_persists_and_blocks_trading(tmp_path):
    state_file = tmp_path / 'risk_state.json'
    ks = KillSwitch(persist_path=str(tmp_path / 'kill_switch.json'))
    re = RiskEngine(db_session=None, kill_switch=ks, app_state=None)
    re.state_file = str(state_file)
    re.daily_pnl_pct = -0.035

    proposal = {
        'symbol': 'XAUUSDT',
        'entry_price': 100,
        'quantity': 0.1,
        'leverage': 1
    }

    decision = asyncio.run(re.check_trade_approval(proposal))
    assert not decision.approved
    assert re.daily_loss_lock_active is True
    assert state_file.exists()

    persisted = json.loads(state_file.read_text())
    assert persisted['daily_loss_lock_active'] is True
    assert ks.is_engaged()


def test_leverage_enforced_by_manager():
    # Create a leverage manager that always recommends 1x
    class OneLeverageManager(LeverageManager):
        def recommend_leverage(self, symbol: str = '', vol_pct: float = None) -> int:
            return 1

    lm = OneLeverageManager()
    re = RiskEngine(db_session=None, leverage_manager=lm)

    proposal = {
        'symbol': 'XAUUSDT',
        'entry_price': 100,
        'quantity': 0.001,
        'leverage': 5
    }

    decision = asyncio.run(re.check_trade_approval(proposal))
    assert not decision.approved
    assert any('leverage' in v.lower() for v in decision.violations)
