"""
Sync Agent - Central state engine that listens to MEXC WebSocket
and maintains database as single source of truth.

Responsibilities:
- Listen to MEXC WebSocket for real-time updates
- Sync exchange state to database
- Detect mismatches and trigger reconciliation
- Handle reconnections gracefully
- Handle partial fills and orphaned orders
"""
import asyncio
from app.websocket.manager import MEXCWebSocketManager
from app.database.repositories import TradeRepository, PositionRepository
from app.events.event_bus import event_bus
from app.events.event_types import (
    SYNC_RECEIVED, POSITION_UPDATED, ORDER_FILLED, 
    ORDER_PARTIALLY_FILLED, SYNC_MISMATCH
)
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
        event_bus.subscribe(ORDER_PARTIALLY_FILLED, self._on_order_partially_filled)
    
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
        """
        Handle order fill event with partial fill support.
        
        Detects:
        - Full fills: Update trade status to OPEN
        - Partial fills: Update filled_quantity, keep status as OPEN
        - Orphaned orders: Log warning if trade not found
        """
        if not db_session:
            return
        
        payload = event['payload']
        
        try:
            # Check for partial fill
            filled_qty = payload.get('filled_quantity', payload.get('quantity', 0))
            total_qty = payload.get('total_quantity', filled_qty)
            
            # Find trade by order ID
            trade = await self.trade_repo.get_trade_by_order_id(
                payload['order_id'], 
                db_session
            )
            
            if trade:
                if filled_qty < total_qty:
                    # Partial fill - update but keep status as OPEN
                    logger.info(
                        f"⚠️  Partial fill detected: {payload['order_id']} "
                        f"({filled_qty}/{total_qty})"
                    )
                    
                    # Update trade with partial fill info
                    await self.trade_repo.update_trade_partial_fill(
                        trade_id=trade.id,
                        filled_quantity=filled_qty,
                        db_session=db_session
                    )
                    
                    # Publish partial fill event
                    await event_bus.publish(ORDER_PARTIALLY_FILLED, {
                        'order_id': payload['order_id'],
                        'trade_id': trade.id,
                        'filled_quantity': filled_qty,
                        'total_quantity': total_qty,
                        'fill_pct': round((filled_qty / total_qty) * 100, 2)
                    }, priority=3)
                else:
                    # Full fill - mark as OPEN
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
                    
                    # Publish full fill event
                    await event_bus.publish(ORDER_FILLED, {
                        'order_id': payload['order_id'],
                        'trade_id': trade.id,
                        'symbol': trade.symbol,
                        'filled_quantity': filled_qty
                    }, priority=2)
            else:
                # Orphaned order - not in our database
                logger.warning(
                    f"⚠️  Orphaned order detected: {payload['order_id']} "
                    f"(not in database)"
                )
                
                # Publish mismatch event
                await event_bus.publish(SYNC_MISMATCH, {
                    'type': 'orphaned_order',
                    'order_id': payload['order_id'],
                    'details': 'Order exists on exchange but not in database'
                }, priority=5)
            
        except Exception as e:
            logger.error(f"Failed to process order fill: {e}")
    
    async def _periodic_reconciliation(self, db_session_factory):
        """
        Run periodic REST API reconciliation with enhanced checks.
        
        Checks:
        1. Standard reconciliation (DB vs Exchange positions)
        2. Orphaned order detection (trades in DB but not on exchange)
        3. Stale position detection (positions not updated recently)
        """
        while self.running:
            try:
                async for db_session in db_session_factory():
                    from app.services.reconciliation_service import ReconciliationService
                    recon_service = ReconciliationService()
                    
                    # Standard reconciliation
                    await recon_service.reconcile(mode='DEMO', db_session=db_session)
                    await recon_service.reconcile(mode='LIVE', db_session=db_session)
                    
                    # Enhanced: Check for orphaned orders
                    await self._detect_orphaned_orders(db_session)
                    
                    break
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")
            
            await asyncio.sleep(120)  # Every 2 minutes
    
    async def _on_order_partially_filled(self, event, db_session: AsyncSession = None):
        """Handle partial fill event - log and monitor."""
        if not db_session:
            return
        
        payload = event['payload']
        logger.info(
            f"📊 Partial fill progress: {payload.get('fill_pct', 0)}% "
            f"({payload.get('filled_quantity', 0)}/{payload.get('total_quantity', 0)})"
        )
    
    async def _detect_orphaned_orders(self, db_session: AsyncSession):
        """
        Detect trades in database that don't exist on exchange.
        
        This catches:
        - Orders that were cancelled on exchange but not synced
        - Database entries for failed orders
        - Manual exchange interventions
        """
        try:
            from app.infra.exchange_manager import UnifiedExchangeManager
            from app.config import settings
            
            # Get all OPEN/PENDING trades from DB
            open_trades = await self.trade_repo.get_open_trades(db_session)
            
            if not open_trades:
                return
            
            logger.debug(f"Checking {len(open_trades)} open trades for orphaned orders...")
            
            # Initialize exchange manager to fetch orders
            exchange_manager = UnifiedExchangeManager(
                exchange_name=settings.ACTIVE_EXCHANGE,
                use_testnet=settings.BINANCE_TESTNET
            )
            
            # Fetch all open orders from exchange
            exchange_orders = await exchange_manager.fetch_open_orders()
            exchange_order_ids = {order.get('id') or order.get('orderId') for order in exchange_orders}
            
            # Check each trade
            orphaned_count = 0
            for trade in open_trades:
                if not trade.exchange_order_id:
                    continue
                
                if trade.exchange_order_id not in exchange_order_ids:
                    orphaned_count += 1
                    logger.warning(
                        f"⚠️  Orphaned trade detected: {trade.id} "
                        f"(order {trade.exchange_order_id} not on exchange)"
                    )
                    
                    # Mark trade as potentially orphaned
                    trade.status = 'ORPHANED'
                    trade.error_message = (
                        f'Order {trade.exchange_order_id} not found on exchange. '
                        f'Manual verification required.'
                    )
                    
                    # Publish mismatch event
                    await event_bus.publish(SYNC_MISMATCH, {
                        'type': 'orphaned_trade',
                        'trade_id': trade.id,
                        'order_id': trade.exchange_order_id,
                        'symbol': trade.symbol
                    }, priority=5)
            
            if orphaned_count > 0:
                await db_session.commit()
                logger.warning(f"Found {orphaned_count} orphaned trades")
            else:
                logger.debug("✅ No orphaned trades detected")
            
        except Exception as e:
            logger.error(f"Orphaned order detection failed: {e}")
    
    async def stop(self):
        """Stop sync agent."""
        self.running = False
        await self.websocket_manager.disconnect()
        logger.info("🛑 Sync Agent stopped")
