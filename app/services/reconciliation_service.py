"""
Reconciliation Service - Periodically compares database state with exchange state.
Detects and repairs mismatches. Runs every 2 minutes.

This is a CRITICAL component for maintaining single source of truth.
"""
from app.exchange.exchange_router import ExchangeRouter
from app.database.repositories import TradeRepository, PositionRepository
from app.events.event_bus import event_bus
from app.events.event_types import (
    SYNC_MISMATCH, SYNC_REPAIRED, 
    RECONCILIATION_STARTED, RECONCILIATION_COMPLETED
)
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ReconciliationService:
    """
    Enterprise-grade reconciliation engine.
    Compares DB vs Exchange every 2 minutes.
    Auto-repairs mismatches and sends alerts.
    """
    
    def __init__(self):
        self.router = ExchangeRouter()
        self.trade_repo = TradeRepository()
        self.position_repo = PositionRepository()
    
    async def reconcile(self, mode='DEMO', db_session: AsyncSession = None):
        """Run full reconciliation check."""
        logger.info(f"🔍 Reconciliation: Starting {mode} mode check...")
        
        await event_bus.publish(RECONCILIATION_STARTED, {'mode': mode})
        
        if not db_session:
            return
        
        try:
            # Fetch exchange positions
            exchange = self.router.get_exchange(mode)
            exchange_positions = await exchange.get_positions()
            exchange_symbols = {p['symbol'] for p in exchange_positions}
            
            # Fetch database positions
            db_positions = await self.position_repo.get_open_positions(db_session)
            db_symbols = {p.symbol for p in db_positions}
            
            mismatches_found = 0
            
            # Case 1: Position in exchange but not in DB
            missing_in_db = exchange_symbols - db_symbols
            for symbol in missing_in_db:
                mismatches_found += 1
                logger.warning(f"⚠️  Position in exchange but not in DB: {symbol}")
                await self._repair_missing_in_db(symbol, exchange_positions, mode, db_session)
            
            # Case 2: Position in DB but not in exchange (ghost position)
            missing_in_exchange = db_symbols - exchange_symbols
            for symbol in missing_in_exchange:
                mismatches_found += 1
                logger.warning(f"⚠️  Ghost position in DB: {symbol}")
                await self._repair_ghost_position(symbol, db_session)
            
            # Case 3: Size/price mismatches
            for ex_pos in exchange_positions:
                symbol = ex_pos['symbol']
                db_pos = next((p for p in db_positions if p.symbol == symbol), None)
                
                if db_pos:
                    size_diff = abs(ex_pos.get('size', 0) - db_pos.size)
                    price_diff = abs(ex_pos.get('current_price', 0) - db_pos.current_price)
                    
                    if size_diff > 0.001 or price_diff > 0.01:
                        mismatches_found += 1
                        logger.warning(f"⚠️  Mismatch for {symbol}: size_diff={size_diff}, price_diff={price_diff}")
                        await self._repair_mismatch(symbol, ex_pos, db_pos, db_session)
            
            # Case 4: Verify open trades match positions
            await self._verify_trade_position_consistency(mode, db_session)
            
            # Case 5: Detect orphaned orders (trades in DB but not on exchange)
            await self._detect_orphaned_orders(mode, db_session)
            
            if mismatches_found == 0:
                logger.info("✅ Reconciliation: No mismatches found")
            else:
                logger.info(f"✅ Reconciliation: Repaired {mismatches_found} mismatches")
            
            await event_bus.publish(RECONCILIATION_COMPLETED, {
                'mode': mode,
                'mismatches_found': mismatches_found
            })
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            await event_bus.publish(SYNC_MISMATCH, {
                'error': str(e),
                'mode': mode
            })
    
    async def _repair_missing_in_db(self, symbol, exchange_positions, mode, db_session):
        """Recreate missing position in database."""
        ex_pos = next(p for p in exchange_positions if p['symbol'] == symbol)
        
        # Find associated trade
        trade = await self.trade_repo.get_open_trade_by_symbol(symbol, db_session)
        
        if trade:
            # Create position record
            await self.position_repo.upsert_position({
                'trade_id': trade.id,
                'symbol': symbol,
                'size': ex_pos.get('size', 0),
                'entry_price': ex_pos.get('entry_price', 0),
                'current_price': ex_pos.get('current_price', 0),
                'unrealized_pnl': ex_pos.get('unrealized_pnl', 0),
                'liquidation_price': ex_pos.get('liquidation_price'),
                'leverage': ex_pos.get('leverage', 1),
                'status': 'open',
                'last_sync': datetime.utcnow(),
                'sync_source': 'reconciliation'
            }, db_session)
            
            await event_bus.publish(SYNC_REPAIRED, {
                'action': 'recreated_position',
                'symbol': symbol,
                'mode': mode
            })
        else:
            logger.error(f"No trade found for orphaned position: {symbol}")
    
    async def _repair_ghost_position(self, symbol, db_session):
        """Mark ghost position as closed."""
        position = await self.position_repo.get_position_by_symbol(symbol, db_session)
        
        if position:
            # Close position
            position.status = 'closed'
            position.last_sync = datetime.utcnow()
            
            # Close associated trade
            if position.trade_id:
                trade = await self.trade_repo.get_trade(position.trade_id, db_session)
                if trade and trade.status in ['OPEN', 'PENDING', 'PARTIAL']:
                    trade.status = 'CLOSED'
                    trade.closed_at = datetime.utcnow().isoformat()
                    trade.error_message = 'Ghost position detected and closed during reconciliation'
            
            await db_session.commit()
            
            await event_bus.publish(SYNC_REPAIRED, {
                'action': 'closed_ghost_position',
                'symbol': symbol
            })
    
    async def _repair_mismatch(self, symbol, ex_pos, db_pos, db_session):
        """Update position to match exchange."""
        db_pos.size = ex_pos.get('size', 0)
        db_pos.current_price = ex_pos.get('current_price', 0)
        db_pos.unrealized_pnl = ex_pos.get('unrealized_pnl', 0)
        db_pos.last_sync = datetime.utcnow()
        db_pos.sync_source = 'reconciliation'
        
        await db_session.commit()
        
        await event_bus.publish(SYNC_REPAIRED, {
            'action': 'updated_position',
            'symbol': symbol,
            'changes': {
                'size': ex_pos.get('size', 0),
                'price': ex_pos.get('current_price', 0)
            }
        })
    
    async def _verify_trade_position_consistency(self, mode, db_session):
        """Deep verification of trade-position-order consistency."""
        open_trades = await self.trade_repo.get_open_trades(db_session)
        open_positions = await self.position_repo.get_open_positions(db_session)
        
        # Also fetch open orders
        exchange = self.router.get_exchange(mode)
        try:
            open_orders = await exchange.fetch_open_orders()
            order_symbols = {
                o.get('symbol') for o in open_orders 
                if o.get('status') == 'open'
            }
        except Exception as e:
            logger.warning(f"Could not fetch open orders: {e}")
            order_symbols = set()
        
        trade_symbols = {t.symbol for t in open_trades}
        position_symbols = {p.symbol for p in open_positions}
        
        # Detect inconsistencies
        trades_without_positions = trade_symbols - position_symbols
        positions_without_trades = position_symbols - trade_symbols
        orders_without_trades = order_symbols - trade_symbols
        
        for symbol in trades_without_positions:
            logger.warning(f"⚠️  Trade without position: {symbol} - Possible partial fill")
            # Trigger immediate position sync
            await self._trigger_emergency_sync(symbol, mode, db_session)
        
        for symbol in positions_without_trades:
            logger.warning(f"⚠️  Position without trade: {symbol} - Orphaned position")
        
        for symbol in orders_without_trades:
            logger.warning(f"⚠️  Order without trade record: {symbol}")
    
    async def _detect_orphaned_orders(self, mode, db_session):
        """
        Detect trades that exist in database but not on exchange.
        
        These are typically:
        - Cancelled orders not synced
        - Failed orders still marked as OPEN
        - Manual interventions on exchange
        """
        try:
            from app.infra.exchange_manager import UnifiedExchangeManager
            from app.config import settings
            
            # Get open trades from DB
            open_trades = await self.trade_repo.get_open_trades(db_session)
            
            if not open_trades:
                return
            
            # Fetch open orders from exchange
            exchange_manager = UnifiedExchangeManager(
                exchange_name=settings.ACTIVE_EXCHANGE,
                use_testnet=settings.BINANCE_TESTNET
            )
            
            exchange_orders = await exchange_manager.fetch_open_orders()
            exchange_order_ids = {
                order.get('id') or order.get('orderId') 
                for order in exchange_orders
            }
            
            # Find orphaned trades
            orphaned_trades = [
                trade for trade in open_trades
                if trade.exchange_order_id and trade.exchange_order_id not in exchange_order_ids
            ]
            
            for trade in orphaned_trades:
                logger.warning(
                    f"⚠️  Orphaned trade in reconciliation: {trade.id} "
                    f"(order {trade.exchange_order_id} not found on exchange)"
                )
                
                # Mark as orphaned
                trade.status = 'ORPHANED'
                trade.error_message = (
                    f'Order not found on exchange during reconciliation. '
                    f'May need manual closure.'
                )
                
                # Publish event
                await event_bus.publish(SYNC_MISMATCH, {
                    'type': 'orphaned_trade_reconciliation',
                    'trade_id': trade.id,
                    'order_id': trade.exchange_order_id,
                    'symbol': trade.symbol,
                    'mode': mode
                }, priority=5)
            
            if orphaned_trades:
                await db_session.commit()
                logger.warning(f"Reconciliation found {len(orphaned_trades)} orphaned trades")
        
        except Exception as e:
            logger.error(f"Orphaned order detection in reconciliation failed: {e}")
    
    async def _trigger_emergency_sync(self, symbol: str, mode: str, db_session):
        """Force immediate sync for problematic symbol."""
        logger.info(f"🔄 Triggering emergency sync for {symbol}")
        
        try:
            exchange = self.router.get_exchange(mode)
            positions = await exchange.get_positions()
            
            # Update database immediately
            for pos in positions:
                if pos['symbol'] == symbol:
                    await self.position_repo.upsert_position({
                        **pos,
                        'sync_source': 'emergency_reconciliation'
                    }, db_session)
            
            await event_bus.publish(SYNC_REPAIRED, {
                'action': 'emergency_sync_triggered',
                'symbol': symbol,
                'mode': mode
            })
        except Exception as e:
            logger.error(f"Emergency sync failed for {symbol}: {e}")
