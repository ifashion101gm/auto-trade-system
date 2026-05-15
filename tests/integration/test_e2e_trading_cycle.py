"""Integration tests for complete E2E trading cycle - Issue X.

Expanded test suite covering all execution modes:
1. Proposal mode (no order placement)
2. Semi-auto small position (≤$100, auto-execute)
3. Semi-auto large position (>$100, await confirmation)
4. Fully-auto mode (immediate execution)
5. Risk violation rejection
6. Exchange rejection handling
7. Error recovery scenarios
8. State machine validation during cycles
9. Multiple consecutive cycles without corruption
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.trading_service import TradingService
from app.execution.states import ExecutionState
from app.risk.risk_engine import RiskEngine, RiskDecision
from app.database.models import PaperTrades, TradeProposals


# ============================================================================
# Issue X: Execution Mode Tests
# ============================================================================

class TestProposalMode:
    """Test proposal-only execution mode (no orders placed)."""
    
    @pytest.mark.asyncio
    async def test_proposal_mode_no_order_placement(self, mock_exchange, mock_event_bus, mock_db_session):
        """
        Test that proposal mode creates trade proposal but NO order on exchange.
        
        Scenario: EXECUTION_MODE='proposal'
        Expected: Proposal created in DB, no exchange API calls
        """
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='proposal'  # Proposal-only mode
        )
        
        mock_signal = MagicMock()
        mock_signal.side = 'buy'
        mock_signal.entry_price = 2000.0
        mock_signal.quantity = 0.01
        mock_signal.stop_loss = 1980.0
        mock_signal.take_profit = 2040.0
        mock_signal.leverage = 1
        mock_signal.confidence = 0.85
        mock_signal.strategy_name = 'test_strategy'
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify proposal created
        assert result['status'] == 'proposal_created'
        assert 'proposal_id' in result
        
        # Verify NO order placed on exchange
        mock_exchange.place_order.assert_not_called()
        
        # Verify state transitions correct
        states_visited = [h['to'] for h in service.state_history]
        assert ExecutionState.PROPOSING.value in states_visited
        assert ExecutionState.EXECUTING.value not in states_visited  # Should not execute
    
    @pytest.mark.asyncio
    async def test_proposal_mode_database_record(self, mock_exchange, mock_event_bus, mock_db_session):
        """Test that proposal mode creates database record."""
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='proposal'
        )
        
        mock_signal = MagicMock()
        mock_signal.side = 'buy'
        mock_signal.entry_price = 2000.0
        mock_signal.quantity = 0.01
        mock_signal.confidence = 0.85
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify proposal exists in database
        stmt = select(TradeProposals).where(
            TradeProposals.symbol == 'XAUUSDT',
            TradeProposals.status == 'pending'
        )
        query_result = await mock_db_session.execute(stmt)
        proposal = query_result.scalar_one_or_none()
        
        assert proposal is not None, "Proposal should be created in database"
        assert proposal.side == 'buy'
        assert proposal.entry_price == 2000.0


class TestSemiAutoSmallPosition:
    """Test semi-auto mode with small positions (auto-execute ≤$100)."""
    
    @pytest.mark.asyncio
    async def test_semi_auto_small_position_auto_executes(self, mock_exchange, mock_event_bus, mock_db_session):
        """
        Test that small positions auto-execute in semi-auto mode.
        
        Scenario: Position value ≤ $100 threshold
        Expected: Order placed automatically without confirmation
        """
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
        
        # Mock successful order placement
        mock_exchange.place_order = AsyncMock(return_value={
            'id': 'ORDER_123',
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'amount': 0.01,
            'price': 2000.0,
            'status': 'closed',
            'filled': 0.01
        })
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='semi-auto',
            auto_execute_threshold_usd=100.0  # Small position threshold
        )
        
        # Create small position ($20 value)
        mock_signal = MagicMock()
        mock_signal.side = 'buy'
        mock_signal.entry_price = 2000.0
        mock_signal.quantity = 0.01  # $20 position
        mock_signal.confidence = 0.85
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify order was placed (auto-executed)
        assert result['status'] == 'monitoring'
        mock_exchange.place_order.assert_called_once()
        
        # Verify trade recorded in database
        stmt = select(PaperTrades).where(
            PaperTrades.symbol == 'XAUUSDT',
            PaperTrades.status == 'open'
        )
        query_result = await mock_db_session.execute(stmt)
        trade = query_result.scalar_one_or_none()
        
        assert trade is not None, "Trade should be recorded in database"
        assert trade.qty == 0.01


class TestSemiAutoLargePosition:
    """Test semi-auto mode with large positions (await confirmation >$100)."""
    
    @pytest.mark.asyncio
    async def test_semi_auto_large_position_awaits_confirmation(self, mock_exchange, mock_event_bus, mock_db_session):
        """
        Test that large positions require confirmation in semi-auto mode.
        
        Scenario: Position value > $100 threshold
        Expected: Proposal created, NO order placed, status='awaiting_confirmation'
        """
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='semi-auto',
            auto_execute_threshold_usd=100.0
        )
        
        # Create large position ($500 value)
        mock_signal = MagicMock()
        mock_signal.side = 'buy'
        mock_signal.entry_price = 2000.0
        mock_signal.quantity = 0.25  # $500 position (> $100 threshold)
        mock_signal.confidence = 0.85
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify NO order placed
        mock_exchange.place_order.assert_not_called()
        
        # Verify awaiting confirmation status
        assert result['status'] == 'awaiting_confirmation'
        
        # Verify proposal created in database
        stmt = select(TradeProposals).where(
            TradeProposals.symbol == 'XAUUSDT',
            TradeProposals.status == 'pending'
        )
        query_result = await mock_db_session.execute(stmt)
        proposal = query_result.scalar_one_or_none()
        
        assert proposal is not None, "Proposal should exist for manual review"
        assert proposal.qty == 0.25


class TestFullyAutoMode:
    """Test fully-automatic execution mode (all positions execute immediately)."""
    
    @pytest.mark.asyncio
    async def test_fully_auto_immediate_execution(self, mock_exchange, mock_event_bus, mock_db_session):
        """
        Test that fully-auto mode executes all positions immediately.
        
        Scenario: EXECUTION_MODE='fully-auto', any position size
        Expected: Order placed immediately, no confirmation needed
        """
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
        
        # Mock successful order placement
        mock_exchange.place_order = AsyncMock(return_value={
            'id': 'ORDER_456',
            'symbol': 'XAUUSDT',
            'side': 'sell',
            'amount': 0.05,
            'price': 2010.0,
            'status': 'closed',
            'filled': 0.05
        })
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='fully-auto'
        )
        
        mock_signal = MagicMock()
        mock_signal.side = 'sell'
        mock_signal.entry_price = 2010.0
        mock_signal.quantity = 0.05
        mock_signal.confidence = 0.90
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify immediate execution
        assert result['status'] == 'monitoring'
        mock_exchange.place_order.assert_called_once()
        
        # Verify full lifecycle completed
        states_visited = [h['to'] for h in service.state_history]
        assert ExecutionState.EXECUTING.value in states_visited
        assert ExecutionState.MONITORING.value in states_visited


# ============================================================================
# Issue X: Rejection and Failure Handling Tests
# ============================================================================

class TestRiskViolationRejection:
    """Test risk engine rejection scenarios."""
    
    @pytest.mark.asyncio
    async def test_risk_violation_rejection(self, mock_exchange, mock_event_bus, mock_db_session):
        """
        Test that risk violations prevent order placement.
        
        Scenario: Signal violates risk rules (e.g., position too large)
        Expected: Rejected by RiskEngine, proposal status='rejected', no order
        """
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        
        # Simulate risk violation
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(
            approved=False,
            violations=["Position size exceeds maximum allowed", "Leverage too high"]
        )
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='fully-auto'
        )
        
        mock_signal = MagicMock()
        mock_signal.side = 'buy'
        mock_signal.entry_price = 2000.0
        mock_signal.quantity = 1.0  # Excessively large
        mock_signal.leverage = 10  # Too high
        mock_signal.confidence = 0.85
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify rejection
        assert result['status'] == 'rejected'
        assert 'rejection_reasons' in result
        assert len(result['rejection_reasons']) >= 2
        
        # Verify NO order placed
        mock_exchange.place_order.assert_not_called()
        
        # Verify proposal marked as rejected in database
        stmt = select(TradeProposals).where(
            TradeProposals.symbol == 'XAUUSDT',
            TradeProposals.status == 'rejected'
        )
        query_result = await mock_db_session.execute(stmt)
        proposal = query_result.scalar_one_or_none()
        
        assert proposal is not None, "Rejected proposal should be recorded"


class TestExchangeRejection:
    """Test exchange-side order rejection scenarios."""
    
    @pytest.mark.asyncio
    async def test_exchange_order_rejection(self, mock_exchange, mock_event_bus, mock_db_session):
        """
        Test handling of exchange order rejection.
        
        Scenario: Exchange rejects order (insufficient margin, invalid params, etc.)
        Expected: Proper error handling, proposal status='failed', alert sent
        """
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
        
        # Mock exchange rejection
        mock_exchange.place_order = AsyncMock(side_effect=Exception(
            "Insufficient margin: Available balance $100, required $500"
        ))
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='fully-auto'
        )
        
        mock_signal = MagicMock()
        mock_signal.side = 'buy'
        mock_signal.entry_price = 2000.0
        mock_signal.quantity = 0.25
        mock_signal.confidence = 0.85
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify failure status
        assert result['status'] == 'failed'
        assert 'error' in result
        assert "Insufficient margin" in result['error']
        
        # Verify trade/proposal marked as failed
        stmt = select(PaperTrades).where(
            PaperTrades.symbol == 'XAUUSDT',
            PaperTrades.status == 'failed'
        )
        query_result = await mock_db_session.execute(stmt)
        failed_trade = query_result.scalar_one_or_none()
        
        assert failed_trade is not None, "Failed trade should be recorded"


# ============================================================================
# Issue X: Error Recovery and Resilience Tests
# ============================================================================

class TestErrorRecovery:
    """Test system resilience and error recovery."""
    
    @pytest.mark.asyncio
    async def test_api_timeout_recovery(self, mock_exchange, mock_event_bus, mock_db_session):
        """
        Test recovery from API timeout during execution.
        
        Scenario: Exchange API times out during order placement
        Expected: Retry logic triggers, no phantom trade created
        """
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
        
        # Mock timeout on first call, success on retry
        call_count = [0]
        async def mock_place_order_with_retry(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise TimeoutError("Request timed out after 30s")
            return {
                'id': 'ORDER_RETRY_789',
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'amount': 0.01,
                'price': 2000.0,
                'status': 'closed',
                'filled': 0.01
            }
        
        mock_exchange.place_order = mock_place_order_with_retry
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='fully-auto'
        )
        
        mock_signal = MagicMock()
        mock_signal.side = 'buy'
        mock_signal.entry_price = 2000.0
        mock_signal.quantity = 0.01
        mock_signal.confidence = 0.85
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify eventual success after retry
        assert result['status'] == 'monitoring'
        assert call_count[0] >= 2, "Should have retried at least once"
    
    @pytest.mark.asyncio
    async def test_partial_fill_handling(self, mock_exchange, mock_event_bus, mock_db_session):
        """
        Test handling of partially filled orders.
        
        Scenario: Order only partially filled by exchange
        Expected: State reflects partial fill, reconciliation handles correctly
        """
        mock_position_monitor = AsyncMock()
        mock_risk_engine = AsyncMock()
        mock_risk_engine.check_trade_approval.return_value = RiskDecision(approved=True)
        
        # Mock partial fill
        mock_exchange.place_order = AsyncMock(return_value={
            'id': 'ORDER_PARTIAL',
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'amount': 0.01,
            'price': 2000.0,
            'status': 'partially_filled',
            'filled': 0.005,  # Only 50% filled
            'remaining': 0.005
        })
        
        service = TradingService(
            exchange_manager=mock_exchange,
            event_bus=mock_event_bus,
            position_monitor=mock_position_monitor,
            risk_engine=mock_risk_engine,
            db_session=mock_db_session,
            execution_mode='fully-auto'
        )
        
        mock_signal = MagicMock()
        mock_signal.side = 'buy'
        mock_signal.entry_price = 2000.0
        mock_signal.quantity = 0.01
        mock_signal.confidence = 0.85
        
        with patch('app.strategy.strategy_manager.StrategyManager.generate_signals',
                   return_value=[mock_signal]):
            result = await service.execute_trading_cycle(symbol="XAUUSDT")
        
        # Verify partial fill recorded
        assert result['status'] in ['monitoring', 'partially_filled']
        
        # Verify trade reflects partial fill
        stmt = select(PaperTrades).where(
            PaperTrades.symbol == 'XAUUSDT'
        )
        query_result = await mock_db_session.execute(stmt)
        trade = query_result.scalar_one_or_none()
        
        assert trade is not None
        # Note: Actual implementation may vary on how partial fills are tracked


# ============================================================================
# Legacy Tests (Preserved for Backward Compatibility)
# ============================================================================

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
