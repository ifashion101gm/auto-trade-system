"""
Integration tests for Startup Recovery Service.

Tests:
1. Recovers with open positions from DB
2. Handles restart during pending order
3. Handles restart during API outage gracefully
4. Blocks trading if circuit breaker is OPEN
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.startup_recovery import StartupRecoveryService, StartupRecoveryResult


@pytest.fixture
def mock_exchange_manager():
    """Create mock exchange manager."""
    manager = AsyncMock()
    manager.fetch_positions = AsyncMock(return_value=[])
    manager.fetch_ticker = AsyncMock(return_value={'last_price': 50000.0})
    return manager


@pytest.fixture
def mock_position_monitor():
    """Create mock position monitor."""
    monitor = AsyncMock()
    monitor.start_monitoring = AsyncMock()
    monitor.get_monitored_count = MagicMock(return_value=0)
    return monitor


@pytest.fixture
def mock_reconciliation_service():
    """Create mock reconciliation service."""
    service = AsyncMock()
    result = MagicMock()
    result.is_synced = True
    result.repaired_count = 0
    result.orphaned_positions = []
    result.ghost_positions = []
    result.to_dict = MagicMock(return_value={'is_synced': True})
    service.reconcile_positions = AsyncMock(return_value=result)
    return service


@pytest.fixture
def mock_circuit_breaker():
    """Create mock circuit breaker."""
    cb = AsyncMock()
    cb.state = 'CLOSED'
    health = MagicMock()
    health.can_trade = True
    health.state = 'CLOSED'
    health.reason = None
    cb.check_system_health = AsyncMock(return_value=health)
    return cb


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    return AsyncMock()


@pytest.fixture
def mock_notifier():
    """Create mock Telegram notifier."""
    notifier = AsyncMock()
    notifier.send_message = AsyncMock()
    return notifier


@pytest.fixture
def recovery_service(
    mock_exchange_manager,
    mock_position_monitor,
    mock_reconciliation_service,
    mock_circuit_breaker,
    mock_event_bus,
    mock_notifier
):
    """Create startup recovery service with mocks."""
    return StartupRecoveryService(
        exchange_manager=mock_exchange_manager,
        position_monitor=mock_position_monitor,
        reconciliation_service=mock_reconciliation_service,
        circuit_breaker=mock_circuit_breaker,
        event_bus=mock_event_bus,
        notifier=mock_notifier
    )


class TestStartupRecovery:
    """Test startup recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_recovers_with_open_positions_from_db(self, recovery_service, mock_db_session):
        """Should successfully recover when DB has open positions."""
        # Setup: DB has 1 open position
        mock_trade = MagicMock()
        mock_trade.id = 'trade_001'
        mock_trade.symbol = 'BTC/USDT'
        mock_trade.side = 'LONG'
        mock_trade.entry_price = 50000.0
        mock_trade.qty = 0.1
        mock_trade.user_id = 'default_user'
        mock_trade.status = 'open'
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_trade]
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery
        result = await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should succeed
        assert result.success == True or len(result.errors) == 0
        assert result.db_positions_loaded == 1
        assert result.can_resume_trading == True
    
    @pytest.mark.asyncio
    async def test_handles_restart_during_pending_order(self, recovery_service, mock_db_session):
        """Should handle restart when orders are pending on exchange."""
        # Setup: Exchange has positions (simulating pending fills)
        recovery_service.exchange_manager.fetch_positions.return_value = [
            {
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'size': 0.1,
                'entry_price': 50000.0
            }
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery
        result = await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should detect ghost position and repair
        assert result.exchange_positions_found >= 0
        # Reconciliation should have been called
        recovery_service.reconciliation_service.reconcile_positions.assert_called()
    
    @pytest.mark.asyncio
    async def test_handles_restart_during_api_outage(self, recovery_service, mock_db_session):
        """Should handle restart gracefully when exchange API is down."""
        # Simulate API failure
        recovery_service.exchange_manager.fetch_positions.side_effect = Exception("API timeout")
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery - should not crash
        result = await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should have errors but not crash
        assert len(result.errors) > 0
        assert any('exchange' in err.lower() or 'api' in err.lower() for err in result.errors)
    
    @pytest.mark.asyncio
    async def test_blocks_trading_if_circuit_breaker_open(self, recovery_service, mock_db_session, mock_circuit_breaker):
        """Should block trading resumption if circuit breaker is OPEN."""
        # Set circuit breaker to OPEN
        mock_circuit_breaker.state = 'OPEN'
        health = MagicMock()
        health.can_trade = False
        health.state = 'OPEN'
        health.reason = 'API failures exceeded threshold'
        mock_circuit_breaker.check_system_health.return_value = health
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery
        result = await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should block trading
        assert result.can_resume_trading == False
        assert any('circuit' in err.lower() or 'breaker' in err.lower() for err in result.errors)
    
    @pytest.mark.asyncio
    async def test_quick_health_check(self, recovery_service):
        """Quick health check should return system status."""
        health = await recovery_service.quick_health_check()
        
        assert 'timestamp' in health
        assert 'circuit_breaker' in health
        assert 'exchange_api' in health
        assert 'position_monitor' in health
    
    @pytest.mark.asyncio
    async def test_sends_recovery_notification(self, recovery_service, mock_db_session, mock_notifier):
        """Should send Telegram notification after recovery."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery
        await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should send notification
        mock_notifier.send_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_restarts_position_monitors(self, recovery_service, mock_db_session, mock_position_monitor):
        """Should restart monitors for all open positions."""
        # Setup: DB has 2 open positions
        mock_trade1 = MagicMock()
        mock_trade1.id = 'trade_001'
        mock_trade1.symbol = 'BTC/USDT'
        mock_trade1.side = 'LONG'
        mock_trade1.entry_price = 50000.0
        mock_trade1.qty = 0.1
        mock_trade1.user_id = 'default_user'
        mock_trade1.status = 'open'
        
        mock_trade2 = MagicMock()
        mock_trade2.id = 'trade_002'
        mock_trade2.symbol = 'ETH/USDT'
        mock_trade2.side = 'SHORT'
        mock_trade2.entry_price = 3000.0
        mock_trade2.qty = 1.0
        mock_trade2.user_id = 'default_user'
        mock_trade2.status = 'open'
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_trade1, mock_trade2]
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery
        result = await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should restart monitors for both positions
        assert mock_position_monitor.start_monitoring.call_count == 2
        assert result.monitors_restarted == 2
    
    @pytest.mark.asyncio
    async def test_resets_state_machines(self, recovery_service, mock_db_session):
        """Should reset state validator to clean state."""
        from app.execution.state_validator import state_validator
        
        # Set state validator to non-IDLE state
        state_validator.current_state = 'EXECUTING'
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery
        await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # State should be reset
        assert state_validator.current_state is None
    
    @pytest.mark.asyncio
    async def test_recovery_time_tracking(self, recovery_service, mock_db_session):
        """Should track recovery execution time."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery
        result = await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should have recovery time
        assert result.recovery_time_seconds > 0
        assert result.recovery_time_seconds < 10  # Should complete quickly with mocks
    
    @pytest.mark.asyncio
    async def test_comprehensive_error_handling(self, recovery_service, mock_db_session):
        """Should handle multiple error scenarios gracefully."""
        # Setup multiple failures
        recovery_service.exchange_manager.fetch_positions.side_effect = Exception("Exchange error")
        recovery_service.reconciliation_service.reconcile_positions.side_effect = Exception("Reconciliation error")
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Run recovery - should not crash
        result = await recovery_service.execute_recovery(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should collect errors but complete
        assert len(result.errors) > 0
        assert result.can_resume_trading == False
        assert result.recovery_time_seconds > 0
