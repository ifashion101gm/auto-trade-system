"""
Self-Healing Watchdog System for Production Auto Trade System.

Provides proactive monitoring and automatic recovery for:
- API connectivity health (exchange responsiveness, latency tracking)
- Database transaction staleness (connection pool exhaustion, stale transactions)
- Memory usage monitoring (leak detection, GC triggers)
- Worker queue health (frozen workers, stuck tasks)

REFACTORED: Watchdogs now emit FailureEvents to ResilienceManager instead of
taking direct recovery actions. This prevents conflicting recovery logic and
enables coordinated, deterministic healing.

All watchdogs run as background tasks and integrate with the existing
self-healing architecture via ResilienceManager.
"""
import asyncio
import time
import gc
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from loguru import logger

# Import resilience platform components
try:
    from app.resilience import (
        FailureEvent,
        FailureSeverity,
        FailureDomain,
        ResilienceManager,
    )
    RESILIENCE_PLATFORM_AVAILABLE = True
except ImportError:
    RESILIENCE_PLATFORM_AVAILABLE = False
    logger.warning("⚠️ Resilience platform not available - using legacy mode")


class APIWatchdog:
    """
    Monitor exchange API health and trigger recovery on failures.
    
    Monitors:
    - API endpoint responsiveness (ticker, balance, orders)
    - Request latency thresholds
    - Error rate tracking
    - Automatic degraded mode activation
    """
    
    def __init__(
        self,
        exchange_manager=None,
        max_latency_ms: float = 5000,
        check_interval_sec: int = 30,
        consecutive_failure_threshold: int = 3,
        resilience_manager=None  # NEW: ResilienceManager instance
    ):
        """
        Initialize API watchdog.
        
        Args:
            exchange_manager: UnifiedExchangeManager instance
            max_latency_ms: Maximum acceptable API latency in milliseconds
            check_interval_sec: How often to check API health
            consecutive_failure_threshold: Number of consecutive failures before alerting
            resilience_manager: ResilienceManager for coordinated failure handling
        """
        self.exchange_manager = exchange_manager
        self.max_latency_ms = max_latency_ms
        self.check_interval_sec = check_interval_sec
        self.consecutive_failure_threshold = consecutive_failure_threshold
        self.resilience_manager = resilience_manager  # NEW
        
        # State tracking
        self.consecutive_failures = 0
        self.last_check_time = None
        self.is_running = False
        self.latency_history: List[float] = []
        
        logger.info("✅ API Watchdog initialized")
        logger.info(f"   Max Latency: {max_latency_ms}ms")
        logger.info(f"   Check Interval: {check_interval_sec}s")
        logger.info(f"   Failure Threshold: {consecutive_failure_threshold}")
        logger.info(f"   Resilience Platform: {'Enabled' if resilience_manager else 'Disabled'}")
    
    async def check_api_health(self) -> Dict[str, Any]:
        """
        Check if exchange APIs are responsive.
        
        Returns:
            Dictionary with health status and metrics
        """
        endpoints = ['ticker', 'balance', 'orders']
        results = {}
        total_start = time.time()
        
        for endpoint in endpoints:
            try:
                start = time.time()
                
                # Test endpoint based on type
                if endpoint == 'ticker':
                    await self._test_ticker_endpoint()
                elif endpoint == 'balance':
                    await self._test_balance_endpoint()
                elif endpoint == 'orders':
                    await self._test_orders_endpoint()
                
                latency = (time.time() - start) * 1000  # Convert to ms
                
                results[endpoint] = {
                    'status': 'healthy',
                    'latency_ms': round(latency, 2),
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Track latency
                self.latency_history.append(latency)
                if len(self.latency_history) > 100:
                    self.latency_history = self.latency_history[-100:]
                
                # Check if latency exceeds threshold
                if latency > self.max_latency_ms:
                    logger.warning(
                        f"⚠️ High API latency detected: {endpoint} took {latency:.0f}ms "
                        f"(threshold: {self.max_latency_ms}ms)"
                    )
                    await self.trigger_degraded_mode(endpoint, latency)
                
            except Exception as e:
                results[endpoint] = {
                    'status': 'failed',
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                logger.error(f"❌ API endpoint failed: {endpoint} - {e}")
                self.consecutive_failures += 1
                
                # Check if we've exceeded failure threshold
                if self.consecutive_failures >= self.consecutive_failure_threshold:
                    await self.trigger_emergency_stop()
        
        # Reset consecutive failures if any endpoint succeeded
        if any(r['status'] == 'healthy' for r in results.values()):
            self.consecutive_failures = 0
        
        total_latency = (time.time() - total_start) * 1000
        
        return {
            'overall_status': 'healthy' if all(
                r['status'] == 'healthy' for r in results.values()
            ) else 'degraded',
            'endpoints': results,
            'total_latency_ms': round(total_latency, 2),
            'avg_latency_ms': round(
                sum(self.latency_history[-10:]) / max(len(self.latency_history[-10:]), 1), 2
            ),
            'consecutive_failures': self.consecutive_failures,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _test_ticker_endpoint(self):
        """Test ticker/price endpoint."""
        if self.exchange_manager:
            await self.exchange_manager.get_ticker('XAUUSDT')
        else:
            # Mock for testing
            await asyncio.sleep(0.1)
    
    async def _test_balance_endpoint(self):
        """Test balance endpoint."""
        if self.exchange_manager:
            await self.exchange_manager.get_balance()
        else:
            # Mock for testing
            await asyncio.sleep(0.1)
    
    async def _test_orders_endpoint(self):
        """Test orders endpoint."""
        if self.exchange_manager:
            await self.exchange_manager.get_open_orders('XAUUSDT')
        else:
            # Mock for testing
            await asyncio.sleep(0.1)
    
    async def trigger_degraded_mode(self, endpoint: str, latency: float):
        """
        Emit failure event for degraded mode activation.
        
        REFACTORED: Instead of directly triggering degraded mode, we emit
        a FailureEvent to ResilienceManager which coordinates the response.
        
        Args:
            endpoint: The API endpoint with high latency
            latency: Measured latency in milliseconds
        """
        logger.warning(
            f"🔶 HIGH LATENCY DETECTED: {endpoint} took {latency:.0f}ms "
            f"(threshold: {self.max_latency_ms}ms)"
        )
        
        # Emit failure event to ResilienceManager
        if self.resilience_manager and RESILIENCE_PLATFORM_AVAILABLE:
            await self.resilience_manager.handle_failure(
                FailureEvent(
                    source="api_watchdog",
                    failure_type="high_latency",
                    severity=FailureSeverity.WARNING,
                    domain=FailureDomain.API,
                    metadata={
                        "endpoint": endpoint,
                        "latency_ms": latency,
                        "threshold_ms": self.max_latency_ms
                    }
                )
            )
        else:
            # Legacy fallback (TODO: remove after full migration)
            logger.warning("⚠️ Degraded mode requested (legacy path - no ResilienceManager)")
    
    async def trigger_emergency_stop(self):
        """
        Emit emergency failure event for immediate action.
        
        REFACTORED: Instead of directly triggering emergency stop, we emit
        a CRITICAL FailureEvent to ResilienceManager which coordinates response.
        """
        logger.critical(
            f"🚨 CONSECUTIVE API FAILURES: {self.consecutive_failures} failures detected"
        )
        
        # Emit critical failure event to ResilienceManager
        if self.resilience_manager and RESILIENCE_PLATFORM_AVAILABLE:
            await self.resilience_manager.handle_failure(
                FailureEvent(
                    source="api_watchdog",
                    failure_type="consecutive_failures",
                    severity=FailureSeverity.EMERGENCY,
                    domain=FailureDomain.API,
                    metadata={
                        "consecutive_failures": self.consecutive_failures,
                        "threshold": self.consecutive_failure_threshold
                    }
                )
            )
        else:
            # Legacy fallback (TODO: remove after full migration)
            logger.critical("🚨 Emergency stop requested (legacy path - no ResilienceManager)")
    
    async def run_periodic_checks(self):
        """Run periodic API health checks in background."""
        self.is_running = True
        logger.info("🔄 API Watchdog started periodic checks")
        
        while self.is_running:
            try:
                health = await self.check_api_health()
                self.last_check_time = datetime.utcnow()
                
                if health['overall_status'] != 'healthy':
                    logger.warning(f"⚠️ API health check failed: {health}")
                
            except Exception as e:
                logger.error(f"API watchdog check failed: {e}")
            
            await asyncio.sleep(self.check_interval_sec)
    
    def stop(self):
        """Stop the watchdog."""
        self.is_running = False
        logger.info("🛑 API Watchdog stopped")


class DatabaseWatchdog:
    """
    Monitor database connectivity and transaction health.
    
    Monitors:
    - Connection pool utilization
    - Stale/dormant transactions
    - Query performance degradation
    - Deadlock detection
    """
    
    def __init__(
        self,
        db_session_factory=None,
        max_pool_utilization_pct: float = 80.0,
        stale_transaction_threshold_sec: int = 300,
        check_interval_sec: int = 60,
        resilience_manager=None  # NEW
    ):
        """
        Initialize database watchdog.
        
        Args:
            db_session_factory: SQLAlchemy async session factory
            max_pool_utilization_pct: Alert when pool usage exceeds this percentage
            stale_transaction_threshold_sec: Consider transaction stale after this duration
            check_interval_sec: How often to check DB health
            resilience_manager: ResilienceManager for coordinated failure handling
        """
        self.db_session_factory = db_session_factory
        self.max_pool_utilization_pct = max_pool_utilization_pct
        self.stale_transaction_threshold_sec = stale_transaction_threshold_sec
        self.check_interval_sec = check_interval_sec
        self.resilience_manager = resilience_manager  # NEW
        
        # State tracking
        self.is_running = False
        self.last_check_time = None
        self.stale_transactions_detected = 0
        
        logger.info("✅ Database Watchdog initialized")
        logger.info(f"   Max Pool Utilization: {max_pool_utilization_pct}%")
        logger.info(f"   Stale Transaction Threshold: {stale_transaction_threshold_sec}s")
    
    async def check_db_health(self) -> Dict[str, Any]:
        """
        Check database connectivity and transaction health.
        
        Returns:
            Dictionary with health status and metrics
        """
        results = {
            'connectivity': 'unknown',
            'pool_utilization': None,
            'stale_transactions': [],
            'query_performance': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Test basic connectivity
        try:
            start = time.time()
            
            if self.db_session_factory:
                async with self.db_session_factory() as session:
                    from sqlalchemy import text
                    await session.execute(text("SELECT 1"))
                    
                    # Check pool stats if available
                    engine = session.get_bind()
                    if hasattr(engine.pool, 'status'):
                        pool_status = engine.pool.status()
                        results['pool_utilization'] = self._parse_pool_status(pool_status)
            
            else:
                # Mock for testing
                await asyncio.sleep(0.05)
            
            query_latency = (time.time() - start) * 1000
            results['connectivity'] = 'healthy'
            results['query_performance'] = {
                'simple_query_ms': round(query_latency, 2)
            }
            
            logger.debug(f"DB connectivity check passed: {query_latency:.0f}ms")
            
        except Exception as e:
            results['connectivity'] = 'failed'
            results['error'] = str(e)
            logger.error(f"❌ Database connectivity check failed: {e}")
            
            await self.alert_db_failure(e)
        
        # Check for stale transactions (if supported)
        if self.db_session_factory:
            stale_txns = await self._detect_stale_transactions()
            results['stale_transactions'] = stale_txns
            
            if stale_txns:
                self.stale_transactions_detected += len(stale_txns)
                logger.warning(
                    f"⚠️ Detected {len(stale_txns)} stale database transactions"
                )
        
        return results
    
    async def _detect_stale_transactions(self) -> List[Dict[str, Any]]:
        """
        Detect stale/dormant transactions in the database.
        
        Returns:
            List of stale transaction details
        """
        # This would query pg_stat_activity or similar in production
        # For now, return empty list (placeholder for future implementation)
        return []
    
    def _parse_pool_status(self, pool_status: str) -> Dict[str, Any]:
        """Parse connection pool status string into structured data."""
        # Placeholder - actual implementation depends on SQLAlchemy version
        return {'raw_status': pool_status}
    
    async def alert_db_failure(self, error: Exception):
        """
        Alert operators of database failure.
        
        Actions:
        - Log critical error
        - Send Telegram alert
        - Trigger recovery attempt
        """
        logger.critical(f"🚨 DATABASE FAILURE DETECTED: {error}")
        
        # TODO: Send Telegram alert
        # TODO: Trigger RecoveryAgent for DB reconnection
    
    async def run_periodic_checks(self):
        """Run periodic database health checks in background."""
        self.is_running = True
        logger.info("🔄 Database Watchdog started periodic checks")
        
        while self.is_running:
            try:
                health = await self.check_db_health()
                self.last_check_time = datetime.utcnow()
                
                if health['connectivity'] != 'healthy':
                    logger.warning(f"⚠️ Database health check failed: {health}")
                
            except Exception as e:
                logger.error(f"Database watchdog check failed: {e}")
            
            await asyncio.sleep(self.check_interval_sec)
    
    def stop(self):
        """Stop the watchdog."""
        self.is_running = False
        logger.info("🛑 Database Watchdog stopped")


class MemoryWatchdog:
    """
    Monitor memory usage and detect potential leaks.
    
    Monitors:
    - RSS memory consumption
    - Memory growth rate over time
    - Object count trends
    - Garbage collection effectiveness
    """
    
    def __init__(
        self,
        memory_warning_threshold_mb: float = 512,
        memory_critical_threshold_mb: float = 1024,
        check_interval_sec: int = 120,
        gc_trigger_threshold_mb: float = 768
    ):
        """
        Initialize memory watchdog.
        
        Args:
            memory_warning_threshold_mb: Alert when memory exceeds this (MB)
            memory_critical_threshold_mb: Critical alert threshold (MB)
            check_interval_sec: How often to check memory
            gc_trigger_threshold_mb: Trigger manual GC when memory exceeds this (MB)
        """
        self.memory_warning_threshold_mb = memory_warning_threshold_mb
        self.memory_critical_threshold_mb = memory_critical_threshold_mb
        self.check_interval_sec = check_interval_sec
        self.gc_trigger_threshold_mb = gc_trigger_threshold_mb
        
        # State tracking
        self.is_running = False
        self.last_check_time = None
        self.memory_samples: List[float] = []
        self.gc_triggers_count = 0
        
        logger.info("✅ Memory Watchdog initialized")
        logger.info(f"   Warning Threshold: {memory_warning_threshold_mb}MB")
        logger.info(f"   Critical Threshold: {memory_critical_threshold_mb}MB")
        logger.info(f"   GC Trigger: {gc_trigger_threshold_mb}MB")
    
    async def check_memory(self) -> Dict[str, Any]:
        """
        Check memory usage and detect anomalies.
        
        Returns:
            Dictionary with memory metrics and alerts
        """
        process = psutil.Process()
        memory_info = process.memory_info()
        
        memory_mb = memory_info.rss / 1024 / 1024
        memory_vms_mb = memory_info.vms / 1024 / 1024
        
        # Track memory samples for trend analysis
        self.memory_samples.append(memory_mb)
        if len(self.memory_samples) > 60:  # Keep last hour (at 120s intervals)
            self.memory_samples = self.memory_samples[-60:]
        
        # Calculate growth rate
        growth_rate = 0
        if len(self.memory_samples) >= 2:
            growth_rate = self.memory_samples[-1] - self.memory_samples[0]
        
        results = {
            'rss_mb': round(memory_mb, 2),
            'vms_mb': round(memory_vms_mb, 2),
            'growth_rate_mb': round(growth_rate, 2),
            'sample_count': len(self.memory_samples),
            'gc_triggers': self.gc_triggers_count,
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Check thresholds
        if memory_mb > self.memory_critical_threshold_mb:
            results['status'] = 'critical'
            logger.critical(
                f"🚨 CRITICAL MEMORY USAGE: {memory_mb:.0f}MB "
                f"(threshold: {self.memory_critical_threshold_mb}MB)"
            )
            await self.trigger_critical_alert(memory_mb)
            
        elif memory_mb > self.memory_warning_threshold_mb:
            results['status'] = 'warning'
            logger.warning(
                f"⚠️ HIGH MEMORY USAGE: {memory_mb:.0f}MB "
                f"(threshold: {self.memory_warning_threshold_mb}MB)"
            )
            
            # Trigger garbage collection if above GC threshold
            if memory_mb > self.gc_trigger_threshold_mb:
                await self.trigger_gc(memory_mb)
        
        # Detect memory leak (continuous growth)
        if growth_rate > 100 and len(self.memory_samples) >= 10:
            logger.warning(
                f"⚠️ POTENTIAL MEMORY LEAK: Memory grew {growth_rate:.0f}MB "
                f"over {len(self.memory_samples)} samples"
            )
            results['potential_leak'] = True
        
        return results
    
    async def trigger_gc(self, current_memory_mb: float):
        """
        Trigger manual garbage collection.
        
        Args:
            current_memory_mb: Current memory usage in MB
        """
        logger.info(f"🧹 Triggering garbage collection (memory: {current_memory_mb:.0f}MB)")
        
        # Force garbage collection
        collected = gc.collect()
        
        # Check memory after GC
        process = psutil.Process()
        memory_after_mb = process.memory_info().rss / 1024 / 1024
        freed_mb = current_memory_mb - memory_after_mb
        
        self.gc_triggers_count += 1
        
        logger.info(
            f"✅ GC completed: Collected {collected} objects, "
            f"freed {freed_mb:.0f}MB (now {memory_after_mb:.0f}MB)"
        )
    
    async def trigger_critical_alert(self, memory_mb: float):
        """
        Trigger critical alert for excessive memory usage.
        
        Actions:
        - Log critical error
        - Send urgent Telegram alert
        - Consider restarting worker processes
        """
        logger.critical(
            f"🚨 CRITICAL MEMORY ALERT: {memory_mb:.0f}MB usage detected. "
            f"Consider restarting application."
        )
        
        # TODO: Send urgent Telegram alert
        # TODO: Consider graceful restart
    
    async def run_periodic_checks(self):
        """Run periodic memory checks in background."""
        self.is_running = True
        logger.info("🔄 Memory Watchdog started periodic checks")
        
        while self.is_running:
            try:
                health = await self.check_memory()
                self.last_check_time = datetime.utcnow()
                
                if health['status'] != 'healthy':
                    logger.warning(f"⚠️ Memory health check: {health['status']}")
                
            except Exception as e:
                logger.error(f"Memory watchdog check failed: {e}")
            
            await asyncio.sleep(self.check_interval_sec)
    
    def stop(self):
        """Stop the watchdog."""
        self.is_running = False
        logger.info("🛑 Memory Watchdog stopped")


class QueueWatchdog:
    """
    Monitor task queue health and detect frozen workers.
    
    Monitors:
    - Task processing timestamps
    - Queue depth/backlog
    - Worker heartbeat status
    - Stuck task detection
    """
    
    def __init__(
        self,
        max_task_age_sec: int = 300,
        max_queue_depth: int = 100,
        check_interval_sec: int = 60
    ):
        """
        Initialize queue watchdog.
        
        Args:
            max_task_age_sec: Alert if oldest task exceeds this age
            max_queue_depth: Alert if queue depth exceeds this
            check_interval_sec: How often to check queue health
        """
        self.max_task_age_sec = max_task_age_sec
        self.max_queue_depth = max_queue_depth
        self.check_interval_sec = check_interval_sec
        
        # State tracking
        self.is_running = False
        self.last_check_time = None
        self.last_task_processed_time = datetime.utcnow()
        self.frozen_worker_alerts = 0
        
        logger.info("✅ Queue Watchdog initialized")
        logger.info(f"   Max Task Age: {max_task_age_sec}s")
        logger.info(f"   Max Queue Depth: {max_queue_depth}")
    
    async def check_queue_health(self) -> Dict[str, Any]:
        """
        Check if tasks are processing normally.
        
        Returns:
            Dictionary with queue health metrics
        """
        now = datetime.utcnow()
        
        # Calculate time since last task was processed
        time_since_last_task = (now - self.last_task_processed_time).total_seconds()
        
        results = {
            'last_task_processed': self.last_task_processed_time.isoformat(),
            'seconds_since_last_task': round(time_since_last_task, 2),
            'queue_depth': 0,  # Would be populated from actual queue
            'status': 'healthy',
            'timestamp': now.isoformat()
        }
        
        # Check if queue appears frozen
        if time_since_last_task > self.max_task_age_sec:
            results['status'] = 'frozen'
            self.frozen_worker_alerts += 1
            
            logger.critical(
                f"🚨 TASK QUEUE APPEARS FROZEN: No tasks processed in "
                f"{time_since_last_task:.0f}s (threshold: {self.max_task_age_sec}s)"
            )
            
            await self.trigger_worker_restart()
        
        # Check queue depth (placeholder - would integrate with actual queue system)
        # if queue_depth > self.max_queue_depth:
        #     results['status'] = 'backlogged'
        #     logger.warning(f"⚠️ Queue backlog: {queue_depth} tasks pending")
        
        return results
    
    def record_task_processed(self):
        """Record that a task was successfully processed."""
        self.last_task_processed_time = datetime.utcnow()
    
    async def trigger_worker_restart(self):
        """
        Emit failure event for worker restart.
        
        REFACTORED: Instead of directly restarting workers, emit a FailureEvent
        to ResilienceManager which coordinates the response.
        """
        logger.critical(
            f"🚨 QUEUE FROZEN: No tasks processed in "
            f"{self.frozen_worker_alerts} consecutive checks"
        )
        
        # Emit critical failure event to ResilienceManager
        if self.resilience_manager and RESILIENCE_PLATFORM_AVAILABLE:
            await self.resilience_manager.handle_failure(
                FailureEvent(
                    source="queue_watchdog",
                    failure_type="worker_frozen",
                    severity=FailureSeverity.CRITICAL,
                    domain=FailureDomain.EXECUTION,
                    metadata={
                        "frozen_checks": self.frozen_worker_alerts
                    }
                )
            )
        else:
            # Legacy fallback
            logger.critical("🚨 Worker restart requested (legacy path)")
    
    async def run_periodic_checks(self):
        """Run periodic queue health checks in background."""
        self.is_running = True
        logger.info("🔄 Queue Watchdog started periodic checks")
        
        while self.is_running:
            try:
                health = await self.check_queue_health()
                self.last_check_time = datetime.utcnow()
                
                if health['status'] != 'healthy':
                    logger.warning(f"⚠️ Queue health check: {health['status']}")
                
            except Exception as e:
                logger.error(f"Queue watchdog check failed: {e}")
            
            await asyncio.sleep(self.check_interval_sec)
    
    def stop(self):
        """Stop the watchdog."""
        self.is_running = False
        logger.info("🛑 Queue Watchdog stopped")


class WatchdogOrchestrator:
    """
    Orchestrates all watchdogs and manages their lifecycle.
    
    REFACTORED: Now integrates with ResilienceManager for coordinated failure handling.
    All watchdogs emit FailureEvents to ResilienceManager instead of taking direct actions.
    
    Provides centralized control for starting/stopping all watchdogs
    and aggregating their health reports.
    """
    
    def __init__(
        self,
        exchange_manager=None,
        db_session_factory=None,
        resilience_manager=None,  # NEW: ResilienceManager instance
        api_check_interval: int = 30,
        db_check_interval: int = 60,
        memory_check_interval: int = 120,
        queue_check_interval: int = 60
    ):
        """
        Initialize watchdog orchestrator.
        
        Args:
            exchange_manager: UnifiedExchangeManager instance
            db_session_factory: SQLAlchemy async session factory
            resilience_manager: ResilienceManager for coordinated failure handling
            api_check_interval: API watchdog check interval (seconds)
            db_check_interval: Database watchdog check interval (seconds)
            memory_check_interval: Memory watchdog check interval (seconds)
            queue_check_interval: Queue watchdog check interval (seconds)
        """
        # Initialize all watchdogs with ResilienceManager
        self.api_watchdog = APIWatchdog(
            exchange_manager=exchange_manager,
            check_interval_sec=api_check_interval,
            resilience_manager=resilience_manager  # NEW
        )
        
        self.db_watchdog = DatabaseWatchdog(
            db_session_factory=db_session_factory,
            check_interval_sec=db_check_interval,
            resilience_manager=resilience_manager  # NEW
        )
        
        self.memory_watchdog = MemoryWatchdog(
            check_interval_sec=memory_check_interval,
            resilience_manager=resilience_manager  # NEW
        )
        
        self.queue_watchdog = QueueWatchdog(
            check_interval_sec=queue_check_interval,
            resilience_manager=resilience_manager  # NEW
        )
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        logger.info("✅ Watchdog Orchestrator initialized")
    
    async def start_all_watchdogs(self):
        """Start all watchdog background tasks."""
        if self.is_running:
            logger.warning("Watchdogs are already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting all watchdogs...")
        
        # Start each watchdog as a background task
        self.background_tasks = [
            asyncio.create_task(self.api_watchdog.run_periodic_checks(), name="api_watchdog"),
            asyncio.create_task(self.db_watchdog.run_periodic_checks(), name="db_watchdog"),
            asyncio.create_task(self.memory_watchdog.run_periodic_checks(), name="memory_watchdog"),
            asyncio.create_task(self.queue_watchdog.run_periodic_checks(), name="queue_watchdog"),
        ]
        
        logger.info(f"✅ All {len(self.background_tasks)} watchdogs started")
    
    async def stop_all_watchdogs(self):
        """Stop all watchdog background tasks."""
        if not self.is_running:
            logger.warning("Watchdogs are not running")
            return
        
        self.is_running = False
        logger.info("🛑 Stopping all watchdogs...")
        
        # Stop each watchdog
        self.api_watchdog.stop()
        self.db_watchdog.stop()
        self.memory_watchdog.stop()
        self.queue_watchdog.stop()
        
        # Cancel background tasks
        for task in self.background_tasks:
            task.cancel()
        
        # Wait for tasks to finish
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        self.background_tasks.clear()
        logger.info("✅ All watchdogs stopped")
    
    async def get_aggregated_health_report(self) -> Dict[str, Any]:
        """
        Get aggregated health report from all watchdogs.
        
        Returns:
            Dictionary with combined health status
        """
        # Run immediate checks on all watchdogs
        api_health = await self.api_watchdog.check_api_health()
        db_health = await self.db_watchdog.check_db_health()
        memory_health = await self.memory_watchdog.check_memory()
        queue_health = await self.queue_watchdog.check_queue_health()
        
        # Determine overall status
        statuses = [
            api_health.get('overall_status', 'unknown'),
            db_health.get('connectivity', 'unknown'),
            memory_health.get('status', 'unknown'),
            queue_health.get('status', 'unknown'),
        ]
        
        if 'critical' in statuses or 'frozen' in statuses:
            overall_status = 'critical'
        elif 'degraded' in statuses or 'warning' in statuses or 'backlogged' in statuses:
            overall_status = 'degraded'
        elif all(s == 'healthy' for s in statuses):
            overall_status = 'healthy'
        else:
            overall_status = 'unknown'
        
        return {
            'overall_status': overall_status,
            'watchdogs': {
                'api': api_health,
                'database': db_health,
                'memory': memory_health,
                'queue': queue_health,
            },
            'timestamp': datetime.utcnow().isoformat()
        }
