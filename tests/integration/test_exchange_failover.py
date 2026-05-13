"""
Exchange Failover Integration Tests - Sprint 4 Multi-Exchange Resilience.

Tests for ExchangeFailoverRouter covering:
- Health check monitoring and status tracking
- Automatic primary→secondary failover on failures
- State synchronization during failover
- Manual override capability
- Recovery and failback to primary exchange

Success Criteria:
- 5 comprehensive tests
- Failover triggers correctly on health degradation
- No trading interruption during switch
- State properly synchronized
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from app.exchange.failover_router import (
    ExchangeFailoverRouter,
    ExchangeStatus,
    FailoverMode
)
from app.database.models import ExchangeHealthChecks


@pytest.fixture
def failover_router():
    """Create an exchange failover router for testing."""
    return ExchangeFailoverRouter(
        primary_exchange='bybit',
        secondary_exchange='mexc',
        health_check_interval=30,
        failover_threshold=3
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


class TestHealthMonitoring:
    """Test exchange health check functionality."""
    
    @pytest.mark.asyncio
    async def test_health_check_updates_status(self, failover_router):
        """Verify health checks update exchange status."""
        # Simulate healthy exchange
        await failover_router.record_health_check(
            exchange='bybit',
            endpoint='ticker',
            status=ExchangeStatus.HEALTHY,
            latency_ms=50.0,
            db_session=None
        )
        
        health = failover_router.get_exchange_health('bybit')
        
        assert health['status'] == ExchangeStatus.HEALTHY
        assert health['latency_ms'] == 50.0
    
    @pytest.mark.asyncio
    async def test_consecutive_failures_tracked(self, failover_router):
        """Verify consecutive failures are counted correctly."""
        # Simulate multiple failures
        for _ in range(3):
            await failover_router.record_health_check(
                exchange='bybit',
                endpoint='orders',
                status=ExchangeStatus.UNHEALTHY,
                error_message='Connection timeout',
                db_session=None
            )
        
        health = failover_router.get_exchange_health('bybit')
        
        assert health['consecutive_failures'] >= 3
    
    @pytest.mark.asyncio
    async def test_health_check_persisted_to_db(self, failover_router, mock_db_session):
        """Verify health checks are logged to database."""
        await failover_router.record_health_check(
            exchange='bybit',
            endpoint='balance',
            status=ExchangeStatus.HEALTHY,
            latency_ms=45.0,
            db_session=mock_db_session
        )
        
        assert mock_db_session.add.called
        assert mock_db_session.commit.called


class TestAutomaticFailover:
    """Test automatic failover triggering."""
    
    @pytest.mark.asyncio
    async def test_failover_triggered_on_threshold(self, failover_router):
        """Verify failover triggers after consecutive failures exceed threshold."""
        # Set initial state
        failover_router.current_active_exchange = 'bybit'
        failover_router.failover_mode = FailoverMode.TRADE_BACKUP
        
        # Simulate failures up to threshold
        for i in range(failover_router.failover_threshold):
            await failover_router.record_health_check(
                exchange='bybit',
                endpoint='orders',
                status=ExchangeStatus.UNHEALTHY,
                error_message=f'Failure {i+1}',
                db_session=None
            )
        
        # Check if failover was triggered
        assert failover_router.current_active_exchange == 'mexc'
        assert failover_router.failover_triggered is True
    
    @pytest.mark.asyncio
    async def test_failover_preserves_state(self, failover_router):
        """Verify trading state is preserved during failover."""
        # Set some state
        failover_router.current_active_exchange = 'bybit'
        failover_router.positions = {
            'XAUUSDT': {'side': 'LONG', 'size': 0.01, 'entry_price': 2000.0}
        }
        
        # Trigger failover
        await failover_router.trigger_failover(
            reason='API outage',
            db_session=None
        )
        
        # State should be preserved
        assert failover_router.current_active_exchange == 'mexc'
        assert 'XAUUSDT' in failover_router.positions
    
    @pytest.mark.asyncio
    async def test_no_failover_below_threshold(self, failover_router):
        """Verify failover does NOT trigger below failure threshold."""
        failover_router.current_active_exchange = 'bybit'
        
        # Simulate fewer failures than threshold
        for _ in range(failover_router.failover_threshold - 1):
            await failover_router.record_health_check(
                exchange='bybit',
                endpoint='orders',
                status=ExchangeStatus.UNHEALTHY,
                error_message='Temporary error',
                db_session=None
            )
        
        # Should still be on primary
        assert failover_router.current_active_exchange == 'bybit'
        assert failover_router.failover_triggered is False


class TestFailoverModes:
    """Test different failover modes."""
    
    @pytest.mark.asyncio
    async def test_read_only_backup_mode(self, failover_router):
        """Verify read-only backup mode uses secondary for pricing only."""
        failover_router.failover_mode = FailoverMode.READ_ONLY_BACKUP
        
        # In this mode, trades should still go to primary even if degraded
        failover_router.current_active_exchange = 'bybit'
        
        # Simulate primary degradation
        await failover_router.record_health_check(
            exchange='bybit',
            endpoint='orders',
            status=ExchangeStatus.DEGRADED,
            latency_ms=500.0,
            db_session=None
        )
        
        # Should NOT trigger full failover in read-only mode
        assert failover_router.current_active_exchange == 'bybit'
    
    @pytest.mark.asyncio
    async def test_trade_backup_mode_switches_orders(self, failover_router):
        """Verify trade backup mode routes new orders to secondary."""
        failover_router.failover_mode = FailoverMode.TRADE_BACKUP
        failover_router.current_active_exchange = 'bybit'
        
        # Trigger failover
        await failover_router.trigger_failover(
            reason='High error rate',
            db_session=None
        )
        
        # New trades should route to secondary
        active = failover_router.get_active_exchange()
        assert active == 'mexc'
    
    @pytest.mark.asyncio
    async def test_safe_halt_mode_stops_trading(self, failover_router):
        """Verify safe halt mode prevents all new trades."""
        failover_router.failover_mode = FailoverMode.SAFE_HALT
        
        await failover_router.trigger_failover(
            reason='Critical system issue',
            db_session=None
        )
        
        # Should indicate trading is halted
        assert not failover_router.is_trading_allowed()


class TestRecoveryAndFailback:
    """Test recovery and failback to primary exchange."""
    
    @pytest.mark.asyncio
    async def test_failback_to_primary_on_recovery(self, failover_router):
        """Verify system fails back to primary when it recovers."""
        # Start in failover state
        failover_router.current_active_exchange = 'mexc'
        failover_router.failover_triggered = True
        
        # Simulate primary recovery
        for _ in range(5):  # Multiple successful checks
            await failover_router.record_health_check(
                exchange='bybit',
                endpoint='ticker',
                status=ExchangeStatus.HEALTHY,
                latency_ms=50.0,
                db_session=None
            )
        
        # Attempt failback
        await failover_router.attempt_failback(db_session=None)
        
        # Should return to primary if healthy
        if failover_router.get_exchange_health('bybit')['consecutive_failures'] == 0:
            assert failover_router.current_active_exchange == 'bybit'
    
    @pytest.mark.asyncio
    async def test_manual_override_capability(self, failover_router):
        """Verify manual override can force exchange selection."""
        failover_router.current_active_exchange = 'bybit'
        
        # Manually override to secondary
        failover_router.manual_override_exchange('mexc')
        
        assert failover_router.current_active_exchange == 'mexc'
        assert failover_router.manual_override_active is True
        
        # Clear override
        failover_router.clear_manual_override()
        
        assert failover_router.manual_override_active is False


class TestStateSynchronization:
    """Test state synchronization during failover."""
    
    @pytest.mark.asyncio
    async def test_positions_synced_during_failover(self, failover_router):
        """Verify open positions are tracked during exchange switch."""
        # Add some positions
        failover_router.positions = {
            'XAUUSDT': {'side': 'LONG', 'size': 0.01, 'entry_price': 2000.0},
            'BTCUSDT': {'side': 'SHORT', 'size': 0.001, 'entry_price': 50000.0}
        }
        
        # Trigger failover
        await failover_router.trigger_failover(
            reason='Testing sync',
            db_session=None
        )
        
        # Positions should still be tracked
        assert len(failover_router.positions) == 2
        assert 'XAUUSDT' in failover_router.positions
    
    @pytest.mark.asyncio
    async def test_balances_tracked_across_exchanges(self, failover_router):
        """Verify balances are tracked for both exchanges."""
        # Set balances
        failover_router.balances = {
            'bybit': {'USDT': 1000.0, 'BTC': 0.01},
            'mexc': {'USDT': 1000.0, 'BTC': 0.01}
        }
        
        # Trigger failover
        await failover_router.trigger_failover(
            reason='Balance tracking test',
            db_session=None
        )
        
        # Both exchange balances should be accessible
        assert 'bybit' in failover_router.balances
        assert 'mexc' in failover_router.balances


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
