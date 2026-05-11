"""
Sync Agent - Central state engine that listens to MEXC WebSocket
and maintains database as single source of truth.

Responsibilities:
- Listen to MEXC WebSocket for real-time updates
- Sync exchange state to database
- Detect mismatches and trigger reconciliation
- Handle reconnections gracefully
"""
import asyncio
from app.exchange.websocket_manager import MEXCWebSocketManager
from app.storage.repository import TradeRepository, PositionRepository
from app.events.event_bus import event_bus
from app.events.event_types import SYNC_RECEIVED, POSITION_UPDATED, ORDER_FILLED
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SyncAgent:
    """
    Central state engine maintaining database consistency.
    Listens to WebSocket + periodic REST verification.
    
    This is the HEART of the single source of truth architecture.
    """
    
    def __init__(self):
        self.websocket_manager = MEXCWebSocketManager(market_type='futures')
        self.trade_repo = TradeRepository()
        self.position_repo = PositionRepository()
        self.running = False
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """Subscribe to WebSocket events."""
        event_bus.subscribe(SYNC_RECEIVED, self._on_sync_received)
        event_bus.subscribe(POSITION_UPDATED, self._on_position_updated)
        event_bus.subscribe(ORDER_FILLED, self._on_order_filled)
    
    async def start_listening(self, symbols=['XAUT/USDT'], db_session_factory=None):
        """Start sync agent with WebSocket and periodic reconciliation."""
        self.running = True
        logger.info("🔄 Sync Agent: Starting WebSocket listener...")
        
        # Start WebSocket connection in background
        asyncio.create_task(self.websocket_manager.connect())
        
        # Subscribe to symbols
        for symbol in symbols:
            await self.websocket_manager.subscribe('position', symbol)
            await self.websocket_manager.subscribe('order', symbol)
            await self.websocket_manager.subscribe('balance', symbol)
        
        # Start periodic REST verification (every 2 minutes)
        if db_session_factory:
            asyncio.create_task(self._periodic_reconciliation(db_session_factory))
        
        logger.info("✅ Sync Agent started")
    
    async def _on_sync_received(self, event):
        """Handle raw sync data from WebSocket."""
        payload = event['payload']
        logger.debug(f"Sync received: {payload['type']}")
    
    async def _on_position_updated(self, event, db_session: AsyncSession = None):
        """Update position in database from WebSocket event."""
        if not db_session:
            return
        
        payload = event['payload']
        symbol = payload['symbol']
        
        try:
            # Upsert position
            await self.position_repo.upsert_position({
                'symbol': symbol,
                'size': payload['size'],
                'entry_price': payload['entry_price'],
                'current_price': payload['current_price'],
                'unrealized_pnl': payload['unrealized_pnl'],
                'liquidation_price': payload.get('liquidation_price'),
                'last_sync': datetime.utcnow(),
                'sync_source': 'websocket'
            }, db_session)
            
            logger.debug(f"📊 Position synced: {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to sync position: {e}")
    
    async def _on_order_filled(self, event, db_session: AsyncSession = None):
        """Handle order fill event."""
        if not db_session:
            return
        
        payload = event['payload']
        
        try:
            # Find trade by order ID
            trade = await self.trade_repo.get_trade_by_order_id(
                payload['order_id'], 
                db_session
            )
            
            if trade:
                # Update trade status
                await self.trade_repo.update_trade_status(
                    trade.id, 
                    'OPEN', 
                    db_session
                )
                
                # Add order event
                await self.trade_repo.add_order_event(
                    trade_id=trade.id,
                    event_type='ORDER_FILLED',
                    payload=payload,
                    db_session=db_session
                )
                
                logger.info(f"✅ Order filled: {payload['order_id']}")
            else:
                logger.warning(f"Trade not found for order: {payload['order_id']}")
            
        except Exception as e:
            logger.error(f"Failed to process order fill: {e}")
    
    async def _periodic_reconciliation(self, db_session_factory):
        """Run periodic REST API reconciliation."""
        while self.running:
            try:
                async for db_session in db_session_factory():
                    from app.services.reconciliation_service import ReconciliationService
                    recon_service = ReconciliationService()
                    await recon_service.reconcile(mode='DEMO', db_session=db_session)
                    await recon_service.reconcile(mode='LIVE', db_session=db_session)
                    break
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")
            
            await asyncio.sleep(120)  # Every 2 minutes
    
    async def stop(self):
        """Stop sync agent."""
        self.running = False
        await self.websocket_manager.disconnect()
        logger.info("🛑 Sync Agent stopped")
