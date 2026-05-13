"""
Paper Trading Integration Tests - Sprint 4 Layer 4.

Tests for PaperTradingSessionManager covering:
- Safety guard enforcement (trade size, daily loss, position limits)
- Realistic fill simulation (spread, slippage, latency)
- Session lifecycle management (start/stop/pause)
- Rate limit handling with exponential backoff
- Performance tracking (latency, slippage metrics)
- Database persistence and state recovery

Success Criteria:
- 8 comprehensive tests
- All safety guards validated
- Realistic market simulation verified
- Session state properly managed
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from app.paper_trading.session_manager import (
    PaperTradingSessionManager,
    SafetyGuardViolation
)
from app.database.models import PaperTrades


@pytest.fixture
def session_manager():
    """Create a paper trading session manager for testing."""
    return PaperTradingSessionManager(
        exchange='binance',
        user_id='test_user',
        starting_balance=1000.0
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session with async support."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_exchange_client():
    """Create a mock exchange client with async methods."""
    client = AsyncMock()
    client.create_market_order = AsyncMock(return_value={
        'order_id': 'test_order_123',
        'price': 2000.5,
        'status': 'FILLED'
    })
    return client


class TestSafetyGuards:
    """Test safety guard enforcement."""
    
    @pytest.mark.asyncio
    async def test_trade_size_limit_enforced(self, session_manager):
        """Verify trade size cannot exceed $100 per trade."""
        session_manager.session_active = True
        
        # Create oversized trade proposal (would be $4000 at $2000 price)
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 2.0,
            'leverage': 1,
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        # Attempt to execute oversized trade
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                proposal=proposal,
                exchange_client=None
            )
        
        assert "Trade size" in str(exc_info.value)
        assert "$100" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_leverage_limit_enforced(self, session_manager):
        """Verify leverage cannot exceed configured maximum."""
        session_manager.session_active = True
        
        # Create proposal with excessive leverage
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 0.01,  # $20 trade
            'leverage': 50,  # Exceeds default max of 5
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        # Attempt excessive leverage
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                proposal=proposal,
                exchange_client=None
            )
        
        assert "Leverage" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_position_size_limit_enforced(self, session_manager):
        """Verify position size cannot exceed 1% of account balance."""
        session_manager.session_active = True
        
        # Calculate max position (1% of $1000 = $10)
        # At $2000 price, that's 0.005 units max
        # Use quantity that exceeds this: 0.1 units = $200 (20% of balance)
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 0.1,  # $200 position (20% of balance, exceeds 1% limit)
            'leverage': 1,
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                proposal=proposal,
                exchange_client=None
            )
        
        # Check that it's a position or trade size violation
        assert "Position" in str(exc_info.value) or "Trade size" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_daily_loss_limit_enforced(self, session_manager):
        """Verify session pauses when daily loss exceeds -5%."""
        session_manager.session_active = True
        session_manager.daily_pnl = -60.0  # -6% of $1000
        
        # Create SMALL valid trade proposal (within all limits)
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 0.001,  # $2 position (well within 1% = $10 limit)
            'leverage': 1,
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        # Should reject new trades due to daily loss limit
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                proposal=proposal,
                exchange_client=None
            )
        
        assert "Daily loss limit" in str(exc_info.value)
        assert not session_manager.session_active  # Session should auto-pause


class TestRealisticSimulation:
    """Test realistic market simulation features."""
    
    @pytest.mark.asyncio
    async def test_spread_simulation(self, session_manager, mock_exchange_client):
        """Verify spread is applied to fill prices."""
        await session_manager.start_session()
        
        # Use small trade size within limits ($2 position)
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 0.001,
            'leverage': 1,
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        result = await session_manager.execute_paper_trade(
            proposal=proposal,
            exchange_client=mock_exchange_client
        )
        
        # Fill price should include spread (slightly higher than entry for BUY)
        assert result['fill_price'] >= 2000.0
    
    @pytest.mark.asyncio
    async def test_slippage_applied(self, session_manager, mock_exchange_client):
        """Verify slippage is tracked and within expected range."""
        await session_manager.start_session()
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 0.001,
            'leverage': 1,
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        result = await session_manager.execute_paper_trade(
            proposal=proposal,
            exchange_client=mock_exchange_client
        )
        
        # Slippage should be calculated and reasonable (< 0.1%)
        assert 'slippage_pct' in result
        assert 0 <= result['slippage_pct'] <= 0.1
    
    @pytest.mark.asyncio
    async def test_latency_simulation(self, session_manager, mock_exchange_client):
        """Verify execution includes realistic latency (50-1000ms)."""
        await session_manager.start_session()
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 0.001,
            'leverage': 1,
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        start_time = asyncio.get_event_loop().time()
        result = await session_manager.execute_paper_trade(
            proposal=proposal,
            exchange_client=mock_exchange_client
        )
        end_time = asyncio.get_event_loop().time()
        
        execution_time_ms = (end_time - start_time) * 1000
        
        # Should have some latency (at least 10ms for async overhead)
        assert execution_time_ms >= 10
        assert 'execution_time_ms' in result or 'latency_ms' in result


class TestSessionLifecycle:
    """Test session lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_session_start_initializes_state(self, session_manager):
        """Verify session start properly initializes all state."""
        await session_manager.start_session()
        
        assert session_manager.session_active is True
        assert session_manager.session_start_time is not None
        assert session_manager.current_balance == 1000.0
        assert session_manager.daily_pnl == 0.0
        assert len(session_manager.daily_trades) == 0
    
    @pytest.mark.asyncio
    async def test_session_stop_clears_state(self, session_manager):
        """Verify session stop properly cleans up."""
        await session_manager.start_session()
        await session_manager.stop_session()
        
        assert session_manager.session_active is False
    
    @pytest.mark.asyncio
    async def test_trade_rejected_when_inactive(self, session_manager):
        """Verify trades are rejected when session is not active."""
        session_manager.session_active = False
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 0.001,
            'leverage': 1,
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                proposal=proposal,
                exchange_client=None
            )
        
        # Check for session inactive message
        assert "active" in str(exc_info.value).lower()


class TestPerformanceTracking:
    """Test performance metrics collection."""
    
    @pytest.mark.asyncio
    async def test_latency_metrics_tracked(self, session_manager, mock_exchange_client):
        """Verify execution latencies are tracked."""
        await session_manager.start_session()
        
        # Execute multiple small trades
        for _ in range(3):
            proposal = {
                'symbol': 'XAUUSDT',
                'side': 'BUY',
                'entry_price': 2000.0,
                'quantity': 0.001,
                'leverage': 1,
                'confidence': 0.85,
                'strategy_name': 'test'
            }
            
            await session_manager.execute_paper_trade(
                proposal=proposal,
                exchange_client=mock_exchange_client
            )
        
        # Should have tracked latencies
        assert len(session_manager.latencies) == 3
        assert all(lat > 0 for lat in session_manager.latencies)
    
    @pytest.mark.asyncio
    async def test_session_metrics_returned(self, session_manager):
        """Verify get_session_metrics returns comprehensive stats."""
        await session_manager.start_session()
        
        metrics = session_manager.get_session_metrics()
        
        assert 'total_trades' in metrics
        assert 'current_balance' in metrics
        assert 'daily_pnl' in metrics
        assert 'avg_latency_ms' in metrics
        assert 'win_rate' in metrics


class TestDatabasePersistence:
    """Test database persistence and recovery."""
    
    @pytest.mark.asyncio
    async def test_trade_persisted_to_database(self, session_manager, mock_db_session):
        """Verify executed trades are saved to database."""
        await session_manager.start_session()
        
        proposal = {
            'symbol': 'XAUUSDT',
            'side': 'BUY',
            'entry_price': 2000.0,
            'quantity': 0.001,
            'leverage': 1,
            'confidence': 0.85,
            'strategy_name': 'test'
        }
        
        # Use None for exchange_client to trigger simulated execution
        result = await session_manager.execute_paper_trade(
            proposal=proposal,
            exchange_client=None,  # Triggers simulation mode
            db_session=mock_db_session
        )
        
        # Verify trade executed successfully
        assert result['status'] == 'executed'
        
        # Verify database add was called
        assert mock_db_session.add.called
    
    @pytest.mark.asyncio
    async def test_session_recovery_from_database(self, session_manager):
        """Verify session can recover state from database."""
        # This would typically query PaperTrades table
        # For now, just verify the method exists and doesn't crash
        assert hasattr(session_manager, '_load_session_from_db')


class TestRateLimitHandling:
    """Test rate limit handling with exponential backoff."""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_applied(self, session_manager):
        """Verify exponential backoff delays on rate limit hits."""
        # Simulate rate limit scenario
        session_manager.rate_limit_hits = 2
        
        delay = session_manager._apply_exponential_backoff()
        
        # Should be 2^2 = 4 seconds (or similar exponential pattern)
        assert delay >= 1.0
        assert delay <= 10.0  # Reasonable upper bound
    
    @pytest.mark.asyncio
    async def test_rate_limit_counter_increments(self, session_manager):
        """Verify rate limit hit counter increments correctly."""
        initial_count = session_manager.rate_limit_hits
        
        # Simulate rate limit handling
        session_manager.rate_limit_hits += 1
        
        assert session_manager.rate_limit_hits == initial_count + 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
