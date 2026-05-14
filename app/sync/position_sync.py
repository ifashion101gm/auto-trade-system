"""
Position Synchronization Service.
Continuously syncs exchange positions with database state.
Prevents ghost trades, duplicated positions, and close failures.

This runs every 5 seconds to ensure DB matches exchange reality.
Also listens to WebSocket reconnection events for immediate sync.

NOTE: Currently configured to use Bybit Demo Trading exclusively.
MEXC integration has been disabled.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.exchange.bybit_connector import BybitConnector
from app.database.repositories import TradeRepository, PositionRepository
from app.events.event_bus import event_bus
from app.events.event_types import SYNC_MISMATCH, SYNC_REPAIRED, WEBSOCKET_RECONNECTED
from app.config import settings
from app.logging_config import get_logger
from app.risk.validator import TradeValidator

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
            testnet: Sync from testnet or live exchange (unused for Bybit demo)
        """
        # Use Bybit Demo Trading connector exclusively
        self.executor = BybitConnector(demo_trading=True)  # Force demo trading mode
        self.trade_repo = TradeRepository()
        self.position_repo = PositionRepository()
        self.testnet = testnet
        self._running = False
        self._sync_interval = 5  # seconds
        
        logger.info("✅ PositionSyncService initialized with Bybit Demo Trading")
        
        # Subscribe to WebSocket reconnection events for immediate sync
        event_bus.subscribe(WEBSOCKET_RECONNECTED, self._on_websocket_reconnected)
    
    async def start(self, db_session_factory):
        """
        Start continuous position synchronization with graceful degradation.
        
        Args:
            db_session_factory: Async session factory for database access
        """
        self._running = True
        logger.info(f"🔄 Position sync started (interval={self._sync_interval}s, testnet={self.testnet})")
        
        consecutive_db_failures = 0
        max_consecutive_failures = 5  # After this many failures, reduce sync frequency
        
        while self._running:
            try:
                # Use a single session for the sync cycle
                async with db_session_factory() as db_session:
                    await self.sync_once(db_session)
                    # Reset failure counter on success
                    consecutive_db_failures = 0
                
                # Normal sync interval
                await asyncio.sleep(self._sync_interval)
                
            except Exception as e:
                error_str = str(e).lower()
                is_db_connection_error = 'errno 111' in error_str or 'connection refused' in error_str or 'database' in error_str
                
                if is_db_connection_error:
                    consecutive_db_failures += 1
                    logger.warning(
                        f"⚠️  Database connection issue during sync (failure {consecutive_db_failures}): {e}"
                    )
                    
                    # Graceful degradation: reduce sync frequency when DB is unavailable
                    if consecutive_db_failures >= max_consecutive_failures:
                        degraded_interval = self._sync_interval * 6  # Sync every 30s instead of 5s
                        logger.warning(
                            f"🔧 Entering degraded mode - reducing sync frequency to {degraded_interval}s "
                            f"due to persistent database issues"
                        )
                        await asyncio.sleep(degraded_interval)
                    else:
                        await asyncio.sleep(self._sync_interval)
                else:
                    # Non-DB errors - log and continue normally
                    logger.error(f"❌ Position sync error: {e}")
                    await asyncio.sleep(self._sync_interval)
    
    def stop(self):
        """Stop position synchronization."""
        self._running = False
        logger.info("🛑 Position sync stopped")
    
    async def _on_websocket_reconnected(self, event):
        """
        Handle WebSocket reconnection by triggering immediate sync.
        
        This ensures we catch any state changes that occurred during disconnection.
        Gracefully handles database connection failures.
        
        Args:
            event: WebSocket reconnection event with metadata
        """
        logger.info(f"🔄 WebSocket reconnected - triggering immediate position sync...")
        
        try:
            # Import db session factory dynamically to avoid circular imports
            from app.database.connection import get_session
            
            async with get_session() as db_session:
                await self.sync_once(db_session)
            
            logger.info("✅ Immediate sync completed after WebSocket reconnect")
        except Exception as e:
            error_str = str(e).lower()
            is_db_error = 'errno 111' in error_str or 'connection refused' in error_str or 'database' in error_str
            
            if is_db_error:
                logger.warning(
                    f"⚠️  Skipping immediate sync after WebSocket reconnect due to DB issue: {e}"
                )
                logger.info("   → Will sync on next scheduled cycle when DB is available")
            else:
                logger.error(f"❌ Failed to sync after WebSocket reconnect: {e}")
    
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
        
        # Step 1: Get exchange positions with error handling
        try:
            exchange_positions = await self.executor.get_positions()
            
            # Validate position data before processing
            validated_positions = []
            for pos in exchange_positions:
                try:
                    # Ensure all required fields are present and valid
                    symbol = pos.get('symbol', '')
                    if not symbol:
                        logger.warning(f"Skipping position with no symbol: {pos}")
                        continue
                    
                    size = float(pos.get('size', 0) or 0)
                    entry_price = float(pos.get('entry_price', 0) or 0)
                    mark_price = float(pos.get('mark_price', 0) or 0)
                    unrealized_pnl = float(pos.get('unrealized_pnl', 0) or 0)
                    
                    validated_positions.append({
                        'symbol': symbol,
                        'size': size,
                        'entry_price': entry_price,
                        'mark_price': mark_price,
                        'unrealized_pnl': unrealized_pnl,
                        'leverage': int(pos.get('leverage', 1) or 1),
                        'liquidation_price': float(pos.get('liquidation_price', 0) or 0)
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid position data skipped: {pos} - Error: {e}")
                    continue
            
            exchange_positions = validated_positions
            exchange_symbols = {pos['symbol'] for pos in exchange_positions}
            logger.debug(f"Exchange positions: {len(exchange_positions)} ({exchange_symbols})")
        except Exception as e:
            logger.error(f"Failed to fetch exchange positions: {type(e).__name__}: {e}")
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
        
        # Step 3b: Verify against risk limits
        risk_validator = TradeValidator()
        await self._verify_risk_consistency(exchange_positions, db_positions, risk_validator, db_session)
        
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
            
            # Create emergency trade record
            from datetime import datetime as dt
            emergency_trade = await self.trade_repo.create_trade({
                'mode': 'DEMO' if self.testnet else 'LIVE',
                'exchange': 'mexc',
                'symbol': symbol,
                'side': 'LONG' if ex_pos.get('size', 0) > 0 else 'SHORT',
                'status': 'ORPHANED_RECOVERED',
                'entry_price': ex_pos.get('entry_price', 0),
                'quantity': abs(ex_pos.get('size', 0)),
                'leverage': ex_pos.get('leverage', 1),
                'error_message': 'Orphaned position recovered during sync'
            }, db_session)
            
            # Then create position record linked to emergency trade
            await self.position_repo.upsert_position({
                'trade_id': emergency_trade.id,
                'symbol': symbol,
                'size': ex_pos.get('size', 0),
                'entry_price': ex_pos.get('entry_price', 0),
                'current_price': ex_pos.get('mark_price', 0),
                'unrealized_pnl': ex_pos.get('unrealized_pnl', 0),
                'liquidation_price': ex_pos.get('liquidation_price'),
                'leverage': ex_pos.get('leverage', 1),
                'status': 'open',
                'last_sync': dt.utcnow(),
                'sync_source': 'emergency_recovery'
            }, db_session)
            
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
            
            # Publish critical alert to freeze strategy
            await event_bus.publish(SYNC_MISMATCH, {
                'type': 'ghost_position_detected',
                'symbol': symbol,
                'action': 'strategy_frozen',
                'testnet': self.testnet
            }, priority=10)
            
            logger.critical(f"🚨 STRATEGY FROZEN: Ghost position detected for {symbol}. Manual intervention required.")
    
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
    
    async def _verify_risk_consistency(
        self,
        exchange_positions: List[Dict],
        db_positions: list,
        risk_validator: TradeValidator,
        db_session
    ):
        """Verify positions comply with risk limits."""
        # Check total exposure
        total_exposure = sum(
            pos.get('size', 0) * pos.get('mark_price', 0) 
            for pos in exchange_positions
        )
        
        max_position_usd = (
            settings.VALIDATION_MODE_MAX_POSITION_USD 
            if self.testnet 
            else settings.LIVE_TRADING_MAX_POSITION_USD
        )
        
        if total_exposure > max_position_usd:
            logger.critical(
                f"🚨 RISK VIOLATION: Total exposure ${total_exposure:.2f} "
                f"exceeds limit ${max_position_usd:.2f}"
            )
            
            # Freeze trading via event
            await event_bus.publish(SYNC_MISMATCH, {
                'type': 'risk_violation',
                'total_exposure': total_exposure,
                'limit': max_position_usd,
                'testnet': self.testnet
            }, priority=10)
    
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
            positions = await self.executor.get_positions()
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
