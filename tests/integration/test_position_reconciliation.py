"""
Integration tests for Position Reconciliation Service.

Tests:
1. Detects orphaned positions (in DB but not exchange)
2. Detects ghost positions (on exchange but not DB)
3. Repairs orphaned positions by marking closed
4. Repairs ghost positions by creating DB records
5. Detects quantity mismatches with tolerance
6. Generates actionable recommendations
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reconciliation_service import PositionReconciliationService, ReconciliationResult
from app.database.models import PaperTrades


@pytest.fixture
def mock_exchange_manager():
    """Create mock exchange manager."""
    manager = AsyncMock()
    return manager


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def reconciliation_service(mock_exchange_manager, mock_event_bus):
    """Create reconciliation service with mocks."""
    return PositionReconciliationService(
        exchange_manager=mock_exchange_manager,
        event_bus=mock_event_bus,
        sync_tolerance_pct=0.01  # 1% tolerance
    )


class TestPositionReconciliation:
    """Test position reconciliation logic."""
    
    @pytest.mark.asyncio
    async def test_detects_orphaned_positions(self, reconciliation_service, mock_exchange_manager, mock_db_session):
        """Should detect positions in DB but not on exchange."""
        # Setup: DB has 1 position, exchange has none
        mock_trade = MagicMock()
        mock_trade.id = 'trade_001'
        mock_trade.symbol = 'BTC/USDT'
        mock_trade.side = 'LONG'
        mock_trade.qty = 0.1
        mock_trade.entry_price = 50000.0
        mock_trade.leverage = 1
        mock_trade.user_id = 'default_user'
        mock_trade.status = 'open'
        
        # Mock DB query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_trade]
        mock_db_session.execute.return_value = mock_result
        
        # Mock exchange returns no positions
        mock_exchange_manager.fetch_positions.return_value = []
        
        # Run reconciliation
        result = await reconciliation_service.reconcile_positions(
            user_id='default_user',
            db_session=mock_db_session,
            auto_repair=False
        )
        
        # Should detect orphaned position
        assert len(result.orphaned_positions) == 1
        assert result.orphaned_positions[0]['trade_id'] == 'trade_001'
        assert result.is_synced == False
    
    @pytest.mark.asyncio
    async def test_detects_ghost_positions(self, reconciliation_service, mock_exchange_manager, mock_db_session):
        """Should detect positions on exchange but not in DB."""
        # Setup: DB has no positions, exchange has 1
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        # Mock exchange returns position
        mock_exchange_manager.fetch_positions.return_value = [
            {
                'symbol': 'ETH/USDT',
                'side': 'buy',
                'size': 1.0,
                'entry_price': 3000.0,
                'leverage': 1,
                'unrealized_pnl': 50.0
            }
        ]
        
        # Run reconciliation
        result = await reconciliation_service.reconcile_positions(
            user_id='default_user',
            db_session=mock_db_session,
            auto_repair=False
        )
        
        # Should detect ghost position
        assert len(result.ghost_positions) == 1
        assert result.ghost_positions[0]['symbol'] == 'ETH/USDT'
        assert result.is_synced == False
    
    @pytest.mark.asyncio
    async def test_repairs_orphaned_positions(self, reconciliation_service, mock_exchange_manager, mock_db_session):
        """Should mark orphaned positions as closed in DB."""
        # Setup orphaned position
        mock_trade = MagicMock()
        mock_trade.id = 'trade_002'
        mock_trade.symbol = 'BTC/USDT'
        mock_trade.status = 'open'
        mock_trade.notes = ''
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_trade]
        mock_db_session.execute.return_value = mock_result
        mock_exchange_manager.fetch_positions.return_value = []
        
        # Run reconciliation with auto-repair
        result = await reconciliation_service.reconcile_positions(
            user_id='default_user',
            db_session=mock_db_session,
            auto_repair=True
        )
        
        # Should repair orphaned position
        assert result.repaired_count >= 1
        assert mock_trade.status == 'closed'
        assert '[RECONCILIATION]' in mock_trade.notes
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_repairs_ghost_positions(self, reconciliation_service, mock_exchange_manager, mock_db_session):
        """Should create DB records for ghost positions."""
        # Setup ghost position
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        mock_exchange_manager.fetch_positions.return_value = [
            {
                'symbol': 'SOL/USDT',
                'side': 'long',
                'size': 10.0,
                'entry_price': 150.0,
                'leverage': 5
            }
        ]
        
        # Run reconciliation with auto-repair
        result = await reconciliation_service.reconcile_positions(
            user_id='default_user',
            db_session=mock_db_session,
            auto_repair=True
        )
        
        # Should create new trade record
        assert result.repaired_count >= 1
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_detects_quantity_mismatches_with_tolerance(self, reconciliation_service, mock_exchange_manager, mock_db_session):
        """Should detect quantity mismatches beyond tolerance threshold."""
        # Setup matching positions with slight quantity difference
        mock_trade = MagicMock()
        mock_trade.id = 'trade_003'
        mock_trade.symbol = 'BTC/USDT'
        mock_trade.side = 'LONG'
        mock_trade.qty = 1.0  # DB says 1.0
        mock_trade.entry_price = 50000.0
        mock_trade.leverage = 1
        mock_trade.user_id = 'default_user'
        mock_trade.status = 'open'
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_trade]
        mock_db_session.execute.return_value = mock_result
        
        # Exchange has slightly different quantity (2% difference > 1% tolerance)
        mock_exchange_manager.fetch_positions.return_value = [
            {
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'size': 1.02,  # 2% more than DB
                'entry_price': 50000.0,
                'leverage': 1
            }
        ]
        
        # Run reconciliation
        result = await reconciliation_service.reconcile_positions(
            user_id='default_user',
            db_session=mock_db_session,
            auto_repair=False
        )
        
        # Should detect mismatch
        assert len(result.mismatches) >= 1
        assert result.mismatches[0]['type'] == 'quantity_mismatch'
        assert result.is_synced == False
    
    @pytest.mark.asyncio
    async def test_generates_recommendations(self, reconciliation_service, mock_exchange_manager, mock_db_session):
        """Should generate actionable recommendations based on findings."""
        # Setup with both orphaned and ghost positions
        mock_trade = MagicMock()
        mock_trade.id = 'trade_004'
        mock_trade.symbol = 'BTC/USDT'
        mock_trade.side = 'LONG'
        mock_trade.qty = 0.1
        mock_trade.entry_price = 50000.0
        mock_trade.leverage = 1
        mock_trade.user_id = 'default_user'
        mock_trade.status = 'open'
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_trade]
        mock_db_session.execute.return_value = mock_result
        
        # Exchange has different position
        mock_exchange_manager.fetch_positions.return_value = [
            {
                'symbol': 'ETH/USDT',
                'side': 'buy',
                'size': 1.0,
                'entry_price': 3000.0,
                'leverage': 1
            }
        ]
        
        # Get report
        report = await reconciliation_service.get_reconciliation_report(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should have recommendations
        assert 'recommendations' in report
        assert len(report['recommendations']) > 0
        
        # Recommendations should mention orphaned and ghost positions
        recommendations_text = ' '.join(report['recommendations']).lower()
        assert 'orphaned' in recommendations_text or 'ghost' in recommendations_text
    
    @pytest.mark.asyncio
    async def test_synced_positions_no_action_required(self, reconciliation_service, mock_exchange_manager, mock_db_session):
        """When all positions match, should indicate no action required."""
        # Setup matching positions
        mock_trade = MagicMock()
        mock_trade.id = 'trade_005'
        mock_trade.symbol = 'BTC/USDT'
        mock_trade.side = 'LONG'
        mock_trade.qty = 1.0
        mock_trade.entry_price = 50000.0
        mock_trade.leverage = 1
        mock_trade.user_id = 'default_user'
        mock_trade.status = 'open'
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_trade]
        mock_db_session.execute.return_value = mock_result
        
        # Exchange has identical position
        mock_exchange_manager.fetch_positions.return_value = [
            {
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'size': 1.0,
                'entry_price': 50000.0,
                'leverage': 1
            }
        ]
        
        # Get report
        report = await reconciliation_service.get_reconciliation_report(
            user_id='default_user',
            db_session=mock_db_session
        )
        
        # Should be synced
        assert report['summary']['is_synced'] == True
        assert 'no action required' in ' '.join(report['recommendations']).lower()
    
    @pytest.mark.asyncio
    async def test_publishes_reconciliation_event(self, reconciliation_service, mock_exchange_manager, mock_db_session, mock_event_bus):
        """Should publish POSITION_RECONCILED event after reconciliation."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        mock_exchange_manager.fetch_positions.return_value = []
        
        # Run reconciliation
        await reconciliation_service.reconcile_positions(
            user_id='default_user',
            db_session=mock_db_session,
            auto_repair=False
        )
        
        # Should publish event
        mock_event_bus.publish.assert_called()
        call_args = mock_event_bus.publish.call_args
        assert call_args[0][0] == 'POSITION_RECONCILED'
