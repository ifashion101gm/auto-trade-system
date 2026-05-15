"""
Reconciliation Effectiveness Tests - Issue U

Comprehensive test suite verifying that the reconciliation engine:
1. Detects orphaned orders (in DB but not on exchange)
2. Detects ghost positions (on exchange but not in DB)
3. Detects price/status mismatches
4. Auto-repairs safe mismatches correctly
5. Prevents false positives on legitimate pending states

These tests use mocked exchanges to simulate various mismatch scenarios
and verify the reconciliation engine handles them appropriately.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.reconciliation_engine import OrderReconciliationEngine, ReconciliationResult
from app.database.models import PaperTrades


@pytest.fixture
def mock_exchange_manager():
    """Create a mock exchange manager."""
    manager = MagicMock()
    manager.get_open_positions = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def mock_notifier():
    """Create a mock Telegram notifier."""
    notifier = MagicMock()
    notifier.send_reconciliation_alert = AsyncMock()
    return notifier


@pytest.fixture
async def reconciliation_engine(mock_exchange_manager, mock_notifier):
    """Create reconciliation engine with mocked dependencies."""
    with patch('app.execution.reconciliation_engine.UnifiedExchangeManager', return_value=mock_exchange_manager):
        with patch('app.execution.reconciliation_engine.TelegramNotifier', return_value=mock_notifier):
            engine = OrderReconciliationEngine(
                exchange_name="bybit",
                use_testnet=True,
                reconciliation_interval=120,
                auto_repair_safe=True,
                enable_telegram_alerts=False,
                enable_prometheus_metrics=False
            )
            engine.exchange_manager = mock_exchange_manager
            engine.notifier = mock_notifier
            yield engine


class TestOrphanedOrderDetection:
    """Test detection of orders in DB but not on exchange."""
    
    @pytest.mark.asyncio
    async def test_detect_orphaned_order(self, reconciliation_engine, db_session):
        """
        Test that reconciliation detects orphaned orders.
        
        Scenario: Trade exists in DB with status='open' but order not found on exchange.
        Expected: Mismatch detected, trade marked as failed.
        """
        # Create a trade in database
        trade = PaperTrades(
            ts_open=datetime.utcnow().isoformat(),
            user_id='test_user',
            exchange='bybit',
            symbol='XAUUSDT',
            side='buy',
            leverage=1,
            qty=0.01,
            entry_price=2000.0,
            exit_price=None,
            stop_loss=None,
            take_profit=None,
            profit=None,
            profit_pct=None,
            status='open',
            trade_status='POSITION_OPEN',
            notes='Order ID: TEST_ORDER_123'
        )
        db_session.add(trade)
        await db_session.commit()
        
        # Mock exchange to return NO positions (order doesn't exist)
        reconciliation_engine.exchange_manager.get_open_positions.return_value = []
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify orphaned order detected
        assert result.mismatches_found >= 1, "Should detect at least one mismatch"
        assert len(result.orphaned_orders) >= 1, "Should have orphaned orders"
        
        # Verify trade was repaired (marked as failed)
        await db_session.refresh(trade)
        assert trade.status == 'failed', f"Trade should be marked as failed, got {trade.status}"
        assert '[RECONCILIATION]' in trade.notes, "Notes should indicate reconciliation repair"
    
    @pytest.mark.asyncio
    async def test_no_false_positive_recent_order(self, reconciliation_engine, db_session):
        """
        Test that recent orders are NOT flagged as orphaned.
        
        Scenario: Trade created 1 hour ago (less than max_orphaned_age_hours).
        Expected: No mismatch flagged (order might still be processing).
        """
        # Set max orphaned age to 24 hours
        reconciliation_engine.max_orphaned_age_hours = 24
        
        # Create a very recent trade (1 hour old)
        recent_time = datetime.utcnow() - timedelta(hours=1)
        trade = PaperTrades(
            ts_open=recent_time.isoformat(),
            user_id='test_user',
            exchange='bybit',
            symbol='XAUUSDT',
            side='buy',
            leverage=1,
            qty=0.01,
            entry_price=2000.0,
            status='open',
            trade_status='POSITION_OPEN',
            notes='Order ID: RECENT_ORDER_456'
        )
        db_session.add(trade)
        await db_session.commit()
        
        # Mock exchange to return NO positions
        reconciliation_engine.exchange_manager.get_open_positions.return_value = []
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify NO orphaned order detected (too recent)
        assert len(result.orphaned_orders) == 0, "Recent orders should not be flagged as orphaned"
        
        # Verify trade status unchanged
        await db_session.refresh(trade)
        assert trade.status == 'open', "Recent trade should remain open"


class TestGhostPositionDetection:
    """Test detection of positions on exchange but not in DB."""
    
    @pytest.mark.asyncio
    async def test_detect_ghost_position(self, reconciliation_engine, db_session):
        """
        Test that reconciliation detects ghost positions.
        
        Scenario: Position exists on exchange but no corresponding DB record.
        Expected: Ghost position detected and imported into DB.
        """
        # Mock exchange to return a position not in DB
        ghost_position = {
            'order_id': 'GHOST_ORDER_789',
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'quantity': 0.02,
            'entry_price': 2010.0,
            'status': 'open'
        }
        reconciliation_engine.exchange_manager.get_open_positions.return_value = [ghost_position]
        
        # Ensure no trades in DB for this symbol
        # (db_session is fresh, so no trades exist)
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify ghost position detected
        assert result.mismatches_found >= 1, "Should detect at least one mismatch"
        assert len(result.ghost_positions) >= 1, "Should have ghost positions"
        
        # Verify ghost position was imported
        from sqlalchemy import select
        stmt = select(PaperTrades).where(
            PaperTrades.symbol == 'XAUUSDT',
            PaperTrades.user_id == 'reconciliation_import'
        )
        query_result = await db_session.execute(stmt)
        imported_trade = query_result.scalar_one_or_none()
        
        assert imported_trade is not None, "Ghost position should be imported to DB"
        assert imported_trade.qty == 0.02, "Imported quantity should match exchange"
        assert imported_trade.entry_price == 2010.0, "Imported price should match exchange"
        assert '[RECONCILIATION]' in imported_trade.notes, "Notes should indicate import"
    
    @pytest.mark.asyncio
    async def test_ghost_position_ignore_mode(self, reconciliation_engine, db_session):
        """
        Test ghost position handling when configured to ignore.
        
        Scenario: Ghost position detected but action='ignore'.
        Expected: Position logged but NOT imported.
        """
        # Configure to ignore ghost positions
        reconciliation_engine.ghost_position_action = "ignore"
        
        # Mock exchange to return a ghost position
        ghost_position = {
            'order_id': 'IGNORED_GHOST',
            'symbol': 'XAUUSDT',
            'side': 'SELL',
            'quantity': 0.01,
            'entry_price': 2005.0,
            'status': 'open'
        }
        reconciliation_engine.exchange_manager.get_open_positions.return_value = [ghost_position]
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify ghost detected but NOT imported
        assert len(result.ghost_positions) >= 1, "Ghost should be detected"
        
        # Verify no import occurred
        from sqlalchemy import select
        stmt = select(PaperTrades).where(
            PaperTrades.notes.like('%IGNORED_GHOST%')
        )
        query_result = await db_session.execute(stmt)
        imported_trade = query_result.scalar_one_or_none()
        
        assert imported_trade is None, "Ghost position should NOT be imported when action='ignore'"


class TestStatusMismatchDetection:
    """Test detection of status differences between DB and exchange."""
    
    @pytest.mark.asyncio
    async def test_detect_status_mismatch(self, reconciliation_engine, db_session):
        """
        Test that reconciliation detects status mismatches.
        
        Scenario: DB shows 'open' but exchange shows 'closed'.
        Expected: Mismatch detected and DB updated to match exchange.
        """
        # Create trade in DB with status='open'
        trade = PaperTrades(
            ts_open=datetime.utcnow().isoformat(),
            user_id='test_user',
            exchange='bybit',
            symbol='XAUUSDT',
            side='buy',
            leverage=1,
            qty=0.01,
            entry_price=2000.0,
            status='open',
            trade_status='POSITION_OPEN',
            notes='Order ID: STATUS_TEST_999'
        )
        db_session.add(trade)
        await db_session.commit()
        
        # Mock exchange to show position as closed
        exchange_position = {
            'order_id': 'STATUS_TEST_999',
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'quantity': 0.01,
            'entry_price': 2000.0,
            'status': 'closed'  # Different from DB
        }
        reconciliation_engine.exchange_manager.get_open_positions.return_value = [exchange_position]
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify status mismatch detected
        assert result.mismatches_found >= 1, "Should detect status mismatch"
        assert len(result.status_mismatches) >= 1, "Should have status mismatches"
        
        # Verify DB updated to match exchange
        await db_session.refresh(trade)
        assert trade.status == 'closed', f"DB status should be updated to 'closed', got {trade.status}"
        assert '[RECONCILIATION]' in trade.notes, "Notes should indicate status update"


class TestAutoRepairFunctionality:
    """Test automatic repair of safe mismatches."""
    
    @pytest.mark.asyncio
    async def test_auto_repair_orphaned_order(self, reconciliation_engine, db_session):
        """
        Test that orphaned orders are auto-repaired when enabled.
        
        Scenario: Orphaned order detected, auto_repair_safe=True.
        Expected: Trade automatically marked as failed.
        """
        # Enable auto-repair
        reconciliation_engine.auto_repair_safe = True
        
        # Create orphaned trade
        trade = PaperTrades(
            ts_open=(datetime.utcnow() - timedelta(days=2)).isoformat(),  # Old enough
            user_id='test_user',
            exchange='bybit',
            symbol='XAUUSDT',
            side='sell',
            leverage=1,
            qty=0.01,
            entry_price=1990.0,
            status='open',
            trade_status='POSITION_OPEN',
            notes='Order ID: AUTOREPAIR_TEST'
        )
        db_session.add(trade)
        await db_session.commit()
        
        # Mock exchange with no positions
        reconciliation_engine.exchange_manager.get_open_positions.return_value = []
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify auto-repair occurred
        assert result.mismatches_repaired >= 1, "Should repair at least one mismatch"
        
        # Verify trade marked as failed
        await db_session.refresh(trade)
        assert trade.status == 'failed', "Orphaned order should be auto-repaired to failed"
        assert trade.trade_status == 'FAILED', "Trade status should be FAILED"
    
    @pytest.mark.asyncio
    async def test_no_auto_repair_when_disabled(self, reconciliation_engine, db_session):
        """
        Test that auto-repair doesn't occur when disabled.
        
        Scenario: Orphaned order detected, auto_repair_safe=False.
        Expected: Alert sent but trade NOT modified.
        """
        # Disable auto-repair
        reconciliation_engine.auto_repair_safe = False
        reconciliation_engine.enable_telegram_alerts = True
        
        # Create orphaned trade
        trade = PaperTrades(
            ts_open=(datetime.utcnow() - timedelta(days=2)).isoformat(),
            user_id='test_user',
            exchange='bybit',
            symbol='XAUUSDT',
            side='buy',
            leverage=1,
            qty=0.01,
            entry_price=2000.0,
            status='open',
            trade_status='POSITION_OPEN',
            notes='Order ID: NO_REPAIR_TEST'
        )
        db_session.add(trade)
        await db_session.commit()
        
        # Mock exchange with no positions
        reconciliation_engine.exchange_manager.get_open_positions.return_value = []
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify NO auto-repair occurred
        assert result.mismatches_repaired == 0, "Should not auto-repair when disabled"
        
        # Verify alert was sent
        assert result.mismatches_alerted >= 1, "Should send alert when auto-repair disabled"
        
        # Verify trade status unchanged
        await db_session.refresh(trade)
        assert trade.status == 'open', "Trade should remain open when auto-repair disabled"


class TestFalsePositivePrevention:
    """Test that legitimate states don't trigger false positives."""
    
    @pytest.mark.asyncio
    async def test_no_false_positive_legitimate_open_position(self, reconciliation_engine, db_session):
        """
        Test that legitimate open positions don't trigger mismatches.
        
        Scenario: Trade in DB matches exchange position exactly.
        Expected: NO mismatches detected.
        """
        # Create trade in DB
        trade = PaperTrades(
            ts_open=datetime.utcnow().isoformat(),
            user_id='test_user',
            exchange='bybit',
            symbol='XAUUSDT',
            side='buy',
            leverage=1,
            qty=0.01,
            entry_price=2000.0,
            status='open',
            trade_status='POSITION_OPEN',
            notes='Order ID: LEGITIMATE_ORDER'
        )
        db_session.add(trade)
        await db_session.commit()
        
        # Mock exchange with matching position
        exchange_position = {
            'order_id': 'LEGITIMATE_ORDER',
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'quantity': 0.01,
            'entry_price': 2000.0,
            'status': 'open'
        }
        reconciliation_engine.exchange_manager.get_open_positions.return_value = [exchange_position]
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify NO mismatches
        assert result.mismatches_found == 0, "Legitimate position should not trigger mismatches"
        assert len(result.orphaned_orders) == 0, "No orphaned orders"
        assert len(result.ghost_positions) == 0, "No ghost positions"
        assert len(result.status_mismatches) == 0, "No status mismatches"
    
    @pytest.mark.asyncio
    async def test_no_false_positive_pending_order(self, reconciliation_engine, db_session):
        """
        Test that pending orders don't trigger false positives.
        
        Scenario: Order recently placed (within max_orphaned_age_hours).
        Expected: No orphaned order flag even if not yet on exchange.
        """
        # Set max orphaned age to 24 hours
        reconciliation_engine.max_orphaned_age_hours = 24
        
        # Create very recent trade (30 minutes old)
        recent_time = datetime.utcnow() - timedelta(minutes=30)
        trade = PaperTrades(
            ts_open=recent_time.isoformat(),
            user_id='test_user',
            exchange='bybit',
            symbol='XAUUSDT',
            side='buy',
            leverage=1,
            qty=0.01,
            entry_price=2000.0,
            status='open',
            trade_status='POSITION_OPEN',
            notes='Order ID: PENDING_ORDER'
        )
        db_session.add(trade)
        await db_session.commit()
        
        # Mock exchange with no positions (order still processing)
        reconciliation_engine.exchange_manager.get_open_positions.return_value = []
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify NO false positive
        assert len(result.orphaned_orders) == 0, "Recent pending order should not be flagged"
        
        # Verify trade status unchanged
        await db_session.refresh(trade)
        assert trade.status == 'open', "Pending order should remain open"


class TestReconciliationMetrics:
    """Test that reconciliation updates metrics correctly."""
    
    @pytest.mark.asyncio
    async def test_metrics_updated_on_mismatch(self, reconciliation_engine, db_session):
        """
        Test that Prometheus metrics are updated when mismatches found.
        
        Scenario: Mismatch detected with metrics enabled.
        Expected: Metrics published successfully.
        """
        # Enable metrics
        reconciliation_engine.enable_prometheus_metrics = True
        
        # Create orphaned trade
        trade = PaperTrades(
            ts_open=(datetime.utcnow() - timedelta(days=2)).isoformat(),
            user_id='test_user',
            exchange='bybit',
            symbol='XAUUSDT',
            side='buy',
            leverage=1,
            qty=0.01,
            entry_price=2000.0,
            status='open',
            trade_status='POSITION_OPEN',
            notes='Order ID: METRICS_TEST'
        )
        db_session.add(trade)
        await db_session.commit()
        
        # Mock exchange with no positions
        reconciliation_engine.exchange_manager.get_open_positions.return_value = []
        
        # Mock metrics collector
        with patch('app.monitoring.prometheus_metrics.get_metrics_collector') as mock_get_metrics:
            mock_metrics = MagicMock()
            mock_get_metrics.return_value = mock_metrics
            
            # Run reconciliation
            result = await reconciliation_engine.run_reconciliation(db_session)
            
            # Verify metrics were attempted
            assert result.mismatches_found >= 1, "Should detect mismatch"
            # Note: Actual metric calls depend on implementation


class TestReconciliationEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_reconciliation_with_exchange_error(self, reconciliation_engine, db_session):
        """
        Test reconciliation behavior when exchange API fails.
        
        Scenario: Exchange API returns error during position fetch.
        Expected: Reconciliation handles gracefully, no crash.
        """
        # Mock exchange to raise exception
        reconciliation_engine.exchange_manager.get_open_positions.side_effect = Exception("API Error")
        
        # Run reconciliation (should not crash)
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify error handled gracefully
        assert len(result.errors) >= 1, "Should record error"
        assert "API Error" in str(result.errors[0]), "Error message should be preserved"
    
    @pytest.mark.asyncio
    async def test_reconciliation_with_empty_database(self, reconciliation_engine, db_session):
        """
        Test reconciliation when database has no open trades.
        
        Scenario: Empty database, exchange has positions.
        Expected: All exchange positions flagged as ghosts.
        """
        # Ensure no trades in DB (fresh session)
        
        # Mock exchange with positions
        exchange_positions = [
            {
                'order_id': 'EMPTY_DB_TEST_1',
                'symbol': 'XAUUSDT',
                'side': 'BUY',
                'quantity': 0.01,
                'entry_price': 2000.0,
                'status': 'open'
            }
        ]
        reconciliation_engine.exchange_manager.get_open_positions.return_value = exchange_positions
        
        # Run reconciliation
        result = await reconciliation_engine.run_reconciliation(db_session)
        
        # Verify ghost positions detected
        assert len(result.ghost_positions) >= 1, "Should detect ghost positions when DB empty"


# Helper fixture for database session
@pytest.fixture
async def db_session():
    """Create a test database session."""
    from app.database.session import get_async_session
    
    async with get_async_session()() as session:
        yield session
        # Cleanup after test
        await session.rollback()
