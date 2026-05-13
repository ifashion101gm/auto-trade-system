"""Integration tests for complete E2E trading cycle."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.trading_service import TradingService
from app.execution.states import ExecutionState
from app.risk.risk_engine import RiskEngine, RiskDecision


@pytest.mark.asyncio
async def test_complete_cycle_success(mock_exchange, mock_event_bus, mock_db_session):
    """Test successful complete trading cycle from idle to monitoring."""
    # Mock position monitor
    mock_position_monitor = AsyncMock()
    
    # Mock risk engine
    mock_risk_engine = AsyncMock()
    mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
    
    service = TradingService(
        exchange_manager=mock_exchange,
        event_bus=mock_event_bus,
        position_monitor=mock_position_monitor,
        risk_engine=mock_risk_engine,
        db_session=mock_db_session
    )
    
    # Mock strategy manager to return a signal
    mock_signal = MagicMock()
    mock_signal.side = 'LONG'
    mock_signal.entry_price = 50000.0
    mock_signal.quantity = 0.01
    mock_signal.stop_loss = 49000.0
    mock_signal.take_profit = 52000.0
    mock_signal.leverage = 2
    mock_signal.confidence = 0.85
    mock_signal.strategy_name = 'breakout'
    
    with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
               return_value=[mock_signal]):
        result = await service.execute_trading_cycle(symbol="BTC/USDT")
    
    assert result['status'] == 'monitoring'
    assert 'execution' in result['stages']
    assert result['stages']['execution']['success'] is True


@pytest.mark.asyncio
async def test_cycle_rejected_by_risk(mock_exchange, mock_event_bus, mock_db_session):
    """Test cycle stops when risk engine rejects proposal."""
    mock_position_monitor = AsyncMock()
    mock_risk_engine = AsyncMock()
    mock_risk_engine.check_trade_approval.return_value = RiskDecision(
        approved=False,
        violations=["Position size too large"]
    )
    
    service = TradingService(
        exchange_manager=mock_exchange,
        event_bus=mock_event_bus,
        position_monitor=mock_position_monitor,
        risk_engine=mock_risk_engine,
        db_session=mock_db_session
    )
    
    mock_signal = MagicMock()
    mock_signal.side = 'LONG'
    mock_signal.entry_price = 50000.0
    mock_signal.quantity = 0.01
    mock_signal.stop_loss = 49000.0
    mock_signal.take_profit = 52000.0
    mock_signal.leverage = 2
    mock_signal.confidence = 0.85
    mock_signal.strategy_name = 'breakout'
    
    with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
               return_value=[mock_signal]):
        result = await service.execute_trading_cycle()
    
    assert result['status'] == 'rejected'
    assert 'rejection_reasons' in result
    assert len(result['rejection_reasons']) > 0


@pytest.mark.asyncio
async def test_cycle_no_signal_generated(mock_exchange, mock_event_bus, mock_db_session):
    """Test cycle exits gracefully when no trading signal."""
    mock_position_monitor = AsyncMock()
    mock_risk_engine = AsyncMock()
    
    service = TradingService(
        exchange_manager=mock_exchange,
        event_bus=mock_event_bus,
        position_monitor=mock_position_monitor,
        risk_engine=mock_risk_engine,
        db_session=mock_db_session
    )
    
    with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
               return_value=[]):
        result = await service.execute_trading_cycle()
    
    assert result['status'] == 'no_signal'


@pytest.mark.asyncio
async def test_state_transitions_during_cycle(mock_exchange, mock_event_bus, mock_db_session):
    """Verify correct state transitions occur during cycle."""
    mock_position_monitor = AsyncMock()
    mock_risk_engine = AsyncMock()
    mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
    
    service = TradingService(
        exchange_manager=mock_exchange,
        event_bus=mock_event_bus,
        position_monitor=mock_position_monitor,
        risk_engine=mock_risk_engine,
        db_session=mock_db_session
    )
    
    mock_signal = MagicMock()
    mock_signal.side = 'LONG'
    mock_signal.entry_price = 50000.0
    mock_signal.quantity = 0.01
    mock_signal.stop_loss = 49000.0
    mock_signal.take_profit = 52000.0
    mock_signal.leverage = 2
    mock_signal.confidence = 0.85
    mock_signal.strategy_name = 'breakout'
    
    with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
               return_value=[mock_signal]):
        await service.execute_trading_cycle()
    
    # Verify state history contains expected transitions
    states_visited = [h['to'] for h in service.state_history]
    assert ExecutionState.FETCHING_DATA.value in states_visited
    assert ExecutionState.ANALYZING.value in states_visited
    assert ExecutionState.VALIDATING.value in states_visited
    assert ExecutionState.EXECUTING.value in states_visited
    assert ExecutionState.MONITORING.value in states_visited


@pytest.mark.asyncio
async def test_cycle_error_handling(mock_exchange, mock_event_bus, mock_db_session):
    """Test cycle handles errors gracefully and transitions to ERROR state."""
    mock_position_monitor = AsyncMock()
    mock_risk_engine = AsyncMock()
    
    service = TradingService(
        exchange_manager=mock_exchange,
        event_bus=mock_event_bus,
        position_monitor=mock_position_monitor,
        risk_engine=mock_risk_engine,
        db_session=mock_db_session
    )
    
    # Force an error during data fetch
    mock_exchange.fetch_ticker.side_effect = Exception("API Error")
    
    result = await service.execute_trading_cycle()
    
    assert result['status'] == 'failed'
    assert 'error' in result
    assert service.current_state == ExecutionState.ERROR


@pytest.mark.asyncio
async def test_multiple_consecutive_cycles(mock_exchange, mock_event_bus, mock_db_session):
    """Test system can execute multiple cycles without state corruption."""
    mock_position_monitor = AsyncMock()
    mock_risk_engine = AsyncMock()
    mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
    
    service = TradingService(
        exchange_manager=mock_exchange,
        event_bus=mock_event_bus,
        position_monitor=mock_position_monitor,
        risk_engine=mock_risk_engine,
        db_session=mock_db_session
    )
    
    mock_signal = MagicMock()
    mock_signal.side = 'LONG'
    mock_signal.entry_price = 50000.0
    mock_signal.quantity = 0.01
    mock_signal.stop_loss = 49000.0
    mock_signal.take_profit = 52000.0
    mock_signal.leverage = 2
    mock_signal.confidence = 0.85
    mock_signal.strategy_name = 'breakout'
    
    for i in range(3):
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle()
            assert result['status'] in ['monitoring', 'no_signal', 'rejected']
    
    # Verify state resets properly between cycles
    assert len(service.state_history) > 0
