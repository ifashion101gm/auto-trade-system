"""
Order Reconciliation Engine - Periodic state sync verification.

This engine detects and repairs mismatches between database and exchange state:
- Orphaned orders (in DB but not on exchange)
- Ghost positions (on exchange but not in DB)
- Status mismatches (different status in DB vs exchange)
- Quantity/price discrepancies

Runs periodically (every 60 seconds) as a background task to ensure
database-exchange consistency for reliable trading operations.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.exchange_manager import UnifiedExchangeManager
from app.database.models import PaperTrades, TradeProposals
from app.notifications.notifier import TelegramNotifier
from app.logging_config import get_logger

logger = get_logger(__name__)


class ReconciliationResult:
    """Result of reconciliation run."""
    
    def __init__(self):
        self.timestamp = datetime.utcnow()
        self.mismatches_found = 0
        self.mismatches_repaired = 0
        self.mismatches_alerted = 0
        self.orphaned_orders = []
        self.ghost_positions = []
        self.status_mismatches = []
        self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'mismatches_found': self.mismatches_found,
            'mismatches_repaired': self.mismatches_repaired,
            'mismatches_alerted': self.mismatches_alerted,
            'orphaned_orders_count': len(self.orphaned_orders),
            'ghost_positions_count': len(self.ghost_positions),
            'status_mismatches_count': len(self.status_mismatches),
            'errors': self.errors
        }


class OrderReconciliationEngine:
    """
    Periodic reconciliation of database vs exchange state.
    
    This engine runs continuously as a background task, comparing
    open positions in the database with actual positions on the exchange.
    
    Detected issues are either auto-repaired (safe operations) or
    flagged for manual review (risky operations).
    """
    
    def __init__(
        self,
        exchange_name: str = "binance",
        use_testnet: bool = True,
        reconciliation_interval: int = 60,
        auto_repair_safe: bool = True,
        enable_telegram_alerts: bool = True,
        enable_prometheus_metrics: bool = True
    ):
        """
        Initialize reconciliation engine.
        
        Args:
            exchange_name: Exchange to reconcile against
            use_testnet: Use testnet mode
            reconciliation_interval: Seconds between reconciliation runs
            auto_repair_safe: Auto-repair safe mismatches (orphaned orders)
            enable_telegram_alerts: Send Telegram alerts for critical mismatches
            enable_prometheus_metrics: Publish metrics to Prometheus
        """
        self.exchange_name = exchange_name
        self.use_testnet = use_testnet
        self.reconciliation_interval = reconciliation_interval
        self.auto_repair_safe = auto_repair_safe
        self.enable_telegram_alerts = enable_telegram_alerts
        self.enable_prometheus_metrics = enable_prometheus_metrics
        
        # Initialize components
        self.exchange_manager = UnifiedExchangeManager(
            exchange_name=exchange_name,
            use_testnet=use_testnet
        )
        self.notifier = TelegramNotifier()
        
        # State tracking
        self.is_running = False
        self.last_run = None
        self.total_runs = 0
        self.total_mismatches = 0
        
        logger.info(f"✅ Reconciliation Engine initialized ({exchange_name.upper()})")
    
    async def start(self, db_session_factory):
        """
        Start reconciliation loop as background task.
        
        Args:
            db_session_factory: Factory function to create DB sessions
        """
        if self.is_running:
            logger.warning("Reconciliation engine already running")
            return
        
        self.is_running = True
        logger.info("🔄 Starting reconciliation engine...")
        
        while self.is_running:
            try:
                # Create new session for each run
                async with db_session_factory() as db_session:
                    result = await self.run_reconciliation(db_session)
                    
                    # Log results
                    if result.mismatches_found > 0:
                        logger.warning(
                            f"⚠️ Reconciliation found {result.mismatches_found} mismatches: "
                            f"{result.mismatches_repaired} repaired, "
                            f"{result.mismatches_alerted} alerted"
                        )
                    else:
                        logger.debug("✅ Reconciliation: No mismatches found")
                    
                    self.last_run = datetime.utcnow()
                    self.total_runs += 1
                    self.total_mismatches += result.mismatches_found
                    
                    # Publish metrics to Prometheus (if enabled)
                    if self.enable_prometheus_metrics:
                        await self._publish_metrics(result)
                    
                    # Send Telegram alerts for critical mismatches (if enabled)
                    if self.enable_telegram_alerts and result.mismatches_found > 0:
                        await self._send_telegram_alerts(result)
                    
            except Exception as e:
                logger.error(f"Reconciliation run failed: {e}", exc_info=True)
            
            # Wait before next run
            await asyncio.sleep(self.reconciliation_interval)
    
    def stop(self):
        """Stop reconciliation loop."""
        logger.info("Stopping reconciliation engine...")
        self.is_running = False
    
    async def run_reconciliation(self, db_session: AsyncSession) -> ReconciliationResult:
        """
        Run single reconciliation cycle.
        
        Compares database positions with exchange positions and detects mismatches.
        
        Args:
            db_session: Database session
            
        Returns:
            ReconciliationResult with detected issues and actions taken
        """
        result = ReconciliationResult()
        
        try:
            # Get open positions from database
            db_positions = await self._get_db_positions(db_session)
            
            # Get actual positions from exchange
            exchange_positions = await self._get_exchange_positions()
            
            # Detect mismatches
            await self._detect_orphaned_orders(db_positions, exchange_positions, result, db_session)
            await self._detect_ghost_positions(db_positions, exchange_positions, result, db_session)
            await self._detect_status_mismatches(db_positions, exchange_positions, result, db_session)
            
            logger.info(
                f"Reconciliation complete: {result.mismatches_found} mismatches, "
                f"{result.mismatches_repaired} repaired"
            )
            
        except Exception as e:
            logger.error(f"Reconciliation failed: {e}", exc_info=True)
            result.errors.append(str(e))
        
        return result
    
    async def _get_db_positions(self, db_session: AsyncSession) -> List[Dict[str, Any]]:
        """Get all open positions from database."""
        stmt = select(PaperTrades).where(
            PaperTrades.status == 'open',
            PaperTrades.exchange == self.exchange_name
        )
        result = await db_session.execute(stmt)
        trades = result.scalars().all()
        
        positions = []
        for trade in trades:
            positions.append({
                'trade_id': trade.id,
                'symbol': trade.symbol,
                'side': trade.side,
                'quantity': trade.qty,
                'entry_price': trade.entry_price,
                'status': trade.status,
                'notes': trade.notes or '',
                'ts_open': trade.ts_open
            })
        
        logger.debug(f"Found {len(positions)} open positions in database")
        return positions
    
    async def _get_exchange_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions from exchange."""
        try:
            # Fetch open positions from exchange
            positions = await self.exchange_manager.get_open_positions()
            
            # Normalize position data
            normalized = []
            for pos in positions:
                normalized.append({
                    'order_id': pos.get('order_id') or pos.get('id'),
                    'symbol': pos.get('symbol'),
                    'side': pos.get('side', '').upper(),
                    'quantity': pos.get('quantity') or pos.get('amount'),
                    'entry_price': pos.get('price') or pos.get('entry_price'),
                    'status': pos.get('status', 'open')
                })
            
            logger.debug(f"Found {len(normalized)} open positions on exchange")
            return normalized
            
        except Exception as e:
            logger.error(f"Failed to fetch exchange positions: {e}")
            return []
    
    async def _detect_orphaned_orders(
        self,
        db_positions: List[Dict],
        exchange_positions: List[Dict],
        result: ReconciliationResult,
        db_session: AsyncSession
    ):
        """Detect orders in DB but not on exchange (orphaned)."""
        # Extract order IDs from exchange positions
        exchange_order_ids = set()
        for pos in exchange_positions:
            if pos.get('order_id'):
                exchange_order_ids.add(pos['order_id'])
        
        # Check each DB position
        for db_pos in db_positions:
            # Extract order ID from notes
            order_id = self._extract_order_id_from_notes(db_pos['notes'])
            
            if order_id and order_id not in exchange_order_ids:
                # Found orphaned order
                result.orphaned_orders.append(db_pos)
                result.mismatches_found += 1
                
                logger.warning(
                    f"⚠️ Orphaned order detected: Trade {db_pos['trade_id']} "
                    f"(Order {order_id}) exists in DB but not on exchange"
                )
                
                # Auto-repair if enabled
                if self.auto_repair_safe:
                    await self._repair_orphaned_order(db_pos, db_session, result)
                else:
                    # Alert for manual review
                    await self._alert_mismatch('ORPHANED_ORDER', db_pos, result)
    
    async def _detect_ghost_positions(
        self,
        db_positions: List[Dict],
        exchange_positions: List[Dict],
        result: ReconciliationResult,
        db_session: AsyncSession
    ):
        """Detect positions on exchange but not in DB (ghost)."""
        # Extract symbols from DB positions
        db_symbols = set()
        for pos in db_positions:
            db_symbols.add(pos['symbol'])
        
        # Check each exchange position
        for exc_pos in exchange_positions:
            if exc_pos['symbol'] not in db_symbols:
                # Found ghost position
                result.ghost_positions.append(exc_pos)
                result.mismatches_found += 1
                
                logger.warning(
                    f"⚠️ Ghost position detected: {exc_pos['symbol']} "
                    f"exists on exchange but not in DB"
                )
                
                # Import into database
                await self._import_ghost_position(exc_pos, db_session, result)
    
    async def _detect_status_mismatches(
        self,
        db_positions: List[Dict],
        exchange_positions: List[Dict],
        result: ReconciliationResult,
        db_session: AsyncSession
    ):
        """Detect status mismatches between DB and exchange."""
        # Build lookup by symbol
        exc_by_symbol = {}
        for pos in exchange_positions:
            exc_by_symbol[pos['symbol']] = pos
        
        # Check each DB position
        for db_pos in db_positions:
            exc_pos = exc_by_symbol.get(db_pos['symbol'])
            
            if exc_pos:
                # Compare statuses
                db_status = db_pos['status'].lower()
                exc_status = exc_pos['status'].lower()
                
                if db_status != exc_status:
                    result.status_mismatches.append({
                        'db_position': db_pos,
                        'exchange_position': exc_pos
                    })
                    result.mismatches_found += 1
                    
                    logger.warning(
                        f"⚠️ Status mismatch: {db_pos['symbol']} - "
                        f"DB={db_status}, Exchange={exc_status}"
                    )
                    
                    # Update DB to match exchange
                    await self._repair_status_mismatch(db_pos, exc_pos, db_session, result)
    
    def _extract_order_id_from_notes(self, notes: str) -> Optional[str]:
        """Extract order ID from trade notes."""
        if not notes:
            return None
        
        # Look for "Order ID: XXXX" pattern
        if 'Order ID:' in notes:
            parts = notes.split('Order ID:')
            if len(parts) > 1:
                order_id = parts[1].strip().split(',')[0].strip()
                return order_id
        
        return None
    
    async def _repair_orphaned_order(
        self,
        db_pos: Dict,
        db_session: AsyncSession,
        result: ReconciliationResult
    ):
        """Repair orphaned order by marking as failed."""
        try:
            stmt = select(PaperTrades).where(PaperTrades.id == db_pos['trade_id'])
            trade_result = await db_session.execute(stmt)
            trade = trade_result.scalar_one_or_none()
            
            if trade:
                trade.status = 'failed'
                trade.trade_status = 'FAILED'
                trade.notes += f"\n[RECONCILIATION] Orphaned order detected and marked as failed at {datetime.utcnow().isoformat()}"
                await db_session.flush()
                
                result.mismatches_repaired += 1
                logger.info(f"✅ Repaired orphaned order: Trade {db_pos['trade_id']}")
                
        except Exception as e:
            logger.error(f"Failed to repair orphaned order: {e}")
            result.errors.append(f"Orphaned order repair failed: {str(e)}")
    
    async def _import_ghost_position(
        self,
        exc_pos: Dict,
        db_session: AsyncSession,
        result: ReconciliationResult
    ):
        """Import ghost position into database."""
        try:
            # Create new trade record
            trade = PaperTrades(
                ts_open=datetime.utcnow().isoformat(),
                user_id='reconciliation_import',
                exchange=self.exchange_name,
                symbol=exc_pos['symbol'],
                side=exc_pos['side'],
                leverage=1,  # Default, may need adjustment
                qty=exc_pos['quantity'],
                entry_price=exc_pos['entry_price'],
                exit_price=None,
                stop_loss=None,
                take_profit=None,
                profit=None,
                profit_pct=None,
                status='open',
                trade_status='POSITION_OPEN',
                notes=f'[RECONCILIATION] Ghost position imported from exchange at {datetime.utcnow().isoformat()}'
            )
            
            db_session.add(trade)
            await db_session.flush()
            
            result.mismatches_repaired += 1
            logger.info(f"✅ Imported ghost position: {exc_pos['symbol']} as Trade {trade.id}")
            
            # Alert operator
            await self._alert_mismatch('GHOST_POSITION_IMPORTED', exc_pos, result)
            
        except Exception as e:
            logger.error(f"Failed to import ghost position: {e}")
            result.errors.append(f"Ghost position import failed: {str(e)}")
    
    async def _repair_status_mismatch(
        self,
        db_pos: Dict,
        exc_pos: Dict,
        db_session: AsyncSession,
        result: ReconciliationResult
    ):
        """Repair status mismatch by updating DB to match exchange."""
        try:
            stmt = select(PaperTrades).where(PaperTrades.id == db_pos['trade_id'])
            trade_result = await db_session.execute(stmt)
            trade = trade_result.scalar_one_or_none()
            
            if trade:
                old_status = trade.status
                trade.status = exc_pos['status'].lower()
                trade.notes += f"\n[RECONCILIATION] Status updated from {old_status} to {trade.status} at {datetime.utcnow().isoformat()}"
                await db_session.flush()
                
                result.mismatches_repaired += 1
                logger.info(
                    f"✅ Repaired status mismatch: Trade {db_pos['trade_id']} "
                    f"({old_status} → {trade.status})"
                )
                
        except Exception as e:
            logger.error(f"Failed to repair status mismatch: {e}")
            result.errors.append(f"Status mismatch repair failed: {str(e)}")
    
    async def _alert_mismatch(
        self,
        mismatch_type: str,
        position_data: Dict,
        result: ReconciliationResult
    ):
        """Send alert for detected mismatch."""
        try:
            await self.notifier.send_reconciliation_alert(
                action=f'{mismatch_type}_DETECTED',
                symbol=position_data.get('symbol', 'UNKNOWN'),
                exchange=self.exchange_name,
                mismatch_type=mismatch_type,
                requires_review=True
            )
            
            result.mismatches_alerted += 1
            
        except Exception as e:
            logger.error(f"Failed to send reconciliation alert: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reconciliation statistics."""
        return {
            'is_running': self.is_running,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'total_runs': self.total_runs,
            'total_mismatches': self.total_mismatches,
            'reconciliation_interval': self.reconciliation_interval
        }
    
    async def _publish_metrics(self, result: ReconciliationResult):
        """
        Publish reconciliation results to Prometheus metrics.
        
        Args:
            result: ReconciliationResult from latest run
        """
        try:
            from app.monitoring.prometheus_metrics import get_metrics_collector
            metrics = get_metrics_collector()
            
            # Update mismatch gauges by type
            metrics.update_reconciliation_mismatches(
                mismatch_type='orphaned',
                count=len(result.orphaned_orders)
            )
            metrics.update_reconciliation_mismatches(
                mismatch_type='ghost',
                count=len(result.ghost_positions)
            )
            metrics.update_reconciliation_mismatches(
                mismatch_type='status_diff',
                count=len(result.status_mismatches)
            )
            
            # Record repairs as counters
            for _ in range(result.mismatches_repaired):
                metrics.record_reconciliation_repair(repair_type='auto_repair')
            
            # Record total mismatches found
            metrics.update_reconciliation_mismatches(
                mismatch_type='total',
                count=result.mismatches_found
            )
            
            logger.debug(f"📊 Published reconciliation metrics: {result.mismatches_found} mismatches")
            
        except ImportError:
            logger.warning("Prometheus metrics not available, skipping metric publication")
        except Exception as e:
            logger.error(f"Failed to publish reconciliation metrics: {e}")
    
    async def _send_telegram_alerts(self, result: ReconciliationResult):
        """
        Send Telegram alerts for critical reconciliation mismatches.
        Implements alert deduplication to prevent spam.
        
        Args:
            result: ReconciliationResult with detected issues
        """
        try:
            # Import alert manager for deduplication
            from app.notifications.alert_manager import get_alert_manager
            alert_mgr = get_alert_manager()
            
            # Alert for orphaned orders (safe - auto-repaired)
            if result.orphaned_orders:
                for order in result.orphaned_orders:
                    await alert_mgr.send_alert(
                        level="WARNING",
                        title="Orphaned Order Detected",
                        message=(
                            f"Trade {order.get('trade_id')} ({order.get('symbol')}) "
                            f"exists in DB but not on exchange. Auto-repaired."
                        ),
                        alert_type=f"orphaned_order_{order.get('trade_id')}",
                        urgency="normal"
                    )
            
            # Alert for ghost positions (requires review)
            if result.ghost_positions:
                for pos in result.ghost_positions:
                    await alert_mgr.send_alert(
                        level="CRITICAL",
                        title="Ghost Position Detected",
                        message=(
                            f"Position {pos.get('symbol')} exists on exchange "
                            f"but not in database. Imported automatically."
                        ),
                        alert_type=f"ghost_position_{pos.get('symbol')}",
                        urgency="high"
                    )
            
            # Alert for status mismatches (requires review)
            if result.status_mismatches:
                for mismatch in result.status_mismatches:
                    db_pos = mismatch.get('db_position', {})
                    exc_pos = mismatch.get('exchange_position', {})
                    await alert_mgr.send_alert(
                        level="WARNING",
                        title="Status Mismatch Detected",
                        message=(
                            f"{db_pos.get('symbol')}: DB={db_pos.get('status')}, "
                            f"Exchange={exc_pos.get('status')}. Auto-repaired."
                        ),
                        alert_type=f"status_mismatch_{db_pos.get('trade_id')}",
                        urgency="normal"
                    )
            
            logger.info(f"📱 Sent {result.mismatches_alerted} Telegram alerts")
            
        except ImportError:
            logger.warning("AlertManager not available, using legacy notifier")
            # Fallback to legacy notifier
            await self._send_legacy_telegram_alerts(result)
        except Exception as e:
            logger.error(f"Failed to send Telegram alerts: {e}")
    
    async def _send_legacy_telegram_alerts(self, result: ReconciliationResult):
        """
        Legacy Telegram alert method (fallback if AlertManager unavailable).
        
        Args:
            result: ReconciliationResult with detected issues
        """
        try:
            # Alert for orphaned orders (safe - auto-repaired)
            if result.orphaned_orders:
                for order in result.orphaned_orders:
                    await self.notifier.send_reconciliation_alert(
                        action='ORPHANED_ORDER_DETECTED',
                        symbol=order.get('symbol', 'UNKNOWN'),
                        exchange=self.exchange_name,
                        mismatch_type='orphaned_order',
                        requires_review=False  # Auto-repaired
                    )
            
            # Alert for ghost positions (requires review)
            if result.ghost_positions:
                for pos in result.ghost_positions:
                    await self.notifier.send_reconciliation_alert(
                        action='GHOST_POSITION_DETECTED',
                        symbol=pos.get('symbol', 'UNKNOWN'),
                        exchange=self.exchange_name,
                        mismatch_type='ghost_position',
                        requires_review=True
                    )
            
            # Alert for status mismatches (requires review)
            if result.status_mismatches:
                for mismatch in result.status_mismatches:
                    await self.notifier.send_reconciliation_alert(
                        action='STATUS_MISMATCH_DETECTED',
                        symbol=mismatch.get('symbol', 'UNKNOWN'),
                        exchange=self.exchange_name,
                        mismatch_type='status_mismatch',
                        requires_review=True
                    )
            
            logger.info(f"📱 Sent {result.mismatches_alerted} Telegram alerts (legacy)")
            
        except Exception as e:
            logger.error(f"Failed to send legacy Telegram alerts: {e}")
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """
        Get detailed reconciliation status for dashboard.
        
        Returns:
            Dictionary with comprehensive reconciliation information
        """
        return {
            'is_running': self.is_running,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'total_runs': self.total_runs,
            'total_mismatches_detected': self.total_mismatches,
            'reconciliation_interval_seconds': self.reconciliation_interval,
            'auto_repair_enabled': self.auto_repair_safe,
            'exchange': self.exchange_name,
            'testnet': self.use_testnet,
            'next_run_in_seconds': max(0, self.reconciliation_interval - (
                (datetime.utcnow() - self.last_run).total_seconds() if self.last_run else 0
            ))
        }
