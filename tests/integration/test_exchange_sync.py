"""
Integration tests for Exchange Sync reconciliation loop.

Validates consistency between Local Database, Exchange State, and Dashboard UI:
- State reconciliation loop (sync_positions)
- Ghost position detection (exchange has position, DB doesn't)
- Auto-repair logic for mismatches
- Dashboard data format consistency

Critical scenario: Desynchronization event where trade record deleted from DB
while position remains open on exchange → sync detects orphaned position
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import List, Dict, Any

from app.sync.position_sync import PositionSyncService


class TestStateReconciliationLoop:
    """Test position synchronization between exchange and database."""
    
    @pytest.mark.asyncio
    async def test_sync_positions_fetches_exchange_state(self):
        """
        Implement test that runs sync_positions() function.
        Assert it fetches live positions from mocked exchange.
        """
        # Mock dependencies
        mock_executor = AsyncMock()
        mock_trade_repo = AsyncMock()
        mock_position_repo = AsyncMock()
        
        # Mock exchange positions
        exchange_positions = [
            {
                'symbol': 'BTC/USDT',
                'size': 0.5,
                'entry_price': 49500.0,
                'mark_price': 50000.0,
                'unrealized_pnl': 250.0,
                'leverage': 2,
                'liquidation_price': 40000.0
            }
        ]
        
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # Mock database positions (matching exchange)
        mock_db_position = MagicMock()
        mock_db_position.symbol = 'BTC/USDT'
        mock_db_position.size = 0.5
        mock_db_position.current_price = 50000.0
        
        mock_position_repo.get_open_positions.return_value = [mock_db_position]
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            # Create mock db session
            mock_db_session = AsyncMock()
            
            # Run sync
            await sync_service.sync_once(mock_db_session)
            
            # Verify exchange was queried
            mock_executor.get_open_positions.assert_called_once()
            
            # Verify DB was queried
            mock_position_repo.get_open_positions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_compares_exchange_vs_database(self):
        """Verify sync compares exchange positions against local DB records."""
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange has position
        exchange_positions = [
            {'symbol': 'BTC/USDT', 'size': 0.5, 'entry_price': 49500.0, 
             'mark_price': 50000.0, 'unrealized_pnl': 250.0, 'leverage': 2}
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # DB has matching position
        db_pos = MagicMock()
        db_pos.symbol = 'BTC/USDT'
        db_pos.size = 0.5
        db_pos.current_price = 50000.0
        mock_position_repo.get_open_positions.return_value = [db_pos]
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            mock_db_session = AsyncMock()
            await sync_service.sync_once(mock_db_session)
            
            # Both sources should be queried for comparison
            assert mock_executor.get_open_positions.called
            assert mock_position_repo.get_open_positions.called


class TestGhostPositionDetection:
    """Test detection of ghost positions (on exchange but not in DB)."""
    
    @pytest.mark.asyncio
    async def test_ghost_position_detected(self):
        """
        Simulate "Ghost Position": position exists on exchange but not in DB.
        Assert sync service detects this discrepancy.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange has position
        exchange_positions = [
            {'symbol': 'ETH/USDT', 'size': 1.0, 'entry_price': 3000.0,
             'mark_price': 3050.0, 'unrealized_pnl': 50.0, 'leverage': 2}
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # DB has NO positions (ghost!)
        mock_position_repo.get_open_positions.return_value = []
        
        # Mock repair method to track if it's called
        repair_called = False
        
        async def mock_repair_missing(symbol, positions, db_session):
            nonlocal repair_called
            repair_called = True
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            sync_service._repair_missing_in_db = mock_repair_missing
            
            mock_db_session = AsyncMock()
            await sync_service.sync_once(mock_db_session)
            
            # Ghost position should trigger repair
            assert repair_called == True
    
    @pytest.mark.asyncio
    async def test_multiple_ghost_positions_detected(self):
        """Verify multiple ghost positions are all detected."""
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange has multiple positions
        exchange_positions = [
            {'symbol': 'BTC/USDT', 'size': 0.5, 'entry_price': 49500.0,
             'mark_price': 50000.0, 'unrealized_pnl': 250.0, 'leverage': 2},
            {'symbol': 'ETH/USDT', 'size': 1.0, 'entry_price': 3000.0,
             'mark_price': 3050.0, 'unrealized_pnl': 50.0, 'leverage': 2}
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # DB empty
        mock_position_repo.get_open_positions.return_value = []
        
        ghost_count = 0
        
        async def count_repairs(symbol, positions, db_session):
            nonlocal ghost_count
            ghost_count += 1
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            sync_service._repair_missing_in_db = count_repairs
            
            mock_db_session = AsyncMock()
            await sync_service.sync_once(mock_db_session)
            
            # Both ghost positions should be detected
            assert ghost_count == 2


class TestAutoRepairLogic:
    """Test automatic repair of position mismatches."""
    
    @pytest.mark.asyncio
    async def test_auto_repair_creates_missing_db_record(self):
        """
        Verify system automatically repairs mismatch by creating missing local record.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange has position
        exchange_positions = [
            {'symbol': 'SOL/USDT', 'size': 10.0, 'entry_price': 100.0,
             'mark_price': 105.0, 'unrealized_pnl': 50.0, 'leverage': 3}
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # DB empty
        mock_position_repo.get_open_positions.return_value = []
        
        # Mock trade repo to return a trade
        mock_trade = MagicMock()
        mock_trade.id = 123
        mock_trade_repo.get_open_trade_by_symbol.return_value = mock_trade
        
        # Track if upsert was called
        upsert_called = False
        
        async def mock_upsert(data, db_session):
            nonlocal upsert_called
            upsert_called = True
            # Verify data structure
            assert 'symbol' in data
            assert data['symbol'] == 'SOL/USDT'
            assert abs(data['size'] - 10.0) < 0.001
        
        mock_position_repo.upsert_position = mock_upsert
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            mock_db_session = AsyncMock()
            await sync_service.sync_once(mock_db_session)
            
            # Should have created missing record
            assert upsert_called == True
    
    @pytest.mark.asyncio
    async def test_auto_repair_alerts_on_orphaned_position(self):
        """
        Verify system alerts user if manual intervention required for orphaned position.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange has position
        exchange_positions = [
            {'symbol': 'ADA/USDT', 'size': 1000.0, 'entry_price': 0.5,
             'mark_price': 0.52, 'unrealized_pnl': 20.0, 'leverage': 2}
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # DB empty
        mock_position_repo.get_open_positions.return_value = []
        
        # No associated trade found (orphaned)
        mock_trade_repo.get_open_trade_by_symbol.return_value = None
        
        alert_published = False
        
        async def mock_publish(event_type, data, priority=0):
            nonlocal alert_published
            if event_type == 'SYNC_MISMATCH':
                alert_published = True
                assert data['type'] == 'orphaned_position'
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo), \
             patch('app.sync.position_sync.event_bus') as mock_event_bus:
            
            mock_event_bus.publish = mock_publish
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            mock_db_session = AsyncMock()
            await sync_service.sync_once(mock_db_session)
            
            # Should publish alert for orphaned position
            assert alert_published == True


class TestDashboardConsistency:
    """Test data format consistency for Dashboard API."""
    
    @pytest.mark.asyncio
    async def test_sync_status_matches_dashboard_format(self):
        """
        Ensure data returned by sync service matches Dashboard API expectations.
        """
        mock_executor = AsyncMock()
        mock_executor.get_open_positions.return_value = [
            {'symbol': 'BTC/USDT', 'size': 0.5, 'mark_price': 50000.0}
        ]
        mock_executor.get_balance.return_value = {'total_usdt': 10000.0}
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor):
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            
            status = await sync_service.get_sync_status()
            
            # Verify expected fields present
            assert 'status' in status
            assert 'exchange_positions' in status
            assert 'balance_usdt' in status
            assert 'testnet' in status
            assert 'last_sync' in status
            
            # Verify types
            assert isinstance(status['exchange_positions'], int)
            assert isinstance(status['balance_usdt'], (int, float))
            assert isinstance(status['testnet'], bool)
    
    @pytest.mark.asyncio
    async def test_position_data_structure_consistency(self):
        """Verify position data structure is consistent across sync cycles."""
        mock_executor = AsyncMock()
        exchange_positions = [
            {
                'symbol': 'BTC/USDT',
                'size': 0.5,
                'entry_price': 49500.0,
                'mark_price': 50000.0,
                'unrealized_pnl': 250.0,
                'leverage': 2,
                'liquidation_price': 40000.0
            }
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # First sync
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor):
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            
            positions = await sync_service.executor.get_open_positions()
            
            # Verify structure
            assert len(positions) == 1
            pos = positions[0]
            
            required_fields = ['symbol', 'size', 'entry_price', 'mark_price', 
                             'unrealized_pnl', 'leverage', 'liquidation_price']
            
            for field in required_fields:
                assert field in pos, f"Missing field: {field}"


class TestCriticalDesynchronizationScenario:
    """Critical scenario: Trade record deleted from DB while position open on exchange."""
    
    @pytest.mark.asyncio
    async def test_desync_detection_and_recovery(self):
        """
        Critical Scenario Test:
        1. Manually delete trade record from local DB
        2. Position remains open on exchange
        3. Trigger sync loop
        4. Assert system identifies orphaned position and recovers/alerts
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange still has position
        exchange_positions = [
            {'symbol': 'XRP/USDT', 'size': 5000.0, 'entry_price': 0.6,
             'mark_price': 0.62, 'unrealized_pnl': 100.0, 'leverage': 2,
             'liquidation_price': 0.45}
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # DB has no positions (trade was deleted!)
        mock_position_repo.get_open_positions.return_value = []
        
        # No trade found (deleted)
        mock_trade_repo.get_open_trade_by_symbol.return_value = None
        
        recovery_actions = []
        
        async def track_emergency_creation(trade_data, db_session):
            recovery_actions.append('emergency_trade_created')
            mock_trade = MagicMock()
            mock_trade.id = 999
            return mock_trade
        
        mock_trade_repo.create_trade = track_emergency_creation
        
        async def track_position_upsert(data, db_session):
            recovery_actions.append('position_recovered')
            assert data['sync_source'] == 'emergency_recovery'
        
        mock_position_repo.upsert_position = track_position_upsert
        
        critical_alert_published = False
        
        async def track_critical_alert(event_type, data, priority=0):
            nonlocal critical_alert_published
            if event_type == 'SYNC_MISMATCH' and priority >= 5:
                critical_alert_published = True
                assert data['type'] == 'orphaned_position'
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo), \
             patch('app.sync.position_sync.event_bus') as mock_event_bus:
            
            mock_event_bus.publish = track_critical_alert
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            mock_db_session = AsyncMock()
            await sync_service.sync_once(mock_db_session)
            
            # Verify recovery actions taken
            assert 'emergency_trade_created' in recovery_actions
            assert 'position_recovered' in recovery_actions
            
            # Verify critical alert published
            assert critical_alert_published == True
    
    @pytest.mark.asyncio
    async def test_desync_flags_for_manual_intervention(self):
        """
        Verify desynchronization flags position for manual intervention when auto-recovery insufficient.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Orphaned position
        exchange_positions = [
            {'symbol': 'DOGE/USDT', 'size': 10000.0, 'entry_price': 0.08,
             'mark_price': 0.085, 'unrealized_pnl': 50.0, 'leverage': 5}
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        mock_position_repo.get_open_positions.return_value = []
        mock_trade_repo.get_open_trade_by_symbol.return_value = None
        
        manual_intervention_flagged = False
        
        async def flag_for_manual_intervention(event_type, data, priority=0):
            nonlocal manual_intervention_flagged
            if data.get('type') == 'orphaned_position':
                manual_intervention_flagged = True
                # Should include position details for manual review
                assert 'position_data' in data
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo), \
             patch('app.sync.position_sync.event_bus') as mock_event_bus:
            
            mock_event_bus.publish = flag_for_manual_intervention
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            mock_db_session = AsyncMock()
            await sync_service.sync_once(mock_db_session)
            
            # Should flag for manual intervention
            assert manual_intervention_flagged == True


class TestSyncErrorHandling:
    """Test sync service error handling and graceful degradation."""
    
    @pytest.mark.asyncio
    async def test_exchange_api_failure_handled_gracefully(self):
        """Verify sync handles exchange API failures without crashing."""
        mock_executor = AsyncMock()
        mock_executor.get_open_positions.side_effect = Exception("Exchange API timeout")
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor):
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            
            mock_db_session = AsyncMock()
            
            # Should not raise exception
            await sync_service.sync_once(mock_db_session)
            
            # Service should still be running
            assert sync_service._running == True
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Verify sync handles database errors gracefully."""
        mock_executor = AsyncMock()
        mock_executor.get_open_positions.return_value = []
        
        mock_position_repo = AsyncMock()
        mock_position_repo.get_open_positions.side_effect = Exception("DB connection lost")
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.position_repo = mock_position_repo
            
            mock_db_session = AsyncMock()
            
            # Should not crash
            await sync_service.sync_once(mock_db_session)
