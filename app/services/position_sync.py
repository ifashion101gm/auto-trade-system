"""
Position Synchronization Service.
Continuously syncs exchange positions with database state.
Prevents ghost trades, duplicated positions, and close failures.

This runs every 5 seconds to ensure DB matches exchange reality.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.exchange.mexc_executor import MexcExecutor
from app.storage.repository import TradeRepository, PositionRepository
from app.events.event_bus import event_bus
from app.events.event_types import SYNC_MISMATCH, SYNC_REPAIRED
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class PositionSyncService:
    """
    Enterprise-grade position synchronization.
    
    Continuously monitors:
    - Open positions on exchange
    - Database trade records
    - Position state consistency
    
    Auto-repairs mismatches and alerts via Telegram.
    """
    
    def __init__(self, testnet: bool = False):
        """
        Initialize position sync service.
        
        Args:
            testnet: Sync from testnet or live exchange
        """
        self.executor = MexcExecutor(testnet=testnet)
        self.trade_repo = TradeRepository()
        self.position_repo = PositionRepository()
        self.testnet = testnet
        self._running = False
        self._sync_interval = 5  # seconds
    
    async def start(self, db_session_factory):
        """
        Start continuous position synchronization.
        
        Args:
            db_session_factory: Async session factory for database access
        """
        self._running = True
        logger.info(f"🔄 Position sync started (interval={self._sync_interval}s, testnet={self.testnet})")
        
        while self._running:
            try:
                async with db_session_factory() as db_session:
                    await self.sync_once(db_session)
                
                await asyncio.sleep(self._sync_interval)
                
            except Exception as e:
                logger.error(f"❌ Position sync error: {e}")
                await asyncio.sleep(self._sync_interval)
    
    def stop(self):
        """Stop position synchronization."""
        self._running = False
        logger.info("🛑 Position sync stopped")
    
    async def sync_once(self, db_session: AsyncSession):
        """
        Perform one synchronization cycle.
        
        Steps:
        1. Fetch all open positions from exchange
        2. Fetch all open trades from database
        3. Compare and detect mismatches
        4. Repair any inconsistencies
        """
        logger.debug("🔄 Running position sync cycle...")
        
        # Step 1: Get exchange positions
        try:
            exchange_positions = await self.executor.get_open_positions()
            exchange_symbols = {pos['symbol'] for pos in exchange_positions}
            logger.debug(f"Exchange positions: {len(exchange_positions)} ({exchange_symbols})")
        except Exception as e:
            logger.error(f"Failed to fetch exchange positions: {e}")
            return
        
        # Step 2: Get database positions
        try:
            db_positions = await self.position_repo.get_open_positions(db_session)
            db_symbols = {pos.symbol for pos in db_positions}
            logger.debug(f"Database positions: {len(db_positions)} ({db_symbols})")
        except Exception as e:
            logger.error(f"Failed to fetch database positions: {e}")
            return
        
        # Step 3: Detect mismatches
        mismatches = []
        
        # Case A: Position on exchange but not in DB
        missing_in_db = exchange_symbols - db_symbols
        for symbol in missing_in_db:
            mismatches.append({
                'type': 'missing_in_db',
                'symbol': symbol,
                'severity': 'HIGH'
            })
            await self._repair_missing_in_db(symbol, exchange_positions, db_session)
        
        # Case B: Position in DB but not on exchange (ghost position)
        missing_in_exchange = db_symbols - exchange_symbols
        for symbol in missing_in_exchange:
            mismatches.append({
                'type': 'ghost_position',
                'symbol': symbol,
                'severity': 'CRITICAL'
            })
            await self._repair_ghost_position(symbol, db_session)
        
        # Case C: Size/price mismatches
        for ex_pos in exchange_positions:
            symbol = ex_pos['symbol']
            db_pos = next((p for p in db_positions if p.symbol == symbol), None)
            
            if db_pos:
                size_diff = abs(ex_pos.get('size', 0) - db_pos.size)
                price_diff = abs(ex_pos.get('mark_price', 0) - db_pos.current_price)
                
                # Threshold: 0.1% size difference or $0.01 price difference
                size_threshold = max(0.001, db_pos.size * 0.001)
                price_threshold = 0.01
                
                if size_diff > size_threshold or price_diff > price_threshold:
                    mismatches.append({
                        'type': 'data_mismatch',
                        'symbol': symbol,
                        'severity': 'MEDIUM',
                        'details': {
                            'size_diff': size_diff,
                            'price_diff': price_diff
                        }
                    })
                    await self._repair_data_mismatch(symbol, ex_pos, db_pos, db_session)
        
        # Step 4: Verify trade-position consistency
        await self._verify_trade_position_consistency(db_session)
        
        # Step 5: Report results
        if mismatches:
            logger.warning(f"⚠️  Sync found {len(mismatches)} mismatches:")
            for m in mismatches:
                logger.warning(f"   - {m['type']}: {m['symbol']} ({m['severity']})")
            
            # Send alert for critical mismatches
            critical = [m for m in mismatches if m['severity'] == 'CRITICAL']
            if critical:
                await event_bus.publish(SYNC_MISMATCH, {
                    'type': 'position_sync',
                    'mismatches': mismatches,
                    'testnet': self.testnet
                }, priority=5)
        else:
            logger.debug("✅ Position sync: All consistent")
    
    async def _repair_missing_in_db(
        self,
        symbol: str,
        exchange_positions: List[Dict],
        db_session: AsyncSession
    ):
        """Recreate missing position record in database."""
        logger.warning(f"🔧 Repairing missing DB position: {symbol}")
        
        ex_pos = next(p for p in exchange_positions if p['symbol'] == symbol)
        
        # Try to find associated trade
        trade = await self.trade_repo.get_open_trade_by_symbol(symbol, db_session)
        
        if trade:
            # Create position record
            await self.position_repo.upsert_position({
                'trade_id': trade.id,
                'symbol': symbol,
                'size': ex_pos.get('size', 0),
                'entry_price': ex_pos.get('entry_price', 0),
                'current_price': ex_pos.get('mark_price', 0),
                'unrealized_pnl': ex_pos.get('unrealized_pnl', 0),
                'liquidation_price': ex_pos.get('liquidation_price'),
                'leverage': ex_pos.get('leverage', 1),
                'status': 'open',
                'last_sync': datetime.utcnow(),
                'sync_source': 'position_sync'
            }, db_session)
            
            await event_bus.publish(SYNC_REPAIRED, {
                'action': 'recreated_position',
                'symbol': symbol,
                'testnet': self.testnet
            })
            
            logger.info(f"✅ Recreated position for {symbol}")
        else:
            logger.error(f"❌ No trade found for orphaned position: {symbol}")
            # This is a serious issue - position exists but no trade record
            await event_bus.publish(SYNC_MISMATCH, {
                'type': 'orphaned_position',
                'symbol': symbol,
                'position_data': ex_pos,
                'testnet': self.testnet
            }, priority=5)
    
    async def _repair_ghost_position(self, symbol: str, db_session: AsyncSession):
        """Mark ghost position as closed in database."""
        logger.warning(f"🔧 Repairing ghost position: {symbol}")
        
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
                    trade.error_message = 'Ghost position detected and closed during sync'
                    
                    logger.warning(f"⚠️  Closed ghost trade: {trade.id}")
            
            await db_session.commit()
            
            await event_bus.publish(SYNC_REPAIRED, {
                'action': 'closed_ghost_position',
                'symbol': symbol,
                'testnet': self.testnet
            })
    
    async def _repair_data_mismatch(
        self,
        symbol: str,
        ex_pos: Dict,
        db_pos,
        db_session: AsyncSession
    ):
        """Update database position to match exchange."""
        logger.debug(f"🔧 Repairing data mismatch: {symbol}")
        
        old_size = db_pos.size
        old_price = db_pos.current_price
        
        db_pos.size = ex_pos.get('size', 0)
        db_pos.current_price = ex_pos.get('mark_price', 0)
        db_pos.unrealized_pnl = ex_pos.get('unrealized_pnl', 0)
        db_pos.last_sync = datetime.utcnow()
        db_pos.sync_source = 'position_sync'
        
        await db_session.commit()
        
        logger.debug(
            f"Updated {symbol}: "
            f"size {old_size}→{db_pos.size}, "
            f"price {old_price}→{db_pos.current_price}"
        )
        
        await event_bus.publish(SYNC_REPAIRED, {
            'action': 'updated_position_data',
            'symbol': symbol,
            'changes': {
                'size': {'old': old_size, 'new': db_pos.size},
                'price': {'old': old_price, 'new': db_pos.current_price}
            },
            'testnet': self.testnet
        })
    
    async def _verify_trade_position_consistency(self, db_session: AsyncSession):
        """Verify all open trades have corresponding positions."""
        open_trades = await self.trade_repo.get_open_trades(db_session)
        open_positions = await self.position_repo.get_open_positions(db_session)
        
        trade_symbols = {t.symbol for t in open_trades}
        position_symbols = {p.symbol for p in open_positions}
        
        # Trades without positions (partially filled or sync issue)
        missing_positions = trade_symbols - position_symbols
        for symbol in missing_positions:
            logger.warning(f"⚠️  Trade without position: {symbol}")
            # This could indicate:
            # - Partially filled order
            # - Position closed but trade not updated
            # - Sync delay
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status for monitoring."""
        try:
            positions = await self.executor.get_open_positions()
            balance = await self.executor.get_balance()
            
            return {
                'status': 'healthy',
                'exchange_positions': len(positions),
                'balance_usdt': balance.get('total_usdt', 0),
                'testnet': self.testnet,
                'last_sync': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'testnet': self.testnet
            }
    
    async def close(self):
        """Close executor connection."""
        await self.executor.close()
