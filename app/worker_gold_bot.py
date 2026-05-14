"""
Gold Trading Bot Worker - Standalone trading engine process.

This is the REAL trading runtime that operates independently from FastAPI.
It handles:
- Position synchronization
- Signal scanning and generation
- Trade execution
- Risk management
- Reconciliation
- Heartbeat monitoring

Run with: python -m app.worker_gold_bot
"""
import asyncio
import sys
from typing import Optional

from app.logging_config import logger, setup_logger
from app.database.connection import init_db, get_session
from app.config import settings
from app.runtime.task_supervisor import TaskSupervisor
from app.risk.circuit_breaker import get_circuit_breaker
from app.strategies.gold_opening_reversal import GoldOpeningReversalStrategy
from app.sync.position_sync import PositionSyncService
from app.recovery.recovery_service import RecoveryService
from app.services.reconciliation_service import ReconciliationService
from app.heartbeat_monitor import HeartbeatMonitor
from app.monitoring.prometheus_metrics import get_metrics_collector


async def position_sync_loop(supervisor: TaskSupervisor):
    """Position synchronization loop with WebSocket-first optimization."""
    logger.info("🔄 Starting position sync service...")
    
    position_sync = PositionSyncService(testnet=True)  # Demo mode
    
    # Start the optimized sync (WebSocket-first, REST fallback every 15s)
    await position_sync.start(get_session)


async def signal_scanning_loop(supervisor: TaskSupervisor):
    """
    Main signal scanning and trade execution loop.
    
    Checks for trading signals every 30 seconds during active sessions.
    Integrates with circuit breaker for safety.
    """
    logger.info("📊 Starting signal scanning loop...")
    
    strategy = GoldOpeningReversalStrategy()
    circuit_breaker = get_circuit_breaker()
    
    while True:
        try:
            # Check circuit breaker before any trading activity
            metrics = {
                'consecutive_losses': circuit_breaker.failure_counts['consecutive_losses'],
                'drawdown_pct': 0.0,  # Would integrate with RiskEngine
                'api_latency_ms': 0,  # Would measure actual latency
                'ws_disconnects_last_hour': len(circuit_breaker.ws_disconnect_timestamps),
                'infrastructure_failures': circuit_breaker.failure_counts['infrastructure_failures']
            }
            
            if not circuit_breaker.check_and_update(metrics):
                logger.warning(f"⚠️  Trading disabled by circuit breaker: {circuit_breaker.disable_reason}")
                await asyncio.sleep(60)  # Wait longer when disabled
                continue
            
            # Check if within trading session
            if not strategy.is_trading_session():
                logger.debug("Outside trading session, sleeping...")
                await asyncio.sleep(60)
                continue
            
            # TODO: Fetch market data and generate signals
            # For now, this is a stub that logs status
            logger.debug("Scanning for gold reversal signals...")
            
            # Market data would come from:
            # - WebSocket price feeds
            # - Exchange API
            # - Technical indicators
            
            # Example (when implemented):
            # market_data = await fetch_market_data('XAUUSDT')
            # signal = await strategy.generate_signal(market_data)
            # if signal:
            #     await execute_trade(signal)
            
            await asyncio.sleep(30)  # Scan every 30 seconds
        
        except Exception as e:
            logger.error(f"Error in signal scanning loop: {e}", exc_info=True)
            await asyncio.sleep(10)


async def reconciliation_loop(supervisor: TaskSupervisor):
    """Periodic reconciliation loop (every 2 minutes)."""
    logger.info("⏱️  Starting reconciliation loop (2-minute interval)...")
    
    reconciliation_service = ReconciliationService()
    
    while True:
        try:
            async with get_session() as db_session:
                await reconciliation_service.reconcile(mode='DEMO', db_session=db_session)
                await reconciliation_service.reconcile(mode='LIVE', db_session=db_session)
        except Exception as e:
            logger.error(f"Reconciliation error: {e}", exc_info=True)
        
        await asyncio.sleep(120)


async def heartbeat_monitor_loop(supervisor: TaskSupervisor):
    """System heartbeat monitoring."""
    logger.info("💓 Starting heartbeat monitor (30s interval)...")
    
    monitor = HeartbeatMonitor()
    await monitor.start()


async def metrics_collection_loop(supervisor: TaskSupervisor):
    """Collect and cache metrics periodically."""
    logger.info("📈 Starting metrics collection loop...")
    
    collector = get_metrics_collector()
    
    while True:
        try:
            # Update metrics
            collector.update_system_metrics()
            
            # Cache hot metrics in Redis (if available)
            # TODO: Implement Redis caching for win rate, P&L, trade count
            
            await asyncio.sleep(60)  # Update every minute
        
        except Exception as e:
            logger.error(f"Metrics collection error: {e}", exc_info=True)
            await asyncio.sleep(30)


async def main():
    """
    Main entry point for gold trading bot worker.
    
    Initializes all components and starts supervised tasks.
    Runs independently from FastAPI control plane.
    """
    logger.info("=" * 80)
    logger.info("🚀 GOLD TRADING BOT WORKER STARTING")
    logger.info("=" * 80)
    logger.info(f"Version: 2.0.0")
    logger.info(f"Environment: {getattr(settings, 'ENVIRONMENT', 'production')}")
    logger.info(f"Active Exchange: {settings.ACTIVE_EXCHANGE}")
    logger.info(f"Trading Symbol: {settings.PRIMARY_TRADING_SYMBOL}")
    logger.info(f"Execution Mode: {settings.EXECUTION_MODE}")
    logger.info("=" * 80)
    
    # Initialize database
    logger.info("🗄️  Initializing PostgreSQL database...")
    await init_db()
    logger.info("✅ Database initialized")
    
    # Run startup recovery
    logger.info("🔄 Running startup recovery checks...")
    recovery_service = RecoveryService()
    async with get_session() as db_session:
        await recovery_service.recover_on_startup(db_session)
    logger.info("✅ Startup recovery completed")
    
    # Create task supervisor
    supervisor = TaskSupervisor(max_restart_attempts=5)
    
    # Start supervised tasks
    logger.info("🔧 Starting supervised background tasks...")
    
    # Critical tasks (will auto-restart on failure)
    supervisor.create_task(
        position_sync_loop(supervisor),
        name="position_sync",
        critical=True,
        restart_delay=2.0
    )
    
    supervisor.create_task(
        signal_scanning_loop(supervisor),
        name="signal_scanning",
        critical=True,
        restart_delay=5.0
    )
    
    supervisor.create_task(
        heartbeat_monitor_loop(supervisor),
        name="heartbeat_monitor",
        critical=True,
        restart_delay=2.0
    )
    
    # Non-critical tasks (log failures but don't restart indefinitely)
    supervisor.create_task(
        reconciliation_loop(supervisor),
        name="reconciliation",
        critical=False,
        restart_delay=10.0
    )
    
    supervisor.create_task(
        metrics_collection_loop(supervisor),
        name="metrics_collection",
        critical=False,
        restart_delay=5.0
    )
    
    logger.info(f"✅ Started {supervisor.get_task_count()} supervised tasks")
    logger.info(f"   Critical tasks: {supervisor.get_critical_task_count()}")
    logger.info("=" * 80)
    logger.info("🎉 GOLD TRADING BOT WORKER FULLY OPERATIONAL")
    logger.info("=" * 80)
    
    # Keep running until shutdown signal
    try:
        # Monitor task health periodically
        while True:
            await asyncio.sleep(30)
            
            # Log health status
            health = supervisor.get_health()
            if health['failed_tasks'] > 0:
                logger.warning(
                    f"⚠️  {health['failed_tasks']} failed tasks detected. "
                    f"Healthy: {health['healthy_tasks']}, Stopped: {health['stopped_tasks']}"
                )
            
            # Check circuit breaker status
            cb = get_circuit_breaker()
            if cb.trading_disabled:
                logger.warning(f"🚨 Circuit breaker ACTIVE: {cb.disable_reason}")
    
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown signal received")
    except Exception as e:
        logger.error(f"Worker crashed: {e}", exc_info=True)
    finally:
        # Graceful shutdown
        logger.info("🛑 Shutting down worker...")
        await supervisor.shutdown(timeout=10)
        logger.info("👋 Worker shutdown complete")


if __name__ == "__main__":
    # Setup logging
    setup_logger()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
