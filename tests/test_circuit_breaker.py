import asyncio

from app.infra.circuit_breaker import SystemCircuitBreaker


class FakeExchangeManager:
    def __init__(self):
        self.closed = []

    async def get_open_positions(self):
        # Return a list of dicts with 'symbol'
        return [
            {'symbol': 'XAUUSDT', 'qty': 0.1},
            {'symbol': 'BTCUSDT', 'qty': 0.2}
        ]

    async def close_position(self, symbol: str):
        # Simulate closing position
        self.closed.append(symbol)
        return {'ok': True, 'symbol': symbol}


class FakeNotifier:
    def __init__(self):
        self.last_call = None

    async def send_emergency_position_closure(self, closed_positions, reason):
        self.last_call = {'closed_positions': closed_positions, 'reason': reason}


def test_emergency_close_positions():
    notifier = FakeNotifier()
    cb = SystemCircuitBreaker(notifier=notifier)

    fake_em = FakeExchangeManager()

    asyncio.run(cb.emergency_close_positions(exchange_manager=fake_em, exclude_symbols=['BTCUSDT']))

    # Ensure BTCUSDT was excluded and XAUUSDT closed
    assert 'XAUUSDT' in fake_em.closed
    assert 'BTCUSDT' not in fake_em.closed
    assert notifier.last_call is not None
    assert any(p['symbol'] == 'XAUUSDT' for p in notifier.last_call['closed_positions'])
