from app.infra.kill_switch import KillSwitch


def test_kill_switch_engage_disengage(tmp_path, monkeypatch):
    file_path = tmp_path / 'kill_state.json'
    notifier = None
    ks = KillSwitch(notifier=notifier, persist_path=str(file_path))

    assert not ks.is_engaged()

    ks.engage(actor='tester', reason='unit test')
    assert ks.is_engaged()
    status = ks.get_status()
    assert status.engaged_by == 'tester'

    ks.disengage(actor='tester', reason='clear')
    assert not ks.is_engaged()
