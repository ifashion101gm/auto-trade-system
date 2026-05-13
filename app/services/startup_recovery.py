"""
Startup Recovery Service - Restores system state after VPS restart or crash.

Responsibilities:
1. Load database snapshot of open positions
2. Query exchange for actual positions and orders
3. Reconcile mismatches (ghost/phantom positions)
4. Rebuild state machine to correct state
5. Restart position monitors
6. Verify circuit breaker health
7. Resume trading only if all checks pass

This prevents catastrophic scenarios like:
- Bot starts empty while live trade exists on exchange
- No stop-loss management on existing positions
- Dashboard shows wrong data
- State machine stuck in invalid state
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.exchange_manager import UnifiedExchangeManager
from app.services.position_monitor import PositionMonitor
from app.services.reconciliation_service import PositionReconciliationService
from app.infra.circuit_breaker import SystemCircuitBreaker
from app.execution.state_validator import state_validator
from app.database.models import PaperTrades
from app.events.event_bus import EventBus
from app.logging_config import get_logger
from app.notifications.notifier import TelegramNotifier

logger = get_logger(__name__)


class StartupRecoveryResult:
    """Result of startup recovery process."""
    
    def __init__(self):
        self.success: bool = False
        self.db_positions_loaded: int = 0
        self.exchange_positions_found: int = 0
        self.positions_repaired: int = 0
        self.monitors_restarted: int = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.recovery_time_seconds: float = 0.0
        self.can_resume_trading: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'db_positions_loaded': self.db_positions_loaded,
            'exchange_positions_found': self.exchange_positions_found,
            'positions_repaired': self.positions_repaired,
            'monitors_restarted': self.monitors_restarted,
            'errors': self.errors,
            'warnings': self.warnings,
            'recovery_time_seconds': round(self.recovery_time_seconds, 2),
            'can_resume_trading': self.can_resume_trading
        }


class StartupRecoveryService:
    """
    Service to recover system state after restart/crash.
    
    Flow:
    1. Load DB snapshot
    2. Query exchange positions
    3. Reconcile mismatches
    4. Rebuild state machines
    5. Restart monitors
    6. Health check
    7. Resume trading if healthy
    """
    
    def __init__(
        self,
        exchange_manager: UnifiedExchangeManager,
        position_monitor: PositionMonitor,
        reconciliation_service: PositionReconciliationService,
        circuit_breaker: SystemCircuitBreaker,
        event_bus: EventBus,
        notifier: TelegramNotifier
    ):
        """
        Initialize startup recovery service.
        
        Args:
            exchange_manager: Exchange manager for API calls
            position_monitor: Position monitor to restart
            reconciliation_service: Service for position reconciliation
            circuit_breaker: Circuit breaker for health checks
            event_bus: Event bus for publishing events
            notifier: Telegram notifier for alerts
        """
        self.exchange_manager = exchange_manager
        self.position_monitor = position_monitor
        self.reconciliation_service = reconciliation_service
        self.circuit_breaker = circuit_breaker
        self.event_bus = event_bus
        self.notifier = notifier
        
        logger.info("✅ StartupRecoveryService initialized")
    
    async def execute_recovery(
        self,
        user_id: str,
        db_session: AsyncSession
    ) -> StartupRecoveryResult:
        """
        Execute full startup recovery sequence.
        
        Args:
            user_id: User ID to recover positions for
            db_session: Database session
        
        Returns:
            StartupRecoveryResult with detailed status
        """
        import time
        start_time = time.time()
        result = StartupRecoveryResult()
        
        try:
            logger.info("🚀 Starting system recovery...")
            
            # Step 1: Load DB snapshot
            await self._step_load_db_snapshot(user_id, db_session, result)
            
            # Step 2: Query exchange positions
            await self._step_query_exchange_positions(result)
            
            # Step 3: Reconcile mismatches
            await self._step_reconcile_positions(user_id, db_session, result)
            
            # Step 4: Rebuild state machines
            await self._step_rebuild_state_machines(result)
            
            # Step 5: Restart position monitors
            await self._step_restart_monitors(user_id, db_session, result)
            
            # Step 6: Health check
            await self._step_health_check(result)
            
            # Step 7: Determine if trading can resume
            result.can_resume_trading = (
                result.success and
                len(result.errors) == 0 and
                self.circuit_breaker.state != 'OPEN'
            )
            
            result.recovery_time_seconds = time.time() - start_time
            
            # Send recovery notification
            await self._send_recovery_notification(result)
            
            if result.can_resume_trading:
                logger.info(f"✅ Recovery complete in {result.recovery_time_seconds:.2f}s - Trading can resume")
            else:
                logger.warning(
                    f"⚠️  Recovery completed but trading blocked: "
                    f"{len(result.errors)} errors, circuit_breaker={self.circuit_breaker.state}"
                )
            
        except Exception as e:
            logger.error(f"Startup recovery failed catastrophically: {e}")
            result.errors.append(f"Catastrophic failure: {str(e)}")
            result.recovery_time_seconds = time.time() - start_time
            result.can_resume_trading = False
        
        return result
    
    async def _step_load_db_snapshot(
        self,
        user_id: str,
        db_session: AsyncSession,
        result: StartupRecoveryResult
    ):
        """Load open positions from database."""
        try:
            logger.info("   Step 1: Loading DB snapshot...")
            
            stmt = select(PaperTrades).where(
                PaperTrades.user_id == user_id,
                PaperTrades.status == 'open'
            )
            
            query_result = await db_session.execute(stmt)
            trades = query_result.scalars().all()
            
            result.db_positions_loaded = len(trades)
            
            if result.db_positions_loaded > 0:
                logger.info(f"   ✅ Found {result.db_positions_loaded} open positions in DB")
                
                for trade in trades:
                    logger.info(
                        f"      - {trade.symbol} {trade.side} "
                        f"@ ${trade.entry_price:.2f} x {trade.qty}"
                    )
            else:
                logger.info("   ℹ️  No open positions in DB")
            
        except Exception as e:
            error_msg = f"DB snapshot load failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
    
    async def _step_query_exchange_positions(self, result: StartupRecoveryResult):
        """Query exchange for actual open positions."""
        try:
            logger.info("   Step 2: Querying exchange positions...")
            
            positions = await self.exchange_manager.fetch_positions()
            result.exchange_positions_found = len(positions)
            
            if result.exchange_positions_found > 0:
                logger.info(f"   ✅ Found {result.exchange_positions_found} positions on exchange")
                
                for pos in positions:
                    logger.info(
                        f"      - {pos.get('symbol')} "
                        f"size={pos.get('size')} "
                        f"side={pos.get('side')}"
                    )
            else:
                logger.info("   ℹ️  No open positions on exchange")
            
        except Exception as e:
            error_msg = f"Exchange position query failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
            result.warnings.append("Cannot verify exchange state - proceeding with caution")
    
    async def _step_reconcile_positions(
        self,
        user_id: str,
        db_session: AsyncSession,
        result: StartupRecoveryResult
    ):
        """Reconcile DB vs exchange positions."""
        try:
            logger.info("   Step 3: Reconciling positions...")
            
            reconciliation = await self.reconciliation_service.reconcile_positions(
                user_id=user_id,
                db_session=db_session,
                auto_repair=True
            )
            
            result.positions_repaired = reconciliation.repaired_count
            
            if reconciliation.is_synced:
                logger.info("   ✅ All positions synchronized")
            else:
                logger.warning(
                    f"   ⚠️  Reconciliation found issues: "
                    f"{len(reconciliation.orphaned_positions)} orphaned, "
                    f"{len(reconciliation.ghost_positions)} ghost"
                )
                result.warnings.append(
                    f"Position mismatch detected: {reconciliation.to_dict()}"
                )
            
        except Exception as e:
            error_msg = f"Position reconciliation failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
    
    async def _step_rebuild_state_machines(self, result: StartupRecoveryResult):
        """Reset state validator to clean state."""
        try:
            logger.info("   Step 4: Rebuilding state machines...")
            
            # Reset state validator to IDLE
            state_validator.current_state = None
            state_validator.transition_log.clear()
            
            logger.info("   ✅ State machines reset to initial state")
            
        except Exception as e:
            error_msg = f"State machine rebuild failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
    
    async def _step_restart_monitors(
        self,
        user_id: str,
        db_session: AsyncSession,
        result: StartupRecoveryResult
    ):
        """Restart position monitors for all open positions."""
        try:
            logger.info("   Step 5: Restarting position monitors...")
            
            # Get open positions from DB
            stmt = select(PaperTrades).where(
                PaperTrades.user_id == user_id,
                PaperTrades.status == 'open'
            )
            
            query_result = await db_session.execute(stmt)
            trades = query_result.scalars().all()
            
            for trade in trades:
                try:
                    await self.position_monitor.start_monitoring(
                        trade_id=trade.id,
                        symbol=trade.symbol,
                        side=trade.side,
                        entry_price=trade.entry_price,
                        quantity=trade.qty,
                        stop_loss=None,  # TODO: Load from strategy config
                        take_profit=None,  # TODO: Load from strategy config
                        db_session=db_session
                    )
                    result.monitors_restarted += 1
                    
                except Exception as e:
                    logger.error(f"Failed to restart monitor for {trade.id}: {e}")
                    result.warnings.append(f"Monitor restart failed for {trade.id}")
            
            if result.monitors_restarted > 0:
                logger.info(f"   ✅ Restarted {result.monitors_restarted} position monitors")
            else:
                logger.info("   ℹ️  No monitors to restart")
            
        except Exception as e:
            error_msg = f"Monitor restart failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
    
    async def _step_health_check(self, result: StartupRecoveryResult):
        """Perform comprehensive health check."""
        try:
            logger.info("   Step 6: Running health check...")
            
            # Check circuit breaker state
            health = await self.circuit_breaker.check_system_health()
            
            if not health.can_trade:
                error_msg = f"Circuit breaker blocking trading: {health.reason}"
                logger.error(error_msg)
                result.errors.append(error_msg)
            else:
                logger.info(f"   ✅ Circuit breaker healthy (state={health.state})")
            
            # Check exchange connectivity
            try:
                ticker = await self.exchange_manager.fetch_ticker("BTC/USDT")
                logger.info(f"   ✅ Exchange API responsive (BTC=${ticker['last_price']:.2f})")
            except Exception as e:
                error_msg = f"Exchange API unresponsive: {str(e)}"
                logger.error(error_msg)
                result.errors.append(error_msg)
            
        except Exception as e:
            error_msg = f"Health check failed: {str(e)}"
            logger.error(error_msg)
            result.errors.append(error_msg)
    
    async def _send_recovery_notification(self, result: StartupRecoveryResult):
        """Send Telegram notification about recovery status."""
        try:
            if result.can_resume_trading:
                message = (
                    f"✅ **System Recovery Complete**\n\n"
                    f"Recovery Time: {result.recovery_time_seconds:.2f}s\n"
                    f"DB Positions: {result.db_positions_loaded}\n"
                    f"Exchange Positions: {result.exchange_positions_found}\n"
                    f"Positions Repaired: {result.positions_repaired}\n"
                    f"Monitors Restarted: {result.monitors_restarted}\n\n"
                    f"Status: **TRADING RESUMED**"
                )
            else:
                message = (
                    f"⚠️ **System Recovery Completed with Issues**\n\n"
                    f"Recovery Time: {result.recovery_time_seconds:.2f}s\n"
                    f"Errors: {len(result.errors)}\n"
                    f"Warnings: {len(result.warnings)}\n\n"
                    f"Status: **TRADING BLOCKED**\n\n"
                    f"Errors:\n" + "\n".join(f"- {e}" for e in result.errors[:5])
                )
            
            await self.notifier.send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send recovery notification: {e}")
    
    async def quick_health_check(self) -> Dict[str, Any]:
        """
        Quick health check without full recovery.
        
        Returns:
            Health status dictionary
        """
        try:
            # Check circuit breaker
            cb_health = await self.circuit_breaker.check_system_health()
            
            # Check exchange connectivity
            try:
                ticker = await self.exchange_manager.fetch_ticker("BTC/USDT")
                exchange_ok = True
                btc_price = ticker['last_price']
            except:
                exchange_ok = False
                btc_price = None
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'circuit_breaker': {
                    'state': cb_health.state,
                    'can_trade': cb_health.can_trade,
                    'reason': cb_health.reason
                },
                'exchange_api': {
                    'connected': exchange_ok,
                    'btc_price': btc_price
                },
                'position_monitor': {
                    'monitored_count': self.position_monitor.get_monitored_count()
                }
            }
            
        except Exception as e:
            logger.error(f"Quick health check failed: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
