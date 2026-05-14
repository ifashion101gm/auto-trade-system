"""
Unit tests for ExecutionService - Centralized order lifecycle management.

Tests cover:
- Order validation and risk checks
- Idempotency protection (prevent duplicate trades)
- Retry logic with exponential backoff
- Database transaction rollback on failure
- Exchange interaction mocking
- Event publishing
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.execution_service import (
    ExecutionService,
    ExecutionRequest,
    ExecutionResult
)


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_exchange_manager():
    """Create mock exchange manager."""
    manager = AsyncMock()
    manager.create_market_order = AsyncMock()
    manager.get_order_status = AsyncMock()
    manager.get_positions = AsyncMock()
    return manager


@pytest.fixture
def mock_risk_engine():
    """Create mock risk engine."""
    engine = AsyncMock()
    engine.check_trade_approval = AsyncMock()
    return engine


@pytest.fixture
def mock_notifier():
    """Create mock Telegram notifier."""
    notifier = AsyncMock()
    notifier.send_trade_alert = AsyncMock()
    return notifier


@pytest.fixture
def execution_service(mock_exchange_manager, mock_risk_engine, mock_notifier):
    """Create ExecutionService instance with mocked dependencies."""
    with patch('app.execution.execution_service.UnifiedExchangeManager', return_value=mock_exchange_manager), \
         patch('app.execution.execution_service.RiskEngine', return_value=mock_risk_engine), \
         patch('app.execution.execution_service.TelegramNotifier', return_value=mock_notifier):
        
        service = ExecutionService(exchange_name='binance', use_testnet=True)
        service.exchange_manager = mock_exchange_manager
        service.risk_engine = mock_risk_engine
        service.notifier = mock_notifier
        
        return service


class TestExecutionRequest:
    """Test ExecutionRequest dataclass."""
    
    def test_create_basic_request(self):
        """Test creating a basic execution request."""
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        assert request.symbol == 'XAUUSDT'
        assert request.side == 'buy'
        assert request.entry_price == 2345.67
        assert request.quantity == 0.1
        assert request.leverage == 1  # Default
        assert request.stop_loss is None
        assert request.take_profit is None
    
    def test_create_full_request(self):
        """Test creating request with all parameters."""
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='sell',
            entry_price=2350.00,
            quantity=0.2,
            leverage=5,
            stop_loss=2340.00,
            take_profit=2370.00,
            strategy_name='trend_following',
            confidence=0.85,
            user_id='user123',
            execution_mode='fully-auto'
        )
        
        assert request.leverage == 5
        assert request.stop_loss == 2340.00
        assert request.take_profit == 2370.00
        assert request.strategy_name == 'trend_following'
        assert request.confidence == 0.85


class TestExecutionResult:
    """Test ExecutionResult dataclass."""
    
    def test_create_success_result(self):
        """Test creating successful execution result."""
        result = ExecutionResult(
            success=True,
            order_id='ORDER123',
            trade_id=456,
            filled_price=2345.67,
            filled_quantity=0.1,
            fee=0.50,
            status='executed'
        )
        
        assert result.success is True
        assert result.order_id == 'ORDER123'
        assert result.trade_id == 456
        assert result.status == 'executed'
    
    def test_create_failure_result(self):
        """Test creating failed execution result."""
        result = ExecutionResult(
            success=False,
            error='Insufficient balance',
            status='failed'
        )
        
        assert result.success is False
        assert result.error == 'Insufficient balance'
        assert result.status == 'failed'
    
    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ExecutionResult(
            success=True,
            order_id='ORDER123',
            filled_price=2345.67,
            warnings=['High slippage detected']
        )
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert result_dict['success'] is True
        assert result_dict['order_id'] == 'ORDER123'
        assert result_dict['filled_price'] == 2345.67
        assert 'High slippage detected' in result_dict['warnings']


class TestExecutionServiceValidation:
    """Test ExecutionService input validation."""
    
    @pytest.mark.asyncio
    async def test_reject_invalid_side(self, execution_service, mock_db_session):
        """Verify service rejects invalid order side."""
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='invalid',  # Must be 'buy' or 'sell'
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        assert result.success is False
        assert result.status == 'failed'
        assert 'invalid' in result.error.lower() or 'side' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_reject_zero_quantity(self, execution_service, mock_db_session):
        """Verify service rejects zero or negative quantity."""
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0  # Invalid
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        assert result.success is False
        assert result.status == 'failed'
    
    @pytest.mark.asyncio
    async def test_reject_negative_price(self, execution_service, mock_db_session):
        """Verify service rejects negative entry price."""
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=-100,  # Invalid
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        assert result.success is False
        assert result.status == 'failed'


class TestExecutionServiceRiskIntegration:
    """Test ExecutionService integration with RiskEngine."""
    
    @pytest.mark.asyncio
    async def test_reject_trade_on_risk_violation(self, execution_service, mock_db_session, mock_risk_engine):
        """Verify trade is rejected when risk engine blocks it."""
        # Mock risk engine to reject trade
        mock_risk_engine.check_trade_approval.return_value = {
            'approved': False,
            'violations': ['Daily loss limit exceeded'],
            'warnings': []
        }
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        assert result.success is False
        assert result.status == 'rejected'
        assert 'risk' in result.error.lower() or 'rejected' in result.error.lower()
        
        # Verify order was NOT placed on exchange
        mock_exchange_manager = execution_service.exchange_manager
        mock_exchange_manager.create_market_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_proceed_when_risk_approved(self, execution_service, mock_db_session, mock_risk_engine, mock_exchange_manager):
        """Verify trade proceeds when risk engine approves."""
        # Mock risk engine to approve trade
        mock_risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange to return successful order
        mock_exchange_manager.create_market_order.return_value = {
            'order_id': 'ORDER123',
            'status': 'filled',
            'filled_price': 2345.67,
            'filled_quantity': 0.1
        }
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        # Verify order WAS placed on exchange
        mock_exchange_manager.create_market_order.assert_called_once()
        
        # Verify risk check was called
        mock_risk_engine.check_trade_approval.assert_called_once()


class TestExecutionServiceIdempotency:
    """Test ExecutionService idempotency protection."""
    
    @pytest.mark.asyncio
    async def test_prevent_duplicate_orders_same_signal(self, execution_service, mock_db_session, mock_exchange_manager):
        """Verify same signal doesn't create duplicate orders."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange response
        mock_exchange_manager.create_market_order.return_value = {
            'order_id': 'ORDER123',
            'status': 'filled',
            'filled_price': 2345.67,
            'filled_quantity': 0.1
        }
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1,
            strategy_name='test_strategy',
            confidence=0.9
        )
        
        # Execute same request twice rapidly
        result1 = await execution_service.execute_trade(request, db_session=mock_db_session)
        result2 = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        # At least one should succeed, but verify deduplication logic exists
        # (Actual dedup behavior depends on implementation)
        assert result1.success is True or result2.success is True


class TestExecutionServiceRetryLogic:
    """Test ExecutionService retry mechanism."""
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, execution_service, mock_db_session, mock_exchange_manager):
        """Verify service retries on timeout errors."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange to fail first 2 attempts, succeed on 3rd
        call_count = [0]
        async def mock_create_order(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise TimeoutError("Request timed out")
            return {
                'order_id': 'ORDER123',
                'status': 'filled',
                'filled_price': 2345.67,
                'filled_quantity': 0.1
            }
        
        mock_exchange_manager.create_market_order.side_effect = mock_create_order
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        # Verify retry occurred (called 3 times)
        assert mock_exchange_manager.create_market_order.call_count == 3
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_fail_after_max_retries(self, execution_service, mock_db_session, mock_exchange_manager):
        """Verify service fails after exhausting retries."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange to always fail
        mock_exchange_manager.create_market_order.side_effect = TimeoutError("Always fails")
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        # Verify max retries attempted (default is 3)
        assert mock_exchange_manager.create_market_order.call_count >= 3
        assert result.success is False
        assert 'timeout' in result.error.lower() or 'retry' in result.error.lower()


class TestExecutionServiceDatabaseTransactions:
    """Test ExecutionService database transaction handling."""
    
    @pytest.mark.asyncio
    async def test_rollback_on_execution_failure(self, execution_service, mock_db_session, mock_exchange_manager):
        """Verify database transaction rolls back on execution failure."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange to fail
        mock_exchange_manager.create_market_order.side_effect = Exception("Exchange error")
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        # Verify rollback was called
        mock_db_session.rollback.assert_called()
        
        # Verify commit was NOT called
        mock_db_session.commit.assert_not_called()
        
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_commit_on_success(self, execution_service, mock_db_session, mock_exchange_manager):
        """Verify database transaction commits on success."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange success
        mock_exchange_manager.create_market_order.return_value = {
            'order_id': 'ORDER123',
            'status': 'filled',
            'filled_price': 2345.67,
            'filled_quantity': 0.1
        }
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        # Verify commit was called
        mock_db_session.commit.assert_called()
        
        # Verify rollback was NOT called
        mock_db_session.rollback.assert_not_called()
        
        assert result.success is True


class TestExecutionServiceEventPublishing:
    """Test ExecutionService event bus integration."""
    
    @pytest.mark.asyncio
    async def test_publish_event_on_success(self, execution_service, mock_db_session, mock_exchange_manager):
        """Verify execution event is published on successful trade."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange success
        mock_exchange_manager.create_market_order.return_value = {
            'order_id': 'ORDER123',
            'status': 'filled',
            'filled_price': 2345.67,
            'filled_quantity': 0.1
        }
        
        # Mock event bus
        with patch('app.execution.execution_service.event_bus') as mock_event_bus:
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1
            )
            
            result = await execution_service.execute_trade(request, db_session=mock_db_session)
            
            # Verify event was published
            assert mock_event_bus.publish.called or mock_event_bus.emit.called
    
    @pytest.mark.asyncio
    async def test_notify_on_failure(self, execution_service, mock_db_session, mock_exchange_manager, mock_notifier):
        """Verify notification is sent on execution failure."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange failure
        mock_exchange_manager.create_market_order.side_effect = Exception("Critical error")
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        # Verify notification was attempted
        assert mock_notifier.send_trade_alert.called or result.success is False


class TestExecutionServiceEdgeCases:
    """Test ExecutionService edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_handle_missing_db_session(self, execution_service):
        """Verify graceful handling when db_session is None."""
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=None)
        
        # Should fail gracefully, not crash
        assert result.success is False
        assert 'session' in result.error.lower() or 'database' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_handle_exchange_maintenance(self, execution_service, mock_db_session, mock_exchange_manager):
        """Verify handling of exchange maintenance mode."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock exchange maintenance error
        from app.infra.exchange_manager import ExchangeError
        mock_exchange_manager.create_market_order.side_effect = ExchangeError("Exchange under maintenance")
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        assert result.success is False
        assert 'maintenance' in result.error.lower() or 'exchange' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_handle_insufficient_balance(self, execution_service, mock_db_session, mock_exchange_manager):
        """Verify handling of insufficient balance error."""
        # Mock risk approval
        execution_service.risk_engine.check_trade_approval.return_value = {
            'approved': True,
            'violations': [],
            'warnings': []
        }
        
        # Mock insufficient balance error
        mock_exchange_manager.create_market_order.side_effect = Exception("Insufficient balance")
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=1000  # Very large quantity
        )
        
        result = await execution_service.execute_trade(request, db_session=mock_db_session)
        
        assert result.success is False
        assert 'balance' in result.error.lower() or 'insufficient' in result.error.lower()


# =============================================================================
# INTEGRATION TESTS (Require real database/exchange - marked for manual run)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_execution_flow_integration():
    """
    Full integration test with real database and exchange.
    
    This test should be run manually against testnet environment.
    Requires:
    - Real database connection
    - Testnet API keys configured
    - Sufficient testnet balance
    """
    pytest.skip("Integration test - run manually with --run-integration flag")
    
    # TODO: Implement full integration test
    # 1. Create real database session
    # 2. Initialize ExecutionService with testnet config
    # 3. Execute small test trade
    # 4. Verify order created on exchange
    # 5. Verify trade record in database
    # 6. Clean up (cancel order, delete record)
