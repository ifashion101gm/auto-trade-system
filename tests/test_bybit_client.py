import pytest
from unittest.mock import AsyncMock, Mock

from app.infra.bybit_client import BybitClient


@pytest.mark.asyncio
async def test_set_leverage_pybit_uses_buy_sell_leverage():
    client = BybitClient.__new__(BybitClient)
    client.use_pybit = True
    client.pybit_session = Mock()
    client._convert_symbol_to_bybit_format = AsyncMock(return_value="XAUUSDT")
    client._handle_pybit_error = Mock()

    client.pybit_session.set_leverage.return_value = {
        'retCode': 0,
        'result': {}
    }

    result = await client.set_leverage("XAU/USDT:USDT", 10)

    client.pybit_session.set_leverage.assert_called_once_with(
        category='linear',
        symbol='XAUUSDT',
        buyLeverage=10,
        sellLeverage=10
    )
    assert result == {'status': 'success', 'leverage': 10, 'symbol': 'XAU/USDT:USDT'}


@pytest.mark.asyncio
async def test_close_position_pybit_reduce_only_with_position_idx():
    client = BybitClient.__new__(BybitClient)
    client.use_pybit = True
    client.pybit_session = Mock()
    client._convert_symbol_to_bybit_format = AsyncMock(return_value="XAUUSDT")
    client._handle_pybit_error = Mock()

    client.pybit_session.get_positions.return_value = {
        'retCode': 0,
        'result': {
            'list': [
                {
                    'symbol': 'XAUUSDT',
                    'side': 'Buy',
                    'size': '0.1',
                    'positionIdx': 1
                }
            ]
        }
    }

    client.pybit_session.place_order.return_value = {
        'retCode': 0,
        'result': {
            'orderId': 'abc123',
            'symbol': 'XAUUSDT',
            'cumExecValue': '123.45',
            'createdTime': 1234567890
        }
    }

    result = await client.close_position("XAU/USDT:USDT")

    client.pybit_session.place_order.assert_called_once_with(
        category='linear',
        symbol='XAUUSDT',
        side='Sell',
        orderType='Market',
        qty='0.1',
        reduceOnly=True,
        positionIdx=1
    )
    assert result['status'] == 'closed'
    assert result['order_id'] == 'abc123'
    assert result['amount'] == 0.1


@pytest.mark.asyncio
async def test_close_position_pybit_reduce_only_no_position_idx():
    client = BybitClient.__new__(BybitClient)
    client.use_pybit = True
    client.pybit_session = Mock()
    client._convert_symbol_to_bybit_format = AsyncMock(return_value="XAUUSDT")
    client._handle_pybit_error = Mock()

    client.pybit_session.get_positions.return_value = {
        'retCode': 0,
        'result': {
            'list': [
                {
                    'symbol': 'XAUUSDT',
                    'side': 'Sell',
                    'size': '0.05'
                }
            ]
        }
    }

    client.pybit_session.place_order.return_value = {
        'retCode': 0,
        'result': {
            'orderId': 'xyz789',
            'symbol': 'XAUUSDT',
            'cumExecValue': '45.00',
            'createdTime': 1234567890
        }
    }

    result = await client.close_position("XAU/USDT:USDT")

    client.pybit_session.place_order.assert_called_once_with(
        category='linear',
        symbol='XAUUSDT',
        side='Buy',
        orderType='Market',
        qty='0.05',
        reduceOnly=True
    )
    assert result['status'] == 'closed'
    assert result['order_id'] == 'xyz789'
    assert result['amount'] == 0.05
