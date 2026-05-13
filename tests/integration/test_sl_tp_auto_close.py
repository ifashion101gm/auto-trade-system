"""Integration tests for SL/TP auto-close functionality."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.position_monitor import PositionMonitor
from app.database.models import PaperTrades


@pytest.mark.asyncio
async def test_sl_hit_triggers_close_order(mock_exchange, mock_event_bus, mock_db_session):
    """Test that SL hit executes close order on exchange."""
    monitor = PositionMonitor(
        event_bus=mock_event_bus,
        exchange_manager=mock_exchange,
        check_interval=0.5  # Fast check for testing
    )
    
    # Setup monitored position
    trade_id = "test_trade_sl"
    
    # Mock ticker to trigger SL (price below stop loss)
    mock_exchange.fetch_ticker.return_value = {'last_price': 49000.0}
    
    # Mock close order execution
    mock_exchange.create_market_order.return_value = {
        'order_id': 'close_ord_123',
        'price': 49000.0,
        'filled': 0.01
    }
    
    # Mock database trade
    mock_trade = PaperTrades(
        id=trade_id,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        qty=0.01,
        stop_loss=49500.0,
        status='open'
    )
    
    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_trade
        return result
    
    mock_db_session.execute = mock_execute
    mock_db_session.commit = AsyncMock()
    
    # Start monitoring
    await monitor.start_monitoring(
        trade_id=trade_id,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.01,
        stop_loss=49500.0,
        take_profit=None,
        db_session=mock_db_session
    )
    
    # Wait for monitoring loop to detect SL and execute close
    await asyncio.sleep(2)
    
    # Verify close order was executed
    assert mock_exchange.create_market_order.called
    call_args = mock_exchange.create_market_order.call_args
    assert call_args[1]['side'] == 'SELL'  # Close LONG with SELL


@pytest.mark.asyncio
async def test_tp_hit_triggers_close_order(mock_exchange, mock_event_bus, mock_db_session):
    """Test that TP hit executes close order on exchange."""
    monitor = PositionMonitor(
        event_bus=mock_event_bus,
        exchange_manager=mock_exchange,
        check_interval=0.5
    )
    
    trade_id = "test_trade_tp"
    
    # Mock ticker to trigger TP (price above take profit)
    mock_exchange.fetch_ticker.return_value = {'last_price': 52500.0}
    
    # Mock close order execution
    mock_exchange.create_market_order.return_value = {
        'order_id': 'close_ord_456',
        'price': 52500.0,
        'filled': 0.01
    }
    
    mock_trade = PaperTrades(
        id=trade_id,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        qty=0.01,
        take_profit=52000.0,
        status='open'
    )
    
    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_trade
        return result
    
    mock_db_session.execute = mock_execute
    mock_db_session.commit = AsyncMock()
    
    await monitor.start_monitoring(
        trade_id=trade_id,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.01,
        stop_loss=None,
        take_profit=52000.0,
        db_session=mock_db_session
    )
    
    await asyncio.sleep(2)
    
    assert mock_exchange.create_market_order.called


@pytest.mark.asyncio
async def test_close_order_failure_fallback(mock_exchange, mock_event_bus, mock_db_session):
    """Test system handles exchange order failure gracefully."""
    monitor = PositionMonitor(
        event_bus=mock_event_bus,
        exchange_manager=mock_exchange,
        check_interval=0.5
    )
    
    trade_id = "test_trade_fail"
    
    # Trigger SL
    mock_exchange.fetch_ticker.return_value = {'last_price': 49000.0}
    
    # Simulate exchange order failure
    mock_exchange.create_market_order.side_effect = Exception("Order failed")
    
    mock_trade = PaperTrades(
        id=trade_id,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        qty=0.01,
        stop_loss=49500.0,
        status='open',
        notes=""
    )
    
    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_trade
        return result
    
    mock_db_session.execute = mock_execute
    mock_db_session.commit = AsyncMock()
    
    await monitor.start_monitoring(
        trade_id=trade_id,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.01,
        stop_loss=49500.0,
        take_profit=None,
        db_session=mock_db_session
    )
    
    await asyncio.sleep(2)
    
    # Verify fallback was used (trade should still be closed with warning)
    assert "WARNING" in mock_trade.notes or mock_trade.status == 'closed'


@pytest.mark.asyncio
async def test_pnl_calculation_accuracy(mock_exchange, mock_event_bus, mock_db_session):
    """Verify P&L calculation uses actual execution price."""
    monitor = PositionMonitor(
        event_bus=mock_event_bus,
        exchange_manager=mock_exchange,
        check_interval=0.5
    )
    
    trade_id = "test_trade_pnl"
    
    # Trigger SL at 49500
    mock_exchange.fetch_ticker.return_value = {'last_price': 49500.0}
    
    # But actual execution has slippage to 49495
    mock_exchange.create_market_order.return_value = {
        'order_id': 'ord_slippage',
        'price': 49495.0,  # Slippage occurred
        'filled': 0.01
    }
    
    mock_trade = PaperTrades(
        id=trade_id,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        qty=0.01,
        stop_loss=49500.0,
        status='open',
        exit_price=None,
        profit=None
    )
    
    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_trade
        return result
    
    mock_db_session.execute = mock_execute
    mock_db_session.commit = AsyncMock()
    
    await monitor.start_monitoring(
        trade_id=trade_id,
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.01,
        stop_loss=49500.0,
        take_profit=None,
        db_session=mock_db_session
    )
    
    await asyncio.sleep(2)
    
    # Verify trade record uses actual execution price (49495), not SL price (49500)
    assert mock_trade.exit_price == 49495.0
    # P&L should be calculated with actual price: (49495 - 50000) * 0.01 = -5.05
    assert abs(mock_trade.profit - (-5.05)) < 0.01
