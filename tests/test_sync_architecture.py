"""
Integration tests for single source of truth architecture.
Tests WebSocket sync, reconciliation, and event flow.
"""
import pytest
pytest.importorskip("pytest_asyncio")
pytest.importorskip("sqlalchemy")
import asyncio
from app.sync.sync_agent import SyncAgent
from app.services.reconciliation_service import ReconciliationService
from app.database.connection import engine
from app.database.repositories import TradeRepository, PositionRepository
from app.events.event_bus import event_bus
from app.events.event_types import POSITION_UPDATED, ORDER_FILLED
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_position_repository_upsert():
    """Test position upsert functionality."""
    # Create a new session for this test
    async with AsyncSession(engine) as db_session:
        repo = PositionRepository()
        
        try:
            # Test creating a new position
            await repo.upsert_position({
                'symbol': 'XAUT/USDT',
                'size': 0.5,
                'entry_price': 3350.0,
                'current_price': 3355.0,
                'unrealized_pnl': 2.5,
                'leverage': 5,
                'status': 'open',
                'sync_source': 'test'
            }, db_session)
            
            # Verify position was created
            position = await repo.get_position_by_symbol('XAUT/USDT', db_session)
            assert position is not None
            assert position.size == 0.5
            assert position.sync_source == 'test'
            
            # Test updating existing position
            await repo.upsert_position({
                'symbol': 'XAUT/USDT',
                'size': 0.6,
                'entry_price': 3350.0,
                'current_price': 3360.0,
                'unrealized_pnl': 6.0,
                'leverage': 5,
                'status': 'open',
                'sync_source': 'websocket'
            }, db_session)
            
            # Verify position was updated
            position = await repo.get_position_by_symbol('XAUT/USDT', db_session)
            assert position.size == 0.6
            assert position.sync_source == 'websocket'
            
        finally:
            await db_session.close()


@pytest.mark.asyncio
async def test_trade_repository_lifecycle():
    """Test complete trade lifecycle through repository."""
    async with AsyncSession(engine) as db_session:
        repo = TradeRepository()
        
        try:
            # Create a trade
            trade_data = {
                'mode': 'DEMO',
                'exchange': 'mexc',
                'symbol': 'XAUT/USDT',
                'side': 'LONG',
                'status': 'PENDING',
                'entry_price': 3350.0,
                'leverage': 5,
                'quantity': 0.5,
                'strategy_name': 'London Breakout'
            }
            
            trade = await repo.create_trade(trade_data, db_session)
            assert trade is not None
            assert trade.status == 'PENDING'
            
            # Update status to OPEN
            await repo.update_trade_status(trade.id, 'OPEN', db_session)
            trade = await repo.get_trade(trade.id, db_session)
            assert trade.status == 'OPEN'
            
            # Add order event
            await repo.add_order_event(
                trade_id=trade.id,
                event_type='ORDER_FILLED',
                payload={'price': 3350.0, 'quantity': 0.5},
                db_session=db_session
            )
            
            # Close trade
            await repo.close_trade(trade.id, 3360.0, 5.0, db_session)
            trade = await repo.get_trade(trade.id, db_session)
            assert trade.status == 'CLOSED'
            assert trade.exit_price == 3360.0
            assert trade.pnl == 5.0
            
        finally:
            await db_session.close()


@pytest.mark.asyncio
async def test_reconciliation_service():
    """Test reconciliation service execution."""
    recon_service = ReconciliationService()
    
    async with AsyncSession(engine) as db_session:
        try:
            # This will run reconciliation (may find no mismatches if system is synced)
            await recon_service.reconcile(mode='DEMO', db_session=db_session)
            
            # If we got here without exceptions, the service is working
            assert True
        finally:
            await db_session.close()


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    """Test event bus publish and subscribe mechanism."""
    received_events = []
    
    async def handler(event):
        received_events.append(event)
    
    # Subscribe to event
    event_bus.subscribe(POSITION_UPDATED, handler)
    
    # Publish event
    await event_bus.publish(POSITION_UPDATED, {
        'symbol': 'XAUT/USDT',
        'size': 0.5,
        'price': 3350.0
    })
    
    # Give async handlers time to execute
    await asyncio.sleep(0.1)
    
    # Verify event was received
    assert len(received_events) > 0
    assert received_events[0]['payload']['symbol'] == 'XAUT/USDT'


@pytest.mark.asyncio
async def test_sync_agent_initialization():
    """Test that sync agent initializes correctly."""
    sync_agent = SyncAgent()
    
    assert sync_agent.websocket_manager is not None
    assert sync_agent.trade_repo is not None
    assert sync_agent.position_repo is not None
    assert sync_agent.running == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
