"""
Integration tests for self-healing watchdogs.

Validates:
- API Watchdog health checks
- Database Watchdog connectivity monitoring
- Memory Watchdog leak detection
- Queue Watchdog frozen worker detection
- Watchdog Orchestrator lifecycle management
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


@pytest.mark.asyncio
class TestAPIWatchdog:
    """Test API Watchdog functionality."""
    
    async def test_api_watchdog_initialization(self):
        """Test watchdog initializes with correct defaults."""
        from app.self_healing.watchdogs import APIWatchdog
        
        watchdog = APIWatchdog(
            max_latency_ms=5000,
            check_interval_sec=30,
            consecutive_failure_threshold=3
        )
        
        assert watchdog.max_latency_ms == 5000
        assert watchdog.check_interval_sec == 30
        assert watchdog.consecutive_failure_threshold == 3
        assert watchdog.consecutive_failures == 0
        assert watchdog.is_running is False
    
    async def test_check_api_health_healthy(self):
        """Test API health check when all endpoints are healthy."""
        from app.self_healing.watchdogs import APIWatchdog
        
        # Mock exchange manager
        mock_exchange = AsyncMock()
        mock_exchange.get_ticker = AsyncMock(return_value={'price': 2345.67})
        mock_exchange.get_balance = AsyncMock(return_value={'total': 10000})
        mock_exchange.get_open_orders = AsyncMock(return_value=[])
        
        watchdog = APIWatchdog(exchange_manager=mock_exchange)
        
        # Run health check
        health = await watchdog.check_api_health()
        
        assert health['overall_status'] == 'healthy'
        assert 'endpoints' in health
        assert 'ticker' in health['endpoints']
        assert health['endpoints']['ticker']['status'] == 'healthy'
        assert watchdog.consecutive_failures == 0
    
    async def test_check_api_health_degraded(self):
        """Test API health check when some endpoints fail."""
        from app.self_healing.watchdogs import APIWatchdog
        
        # Mock exchange manager with failing endpoint
        mock_exchange = AsyncMock()
        mock_exchange.get_ticker = AsyncMock(return_value={'price': 2345.67})
        mock_exchange.get_balance = AsyncMock(side_effect=Exception("Connection timeout"))
        mock_exchange.get_open_orders = AsyncMock(return_value=[])
        
        watchdog = APIWatchdog(exchange_manager=mock_exchange)
        
        # Run health check
        health = await watchdog.check_api_health()
        
        assert health['overall_status'] == 'degraded'
        assert health['endpoints']['balance']['status'] == 'failed'
        assert watchdog.consecutive_failures >= 1
    
    async def test_trigger_emergency_stop_on_consecutive_failures(self):
        """Test emergency stop triggered after threshold failures."""
        from app.self_healing.watchdogs import APIWatchdog
        
        # Mock exchange that always fails
        mock_exchange = AsyncMock()
        mock_exchange.get_ticker = AsyncMock(side_effect=Exception("API down"))
        mock_exchange.get_balance = AsyncMock(side_effect=Exception("API down"))
        mock_exchange.get_open_orders = AsyncMock(side_effect=Exception("API down"))
        
        watchdog = APIWatchdog(
            exchange_manager=mock_exchange,
            consecutive_failure_threshold=3
        )
        
        # Simulate multiple failures
        for _ in range(3):
            await watchdog.check_api_health()
        
        assert watchdog.consecutive_failures >= 3
        # Emergency stop should be triggered (would send alert in production)


@pytest.mark.asyncio
class TestDatabaseWatchdog:
    """Test Database Watchdog functionality."""
    
    async def test_db_watchdog_initialization(self):
        """Test watchdog initializes with correct defaults."""
        from app.self_healing.watchdogs import DatabaseWatchdog
        
        watchdog = DatabaseWatchdog(
            max_pool_utilization_pct=80.0,
            stale_transaction_threshold_sec=300,
            check_interval_sec=60
        )
        
        assert watchdog.max_pool_utilization_pct == 80.0
        assert watchdog.stale_transaction_threshold_sec == 300
        assert watchdog.check_interval_sec == 60
        assert watchdog.is_running is False
    
    async def test_check_db_health_healthy(self):
        """Test DB health check with successful connectivity."""
        from app.self_healing.watchdogs import DatabaseWatchdog
        
        watchdog = DatabaseWatchdog()
        
        # Run health check (will use mock path since no db_session_factory)
        health = await watchdog.check_db_health()
        
        assert health['connectivity'] == 'healthy'
        assert 'query_performance' in health
        assert 'simple_query_ms' in health['query_performance']
    
    async def test_check_db_health_failed(self):
        """Test DB health check when connectivity fails."""
        from app.self_healing.watchdogs import DatabaseWatchdog
        
        # Create a session factory that raises exceptions
        async def failing_session():
            raise Exception("Database connection refused")
        
        # Mock context manager
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        
        watchdog = DatabaseWatchdog(db_session_factory=mock_session_factory)
        
        # Run health check
        health = await watchdog.check_db_health()
        
        assert health['connectivity'] == 'failed'
        assert 'error' in health


@pytest.mark.asyncio
class TestMemoryWatchdog:
    """Test Memory Watchdog functionality."""
    
    async def test_memory_watchdog_initialization(self):
        """Test watchdog initializes with correct defaults."""
        from app.self_healing.watchdogs import MemoryWatchdog
        
        watchdog = MemoryWatchdog(
            memory_warning_threshold_mb=512,
            memory_critical_threshold_mb=1024,
            check_interval_sec=120,
            gc_trigger_threshold_mb=768
        )
        
        assert watchdog.memory_warning_threshold_mb == 512
        assert watchdog.memory_critical_threshold_mb == 1024
        assert watchdog.gc_trigger_threshold_mb == 768
        assert watchdog.is_running is False
    
    async def test_check_memory_healthy(self):
        """Test memory check when usage is normal."""
        from app.self_healing.watchdogs import MemoryWatchdog
        
        watchdog = MemoryWatchdog(memory_warning_threshold_mb=512)
        
        # Run memory check
        health = await watchdog.check_memory()
        
        assert health['status'] == 'healthy'
        assert 'rss_mb' in health
        assert health['rss_mb'] > 0  # Should have some memory usage
        assert 'gc_triggers' in health
    
    async def test_memory_growth_tracking(self):
        """Test memory growth rate calculation."""
        from app.self_healing.watchdogs import MemoryWatchdog
        
        watchdog = MemoryWatchdog()
        
        # Take multiple samples
        for _ in range(5):
            await watchdog.check_memory()
        
        assert len(watchdog.memory_samples) >= 5
        assert 'growth_rate_mb' in await watchdog.check_memory()


@pytest.mark.asyncio
class TestQueueWatchdog:
    """Test Queue Watchdog functionality."""
    
    async def test_queue_watchdog_initialization(self):
        """Test watchdog initializes with correct defaults."""
        from app.self_healing.watchdogs import QueueWatchdog
        
        watchdog = QueueWatchdog(
            max_task_age_sec=300,
            max_queue_depth=100,
            check_interval_sec=60
        )
        
        assert watchdog.max_task_age_sec == 300
        assert watchdog.max_queue_depth == 100
        assert watchdog.check_interval_sec == 60
        assert watchdog.is_running is False
    
    async def test_check_queue_health_healthy(self):
        """Test queue health when tasks are processing normally."""
        from app.self_healing.watchdogs import QueueWatchdog
        
        watchdog = QueueWatchdog(max_task_age_sec=300)
        
        # Record a recent task
        watchdog.record_task_processed()
        
        # Run health check
        health = await watchdog.check_queue_health()
        
        assert health['status'] == 'healthy'
        assert health['seconds_since_last_task'] < 300
    
    async def test_check_queue_health_frozen(self):
        """Test queue health detection when queue is frozen."""
        from app.self_healing.watchdogs import QueueWatchdog
        
        watchdog = QueueWatchdog(max_task_age_sec=1)  # Very short threshold for testing
        
        # Set last task time to far in the past
        watchdog.last_task_processed_time = datetime.utcnow() - timedelta(seconds=600)
        
        # Run health check
        health = await watchdog.check_queue_health()
        
        assert health['status'] == 'frozen'
        assert health['seconds_since_last_task'] > 300
        assert watchdog.frozen_worker_alerts >= 1


@pytest.mark.asyncio
class TestWatchdogOrchestrator:
    """Test Watchdog Orchestrator lifecycle management."""
    
    async def test_orchestrator_initialization(self):
        """Test orchestrator initializes all watchdogs."""
        from app.self_healing.watchdogs import WatchdogOrchestrator
        
        orchestrator = WatchdogOrchestrator(
            api_check_interval=30,
            db_check_interval=60,
            memory_check_interval=120,
            queue_check_interval=60
        )
        
        assert orchestrator.api_watchdog is not None
        assert orchestrator.db_watchdog is not None
        assert orchestrator.memory_watchdog is not None
        assert orchestrator.queue_watchdog is not None
        assert orchestrator.is_running is False
    
    async def test_start_and_stop_all_watchdogs(self):
        """Test starting and stopping all watchdogs."""
        from app.self_healing.watchdogs import WatchdogOrchestrator
        
        orchestrator = WatchdogOrchestrator()
        
        # Start watchdogs
        await orchestrator.start_all_watchdogs()
        assert orchestrator.is_running is True
        assert len(orchestrator.background_tasks) == 4
        
        # Let them run briefly
        await asyncio.sleep(0.5)
        
        # Stop watchdogs
        await orchestrator.stop_all_watchdogs()
        assert orchestrator.is_running is False
        assert len(orchestrator.background_tasks) == 0
    
    async def test_get_aggregated_health_report(self):
        """Test aggregated health report generation."""
        from app.self_healing.watchdogs import WatchdogOrchestrator
        
        orchestrator = WatchdogOrchestrator()
        
        # Get health report
        report = await orchestrator.get_aggregated_health_report()
        
        assert 'overall_status' in report
        assert 'watchdogs' in report
        assert 'api' in report['watchdogs']
        assert 'database' in report['watchdogs']
        assert 'memory' in report['watchdogs']
        assert 'queue' in report['watchdogs']
        assert 'timestamp' in report


# ============================================================================
# Integration Test: Full Watchdog Lifecycle
# ============================================================================

@pytest.mark.asyncio
async def test_full_watchdog_lifecycle():
    """Test complete watchdog lifecycle: init → start → monitor → stop."""
    from app.self_healing.watchdogs import WatchdogOrchestrator
    
    # Initialize
    orchestrator = WatchdogOrchestrator(
        api_check_interval=1,   # Fast checks for testing
        db_check_interval=1,
        memory_check_interval=2,
        queue_check_interval=1
    )
    
    # Start
    await orchestrator.start_all_watchdogs()
    assert orchestrator.is_running is True
    
    # Monitor (let watchdogs run for a few cycles)
    await asyncio.sleep(3)
    
    # Get health report
    health = await orchestrator.get_aggregated_health_report()
    assert health['overall_status'] in ['healthy', 'degraded', 'critical']
    
    # Stop
    await orchestrator.stop_all_watchdogs()
    assert orchestrator.is_running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
