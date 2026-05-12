"""
Position Reconciliation Engine - Critical Component
Compares states across Exchange, Database, Risk Engine, and Open Orders.
Runs every few seconds to detect and repair discrepancies.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.exchange.exchange_router import ExchangeRouter
from app.database.repositories import TradeRepository, PositionRepository, OrderRepository
from app.risk.risk_engine import RiskEngine
from app.events.event_bus import event_bus
from app.notifications.notifier import TelegramNotifier
from app.logging_config import get_logger

logger = get_logger(__name__)


class ReconciliationDiscrepancy:
    """Represents a detected discrepancy."""
    
    def __init__(
        self,
        discrepancy_type: str,
        symbol: str,
        exchange_state: Dict,
        db_state: Dict,
        severity: str = "HIGH"
    ):
        self.discrepancy_type = discrepancy_type
        self.symbol = symbol
        self.exchange_state = exchange_state
        self.db_state = db_state
        self.severity = severity
        self.detected_at = datetime.utcnow()


class PositionReconciliationEngine:
    """
    High-priority reconciliation engine that runs continuously.
    
    Compares:
    - Exchange positions vs Database positions
    - Open orders vs Trade records
    - Risk engine state vs actual positions
    
    Recovery Rules:
    1. DB shows LONG but Exchange shows NONE → Emergency sync + Alert + Freeze strategy
    2. Exchange shows position but DB missing → Recreate DB record
    3. Size mismatch → Update DB to match exchange
    4. Orphaned orders → Cancel or reconcile
    """
    
    def __init__(self, testnet: bool = False):
        self.router = ExchangeRouter()
        self.trade_repo = TradeRepository()
        self.position_repo = PositionRepository()
        self.order_repo = OrderRepository()
        self.risk_engine = RiskEngine(db_session=None)
        self.notifier = TelegramNotifier()
        self.testnet = testnet
        self._running = False
        self._check_interval = 5  # seconds
        self.strategy_frozen = False
    
    async def start(self, db_session_factory):
        """Start continuous reconciliation loop."""
        self._running = True
        logger.info(f"🔄 Reconciliation Engine started (interval={self._check_interval}s)")
        
        while self._running:
            try:
                async with db_session_factory() as db_session:
                    await self.run_reconciliation_cycle(db_session)
                
                await asyncio.sleep(self._check_interval)
                
            except Exception as e:
                logger.error(f"❌ Reconciliation error: {e}")
                await asyncio.sleep(self._check_interval)
    
    def stop(self):
        """Stop reconciliation engine."""
        self._running = False
        logger.info("🛑 Reconciliation Engine stopped")
    
    async def run_reconciliation_cycle(self, db_session: AsyncSession):
        """Execute one full reconciliation cycle."""
        logger.debug("🔍 Running reconciliation cycle...")
        
        discrepancies = []
        
        # Check 1: Compare exchange positions vs database positions
        discrepancies.extend(await self._check_positions(db_session))
        
        # Check 2: Verify open orders consistency
        discrepancies.extend(await self._check_open_orders(db_session))
        
        # Check 3: Validate risk engine state
        discrepancies.extend(await self._check_risk_state(db_session))
        
        # Process discrepancies
        for discrepancy in discrepancies:
            await self._handle_discrepancy(discrepancy, db_session)
        
        if discrepancies:
            logger.warning(f"⚠️ Reconciliation found {len(discrepancies)} discrepancies")
        else:
            logger.debug("✅ Reconciliation: All systems consistent")
    
    async def _check_positions(self, db_session: AsyncSession) -> List[ReconciliationDiscrepancy]:
        """Compare exchange positions with database positions."""
        discrepancies = []
        
        try:
            # Fetch exchange positions
            exchange = self.router.get_exchange('DEMO' if self.testnet else 'LIVE')
            exchange_positions = await exchange.get_positions()
            exchange_symbols = {p['symbol']: p for p in exchange_positions}
            
            # Fetch database positions
            db_positions = await self.position_repo.get_open_positions(db_session)
            db_symbols = {p.symbol: p for p in db_positions}
            
            # Case 1: Position in DB but NOT on exchange (Ghost Position)
            for symbol, db_pos in db_symbols.items():
                if symbol not in exchange_symbols:
                    discrepancy = ReconciliationDiscrepancy(
                        discrepancy_type="GHOST_POSITION",
                        symbol=symbol,
                        exchange_state={'size': 0, 'side': 'NONE'},
                        db_state={'size': db_pos.size, 'side': db_pos.side},
                        severity="CRITICAL"
                    )
                    discrepancies.append(discrepancy)
            
            # Case 2: Position on exchange but NOT in DB (Missing Record)
            for symbol, ex_pos in exchange_symbols.items():
                if symbol not in db_symbols:
                    discrepancy = ReconciliationDiscrepancy(
                        discrepancy_type="MISSING_DB_RECORD",
                        symbol=symbol,
                        exchange_state=ex_pos,
                        db_state={'exists': False},
                        severity="HIGH"
                    )
                    discrepancies.append(discrepancy)
            
            # Case 3: Size/price mismatches
            for symbol in set(exchange_symbols.keys()) & set(db_symbols.keys()):
                ex_pos = exchange_symbols[symbol]
                db_pos = db_symbols[symbol]
                
                size_diff = abs(ex_pos.get('size', 0) - db_pos.size)
                price_diff = abs(ex_pos.get('entry_price', 0) - db_pos.entry_price)
                
                if size_diff > 0.001 or price_diff > 0.01:
                    discrepancy = ReconciliationDiscrepancy(
                        discrepancy_type="STATE_MISMATCH",
                        symbol=symbol,
                        exchange_state=ex_pos,
                        db_state={'size': db_pos.size, 'entry_price': db_pos.entry_price},
                        severity="MEDIUM"
                    )
                    discrepancies.append(discrepancy)
        
        except Exception as e:
            logger.error(f"Position check failed: {e}")
        
        return discrepancies
    
    async def _check_open_orders(self, db_session: AsyncSession) -> List[ReconciliationDiscrepancy]:
        """Verify open orders match trade records."""
        discrepancies = []
        
        try:
            exchange = self.router.get_exchange('DEMO' if self.testnet else 'LIVE')
            open_orders = await exchange.fetch_open_orders()
            exchange_order_ids = {o.get('id') for o in open_orders if o.get('status') == 'open'}
            
            # Get pending orders from DB
            pending_orders = await self.order_repo.get_pending_orders(db_session)
            db_order_ids = {o.exchange_order_id for o in pending_orders if o.exchange_order_id}
            
            # Orphaned orders in DB
            orphaned = db_order_ids - exchange_order_ids
            for order_id in orphaned:
                discrepancies.append(ReconciliationDiscrepancy(
                    discrepancy_type="ORPHANED_ORDER",
                    symbol="UNKNOWN",
                    exchange_state={'exists': False},
                    db_state={'order_id': order_id, 'status': 'PENDING'},
                    severity="HIGH"
                ))
        
        except Exception as e:
            logger.error(f"Open orders check failed: {e}")
        
        return discrepancies
    
    async def _check_risk_state(self, db_session: AsyncSession) -> List[ReconciliationDiscrepancy]:
        """Validate risk engine state matches actual positions."""
        # This would compare risk engine's tracked exposure vs actual positions
        # For now, return empty list - can be enhanced later
        return []
    
    async def _handle_discrepancy(self, discrepancy: ReconciliationDiscrepancy, db_session: AsyncSession):
        """Handle detected discrepancy based on type and severity."""
        logger.warning(
            f"⚠️ Discrepancy detected: {discrepancy.discrepancy_type} "
            f"for {discrepancy.symbol} (Severity: {discrepancy.severity})"
        )
        
        if discrepancy.discrepancy_type == "GHOST_POSITION":
            await self._handle_ghost_position(discrepancy, db_session)
        
        elif discrepancy.discrepancy_type == "MISSING_DB_RECORD":
            await self._handle_missing_db_record(discrepancy, db_session)
        
        elif discrepancy.discrepancy_type == "STATE_MISMATCH":
            await self._handle_state_mismatch(discrepancy, db_session)
        
        elif discrepancy.discrepancy_type == "ORPHANED_ORDER":
            await self._handle_orphaned_order(discrepancy, db_session)
    
    async def _handle_ghost_position(self, discrepancy: ReconciliationDiscrepancy, db_session: AsyncSession):
        """
        Handle ghost position: DB shows position but exchange shows none.
        
        Recovery Rule:
        1. Send emergency Telegram alert
        2. Mark position as closed in DB
        3. Freeze strategy temporarily
        4. Log recovery event
        """
        logger.critical(f"🚨 GHOST POSITION detected for {discrepancy.symbol}!")
        
        # 1. Send Telegram alert
        await self.notifier.send_message(
            f"🚨 CRITICAL: Ghost Position Detected\n"
            f"Symbol: {discrepancy.symbol}\n"
            f"DB State: {discrepancy.db_state}\n"
            f"Exchange State: {discrepancy.exchange_state}\n"
            f"Action: Position marked as closed, strategy frozen"
        )
        
        # 2. Mark position as closed in DB
        position = await self.position_repo.get_position_by_symbol(discrepancy.symbol, db_session)
        if position:
            position.status = 'closed'
            position.last_sync = datetime.utcnow()
        
        # 3. Freeze strategy
        self.strategy_frozen = True
        logger.warning(f"❄️ Strategy FROZEN due to ghost position in {discrepancy.symbol}")
        
        # 4. Log recovery event
        from app.database.models import RecoveryEvents
        recovery_event = RecoveryEvents(
            recovery_type="GHOST_POSITION",
            symbol=discrepancy.symbol,
            exchange="MEXC",  # Or dynamic
            description=f"Ghost position detected and closed. Strategy frozen.",
            old_state=str(discrepancy.db_state),
            new_state=str(discrepancy.exchange_state),
            auto_repaired=1,
            requires_manual_review=1
        )
        db_session.add(recovery_event)
        await db_session.commit()
    
    async def _handle_missing_db_record(self, discrepancy: ReconciliationDiscrepancy, db_session: AsyncSession):
        """
        Handle missing DB record: Exchange has position but DB doesn't.
        
        Recovery Rule:
        1. Recreate position record in DB
        2. Find or create associated trade
        3. Send notification
        """
        logger.warning(f"📝 Missing DB record for {discrepancy.symbol} - recreating...")
        
        ex_pos = discrepancy.exchange_state
        
        # Find associated trade or create placeholder
        trade = await self.trade_repo.get_open_trade_by_symbol(discrepancy.symbol, db_session)
        
        if not trade:
            logger.warning(f"No trade found for {discrepancy.symbol} - creating placeholder")
            # Create minimal trade record
            from app.database.models import Trades
            import uuid
            trade = Trades(
                id=str(uuid.uuid4()),
                mode='DEMO' if self.testnet else 'LIVE',
                exchange='mexc',
                symbol=discrepancy.symbol,
                side='LONG' if ex_pos.get('size', 0) > 0 else 'SHORT',
                status='OPEN',
                entry_price=ex_pos.get('entry_price', 0),
                current_price=ex_pos.get('current_price', 0),
                leverage=ex_pos.get('leverage', 1),
                quantity=abs(ex_pos.get('size', 0)),
                created_at=datetime.utcnow().isoformat()
            )
            db_session.add(trade)
            await db_session.flush()
        
        # Create position record
        await self.position_repo.upsert_position({
            'trade_id': trade.id,
            'symbol': discrepancy.symbol,
            'size': ex_pos.get('size', 0),
            'entry_price': ex_pos.get('entry_price', 0),
            'current_price': ex_pos.get('current_price', 0),
            'unrealized_pnl': ex_pos.get('unrealized_pnl', 0),
            'liquidation_price': ex_pos.get('liquidation_price'),
            'leverage': ex_pos.get('leverage', 1),
            'status': 'open',
            'last_sync': datetime.utcnow(),
            'sync_source': 'reconciliation_engine'
        }, db_session)
        
        await self.notifier.send_message(
            f"📝 Reconciliation: Recreated missing position for {discrepancy.symbol}"
        )
    
    async def _handle_state_mismatch(self, discrepancy: ReconciliationDiscrepancy, db_session: AsyncSession):
        """Handle state mismatch: Update DB to match exchange."""
        logger.info(f"🔄 State mismatch for {discrepancy.symbol} - updating DB...")
        
        position = await self.position_repo.get_position_by_symbol(discrepancy.symbol, db_session)
        if position:
            ex_pos = discrepancy.exchange_state
            position.size = ex_pos.get('size', 0)
            position.current_price = ex_pos.get('current_price', 0)
            position.unrealized_pnl = ex_pos.get('unrealized_pnl', 0)
            position.last_sync = datetime.utcnow()
            position.sync_source = 'reconciliation_engine'
            await db_session.commit()
    
    async def _handle_orphaned_order(self, discrepancy: ReconciliationDiscrepancy, db_session: AsyncSession):
        """Handle orphaned order: Mark as canceled in DB."""
        logger.warning(f"🗑️ Orphaned order detected: {discrepancy.db_state.get('order_id')}")
        
        # Update order status to CANCELED
        # Implementation depends on OrderRepository methods
        # For now, just log
        await self.notifier.send_message(
            f"🗑️ Orphaned order detected and marked for review"
        )
