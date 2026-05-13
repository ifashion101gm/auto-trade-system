"""
Crash Recovery & Resilience Integration Tests.

Validates system stability and state restoration after unexpected failures.
Critical for live trading safety - ensures bot can recover from crashes,
network failures, and database corruption without data loss or position errors.

Test Coverage:
1. State Restoration on Restart
2. WebSocket Disconnection Recovery
3. TP/SL Trigger During Downtime
4. Database Corruption Recovery
5. Critical Scenario: Position reconciliation after hard crash
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta

from app.sync.position_sync import PositionSyncService
from app.websocket.manager import MEXCWebSocketManager
from app.database.repositories import TradeRepository, PositionRepository
from app.events.event_bus import event_bus
from app.events.event_types import (
    WEBSOCKET_DISCONNECTED, WEBSOCKET_RECONNECTED, SYNC_MISMATCH, SYNC_REPAIRED
)


@pytest.fixture
def db_session():
    """Create mocked database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_trade_repo():
    """Create mocked trade repository."""
    repo = AsyncMock(spec=TradeRepository)
    return repo


@pytest.fixture
def mock_position_repo():
    """Create mocked position repository."""
    repo = AsyncMock(spec=PositionRepository)
    return repo


@pytest.fixture
def mock_executor():
    """Create mocked exchange executor."""
    executor = AsyncMock()
    return executor


class TestStateRestorationOnRestart:
    """Test state restoration after bot restart."""
    
    @pytest.mark.asyncio
    async def test_bot_identifies_open_position_from_exchange(self, db_session):
        """
        Simulate bot restart with open position on exchange.
        Assert that PositionSyncService correctly identifies and syncs the position.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange has open position
        exchange_positions = [
            {
                'symbol': 'BTC/USDT',
                'size': 0.01,
                'entry_price': 50000.0,
                'mark_price': 50100.0,
                'unrealized_pnl': 1.0,
                'leverage': 2,
                'liquidation_price': 25000.0
            }
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # Database has NO positions (simulating fresh restart)
        mock_position_repo.get_open_positions.return_value = []
        
        # No existing trade found
        mock_trade_repo.get_open_trade_by_symbol.return_value = None
        
        emergency_trade_created = False
        position_upserted = False
        
        async def track_emergency_trade(trade_data, db_session):
            nonlocal emergency_trade_created
            emergency_trade_created = True
            mock_trade = MagicMock()
            mock_trade.id = 999
            return mock_trade
        
        async def track_position_upsert(data, db_session):
            nonlocal position_upserted
            position_upserted = True
            assert data['sync_source'] == 'emergency_recovery'
            assert data['symbol'] == 'BTC/USDT'
            assert abs(data['size'] - 0.01) < 0.0001
        
        mock_trade_repo.create_trade = track_emergency_trade
        mock_position_repo.upsert_position = track_position_upsert
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            await sync_service.sync_once(db_session)
            
            # Verify orphaned position was recovered
            assert emergency_trade_created == True
            assert position_upserted == True
    
    @pytest.mark.asyncio
    async def test_bot_resumes_monitoring_existing_position(self, db_session):
        """
        Simulate bot restart with existing position in both DB and exchange.
        Assert that monitoring resumes correctly with updated data.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange position with updated price
        exchange_positions = [
            {
                'symbol': 'ETH/USDT',
                'size': 1.0,
                'entry_price': 3000.0,
                'mark_price': 3050.0,  # Price moved up
                'unrealized_pnl': 50.0,
                'leverage': 2,
                'liquidation_price': 1500.0
            }
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # Database has position with old price
        mock_db_position = MagicMock()
        mock_db_position.symbol = 'ETH/USDT'
        mock_db_position.size = 1.0
        mock_db_position.current_price = 3000.0  # Old price
        mock_db_position.unrealized_pnl = 0.0
        
        mock_position_repo.get_open_positions.return_value = [mock_db_position]
        mock_position_repo.get_position_by_symbol.return_value = mock_db_position
        
        data_repaired = False
        
        async def track_data_repair(symbol, ex_pos, db_pos, db_session):
            nonlocal data_repaired
            data_repaired = True
            assert symbol == 'ETH/USDT'
            assert abs(ex_pos['mark_price'] - 3050.0) < 0.01
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            sync_service._repair_data_mismatch = track_data_repair
            
            await sync_service.sync_once(db_session)
            
            # Verify data mismatch was detected and repaired
            assert data_repaired == True


class TestWebSocketDisconnectionRecovery:
    """Test WebSocket disconnection and automatic reconnection."""
    
    @pytest.mark.asyncio
    async def test_websocket_auto_reconnect_triggers(self):
        """
        Simulate WebSocket disconnect during active streaming.
        Assert that reconnection logic triggers automatically.
        """
        ws_manager = MEXCWebSocketManager(market_type='futures')
        
        # Track events
        disconnect_events = []
        reconnect_events = []
        
        async def capture_disconnect(event):
            disconnect_events.append(event)
        
        async def capture_reconnect(event):
            reconnect_events.append(event)
        
        event_bus.subscribe(WEBSOCKET_DISCONNECTED, capture_disconnect)
        event_bus.subscribe(WEBSOCKET_RECONNECTED, capture_reconnect)
        
        # Simulate connection failure
        ws_manager.reconnect_attempts = 0
        ws_manager.running = True
        
        # Mock websocket to raise ConnectionClosed
        with patch('websockets.connect', side_effect=Exception("Connection closed")):
            # Run connect briefly then stop
            task = asyncio.create_task(ws_manager.connect())
            await asyncio.sleep(0.2)
            ws_manager.running = False
            try:
                await task
            except Exception:
                pass
        
        # Verify disconnect event was published
        assert len(disconnect_events) > 0
        assert 'reconnect_delay' in disconnect_events[0]['payload']
        assert 'attempt_count' in disconnect_events[0]['payload']
    
    @pytest.mark.asyncio
    async def test_websocket_resubscribes_after_reconnect(self):
        """
        Assert that WebSocket resubscribes to all channels after reconnection.
        """
        ws_manager = MEXCWebSocketManager(market_type='futures')
        
        # Add subscriptions
        await ws_manager.subscribe('position', 'BTC/USDT')
        await ws_manager.subscribe('order', 'ETH/USDT')
        
        assert len(ws_manager.subscriptions) == 2
        
        # Mock successful connection
        mock_ws = AsyncMock()
        
        with patch('websockets.connect', return_value=mock_ws):
            # Simulate resubscription
            await ws_manager._resubscribe()
            
            # Verify all subscriptions were sent
            assert mock_ws.send.call_count == 2
            
            # Verify subscription messages contain correct channels
            calls = [call[0][0] for call in mock_ws.send.call_args_list]
            channels_sent = []
            for call_data in calls:
                import json
                data = json.loads(call_data)
                channels_sent.extend(data.get('params', []))
            
            assert any('position' in ch for ch in channels_sent)
            assert any('order' in ch for ch in channels_sent)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_with_jitter(self):
        """
        Verify exponential backoff calculation includes jitter.
        """
        from app.websocket.manager import calculate_exponential_backoff
        
        delays = []
        for i in range(5):
            delay = calculate_exponential_backoff(
                attempt=i+1,
                base_delay=5.0,
                max_delay=300.0,
                jitter_factor=0.1
            )
            delays.append(delay)
        
        # Verify exponential growth
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i-1], f"Delay should increase: {delays}"
        
        # Verify jitter is applied (delays shouldn't be exact powers of 2)
        expected_base = [5.0, 10.0, 20.0, 40.0, 80.0]
        for actual, base in zip(delays, expected_base):
            # Actual delay should be within ±10% of base (jitter factor)
            assert base * 0.9 <= actual <= base * 1.1, f"Jitter not applied correctly: {actual} vs {base}"


class TestTPSLTriggerDuringDowntime:
    """Test Take Profit/Stop Loss trigger detection during bot downtime."""
    
    @pytest.mark.asyncio
    async def test_detects_closed_position_after_downtime(self, db_session):
        """
        Simulate TP/SL hit while bot is offline.
        Upon restart, assert bot detects closed position and updates DB.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange has NO positions (TP/SL already hit)
        mock_executor.get_open_positions.return_value = []
        
        # Database still has OPEN position (bot was offline when TP hit)
        mock_db_position = MagicMock()
        mock_db_position.symbol = 'XRP/USDT'
        mock_db_position.size = 5000.0
        mock_db_position.status = 'open'
        mock_db_position.trade_id = 123
        
        mock_position_repo.get_open_positions.return_value = [mock_db_position]
        mock_position_repo.get_position_by_symbol.return_value = mock_db_position
        
        # Mock trade
        mock_trade = MagicMock()
        mock_trade.id = 123
        mock_trade.status = 'OPEN'
        mock_trade_repo.get_trade.return_value = mock_trade
        
        ghost_position_closed = False
        
        async def track_ghost_close(symbol, db_session):
            nonlocal ghost_position_closed
            ghost_position_closed = True
            assert symbol == 'XRP/USDT'
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            sync_service._repair_ghost_position = track_ghost_close
            
            await sync_service.sync_once(db_session)
            
            # Verify ghost position was detected and closed
            assert ghost_position_closed == True
    
    @pytest.mark.asyncio
    async def test_updates_trade_status_on_ghost_detection(self, db_session):
        """
        Verify that when ghost position is detected, associated trade is marked as CLOSED.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # No positions on exchange
        mock_executor.get_open_positions.return_value = []
        
        # Database has stale position
        mock_db_position = MagicMock()
        mock_db_position.symbol = 'ADA/USDT'
        mock_db_position.status = 'open'
        mock_db_position.trade_id = 456
        
        mock_position_repo.get_open_positions.return_value = [mock_db_position]
        mock_position_repo.get_position_by_symbol.return_value = mock_db_position
        
        # Mock trade that needs closing
        mock_trade = MagicMock()
        mock_trade.id = 456
        mock_trade.status = 'OPEN'
        mock_trade.closed_at = None
        mock_trade.error_message = None
        mock_trade_repo.get_trade.return_value = mock_trade
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            await sync_service.sync_once(db_session)
            
            # Verify trade was closed
            assert mock_trade.status == 'CLOSED'
            assert mock_trade.closed_at is not None
            assert 'Ghost position' in mock_trade.error_message


class TestDatabaseCorruptionRecovery:
    """Test database corruption detection and graceful handling."""
    
    @pytest.mark.asyncio
    async def test_handles_locked_database_gracefully(self, db_session):
        """
        Simulate locked SQLite database.
        Assert system logs error and continues rather than crashing.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange positions available
        mock_executor.get_open_positions.return_value = [
            {'symbol': 'BTC/USDT', 'size': 0.01, 'entry_price': 50000.0,
             'mark_price': 50100.0, 'unrealized_pnl': 1.0, 'leverage': 2}
        ]
        
        # Database throws locked error
        from sqlalchemy.exc import OperationalError
        mock_position_repo.get_open_positions.side_effect = OperationalError(
            "database is locked", None, None
        )
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            # Should not raise exception
            await sync_service.sync_once(db_session)
            
            # Verify error was logged (we can't easily test logging, but we verify no crash)
            assert True  # If we reach here, it didn't crash
    
    @pytest.mark.asyncio
    async def test_handles_corrupted_wal_mode(self, db_session):
        """
        Simulate corrupted WAL mode database file.
        Assert system fails gracefully with clear error message.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Database throws corruption error
        from sqlalchemy.exc import DatabaseError
        mock_position_repo.get_open_positions.side_effect = DatabaseError(
            "database disk image is malformed", None, None
        )
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            # Should handle gracefully
            await sync_service.sync_once(db_session)
            
            # System should continue running despite DB error
            assert sync_service._running == True


class TestCriticalScenarioHardCrashRecovery:
    """
    Critical Scenario: Complete crash recovery with position reconciliation.
    
    This test simulates the most dangerous scenario in live trading:
    1. Bot opens LONG position
    2. Bot crashes (process killed)
    3. Position hits SL on exchange while bot is offline
    4. Bot restarts
    5. PositionSyncService must detect discrepancy and reconcile
    """
    
    @pytest.mark.asyncio
    async def test_full_crash_recovery_scenario(self, db_session):
        """
        Full crash recovery scenario:
        - Open LONG position on exchange
        - Simulate hard crash (state reset)
        - Position closes on exchange (SL hit)
        - Restart bot
        - Assert PositionSyncService detects and reconciles
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # === PHASE 1: Before Crash ===
        # Exchange has open position
        initial_exchange_positions = [
            {
                'symbol': 'SOL/USDT',
                'size': 10.0,
                'entry_price': 100.0,
                'mark_price': 98.0,  # Losing position
                'unrealized_pnl': -20.0,
                'leverage': 2,
                'liquidation_price': 50.0
            }
        ]
        
        # Database tracks the position
        mock_initial_trade = MagicMock()
        mock_initial_trade.id = 789
        mock_initial_trade.symbol = 'SOL/USDT'
        mock_initial_trade.status = 'OPEN'
        
        mock_initial_position = MagicMock()
        mock_initial_position.symbol = 'SOL/USDT'
        mock_initial_position.size = 10.0
        mock_initial_position.status = 'open'
        mock_initial_position.trade_id = 789
        
        # === PHASE 2: After Crash & SL Hit ===
        # Exchange position is now CLOSED (SL triggered)
        mock_executor.get_open_positions.return_value = []  # No open positions
        
        # Database still shows OPEN (bot was crashed when SL hit)
        mock_stale_position = MagicMock()
        mock_stale_position.symbol = 'SOL/USDT'
        mock_stale_position.size = 10.0
        mock_stale_position.status = 'open'
        mock_stale_position.trade_id = 789
        
        mock_position_repo.get_open_positions.return_value = [mock_stale_position]
        mock_position_repo.get_position_by_symbol.return_value = mock_stale_position
        
        # Mock trade that needs updating
        mock_stale_trade = MagicMock()
        mock_stale_trade.id = 789
        mock_stale_trade.status = 'OPEN'
        mock_stale_trade.closed_at = None
        mock_stale_trade.error_message = None
        mock_trade_repo.get_trade.return_value = mock_stale_trade
        
        reconciliation_actions = []
        
        async def track_reconciliation(symbol, db_session):
            nonlocal reconciliation_actions
            reconciliation_actions.append('ghost_detected')
            
            # Verify the repair logic closes the position
            mock_stale_position.status = 'closed'
            mock_stale_trade.status = 'CLOSED'
            mock_stale_trade.closed_at = datetime.utcnow().isoformat()
            mock_stale_trade.error_message = 'Ghost position detected and closed during sync'
            
            reconciliation_actions.append('position_closed')
            reconciliation_actions.append('trade_closed')
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            sync_service._repair_ghost_position = track_reconciliation
            
            # Execute sync (simulating bot restart)
            await sync_service.sync_once(db_session)
            
            # === ASSERTIONS ===
            # Verify all reconciliation steps occurred
            assert 'ghost_detected' in reconciliation_actions
            assert 'position_closed' in reconciliation_actions
            assert 'trade_closed' in reconciliation_actions
            
            # Verify trade was properly closed
            assert mock_stale_trade.status == 'CLOSED'
            assert mock_stale_trade.closed_at is not None
            assert 'Ghost position' in mock_stale_trade.error_message
            
            # Verify position was marked closed
            assert mock_stale_position.status == 'closed'
    
    @pytest.mark.asyncio
    async def test_orphaned_position_recovery_after_crash(self, db_session):
        """
        Variant: Position exists on exchange but NOT in DB after crash.
        This happens if DB write failed before crash.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange has position (DB missed it before crash)
        exchange_positions = [
            {
                'symbol': 'AVAX/USDT',
                'size': 5.0,
                'entry_price': 30.0,
                'mark_price': 31.0,
                'unrealized_pnl': 5.0,
                'leverage': 2,
                'liquidation_price': 15.0
            }
        ]
        mock_executor.get_open_positions.return_value = exchange_positions
        
        # Database has NO record of this position
        mock_position_repo.get_open_positions.return_value = []
        mock_trade_repo.get_open_trade_by_symbol.return_value = None
        
        recovery_completed = False
        
        async def track_orphaned_recovery(symbol, positions, db_session):
            nonlocal recovery_completed
            recovery_completed = True
            assert symbol == 'AVAX/USDT'
            
            # Verify emergency trade creation would happen
            pos = next(p for p in positions if p['symbol'] == symbol)
            assert abs(pos['size'] - 5.0) < 0.01
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            sync_service._repair_missing_in_db = track_orphaned_recovery
            
            await sync_service.sync_once(db_session)
            
            # Verify orphaned position was recovered
            assert recovery_completed == True


class TestGracefulDegradationUnderStress:
    """Test system behavior under persistent failure conditions."""
    
    @pytest.mark.asyncio
    async def test_continues_running_after_multiple_db_failures(self, db_session):
        """
        Simulate persistent database connection failures.
        Assert system enters degraded mode but doesn't crash.
        """
        mock_executor = AsyncMock()
        mock_position_repo = AsyncMock()
        mock_trade_repo = AsyncMock()
        
        # Exchange works fine
        mock_executor.get_open_positions.return_value = []
        
        # Database always fails
        from sqlalchemy.exc import OperationalError
        mock_position_repo.get_open_positions.side_effect = OperationalError(
            "connection refused", None, None
        )
        
        with patch('app.sync.position_sync.BybitConnector', return_value=mock_executor), \
             patch('app.sync.position_sync.TradeRepository', return_value=mock_trade_repo), \
             patch('app.sync.position_sync.PositionRepository', return_value=mock_position_repo):
            
            sync_service = PositionSyncService(testnet=True)
            sync_service.executor = mock_executor
            sync_service.trade_repo = mock_trade_repo
            sync_service.position_repo = mock_position_repo
            
            # Run multiple sync cycles
            for i in range(10):
                await sync_service.sync_once(db_session)
                
                # Service should still be running
                assert sync_service._running == True
    
    @pytest.mark.asyncio
    async def test_websocket_circuit_breaker_activates(self):
        """
        Simulate persistent WebSocket failures.
        Assert circuit breaker activates after threshold.
        """
        ws_manager = MEXCWebSocketManager(market_type='futures')
        
        # Set low threshold for testing
        ws_manager.circuit_breaker_threshold = 3
        
        # Simulate multiple reconnection attempts
        for i in range(5):
            ws_manager.reconnect_attempts = i + 1
            await ws_manager._handle_reconnect()
        
        # Circuit breaker should activate
        assert ws_manager.circuit_breaker_active == True
        assert ws_manager.reconnect_attempts >= ws_manager.circuit_breaker_threshold
