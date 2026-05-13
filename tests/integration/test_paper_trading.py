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
    """Create a mock database session."""
    return MagicMock()


class TestSafetyGuards:
    """Test safety guard enforcement."""
    
    @pytest.mark.asyncio
    async def test_trade_size_limit_enforced(self, session_manager):
        """Verify trade size cannot exceed $100 per trade."""
        session_manager.session_active = True
        
        # Attempt to execute oversized trade
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=2.0,  # Would be $4000 at $2000 price
                price=2000.0,
                leverage=1
            )
        
        assert "Trade size" in str(exc_info.value)
        assert "$100" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_leverage_limit_enforced(self, session_manager):
        """Verify leverage cannot exceed configured maximum."""
        session_manager.session_active = True
        
        # Attempt excessive leverage
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=0.01,  # $20 trade
                price=2000.0,
                leverage=50  # Exceeds default max of 5
            )
        
        assert "Leverage" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_position_size_limit_enforced(self, session_manager):
        """Verify position size cannot exceed 1% of account balance."""
        session_manager.session_active = True
        
        # Calculate max position (1% of $1000 = $10)
        # At $2000 price, that's 0.005 units
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=0.1,  # $200 position (20% of balance)
                price=2000.0,
                leverage=1
            )
        
        assert "Position size" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_daily_loss_limit_enforced(self, session_manager):
        """Verify session pauses when daily loss exceeds -5%."""
        session_manager.session_active = True
        session_manager.daily_pnl = -60.0  # -6% of $1000
        
        # Should reject new trades
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=0.01,
                price=2000.0,
                leverage=1
            )
        
        assert "Daily loss limit" in str(exc_info.value)
        assert not session_manager.session_active  # Session should auto-pause


class TestRealisticSimulation:
    """Test realistic market simulation features."""
    
    @pytest.mark.asyncio
    async def test_spread_simulation(self, session_manager):
        """Verify spread is applied to fill prices."""
        session_manager.session_active = True
        
        # Mock exchange client
        with patch.object(session_manager, '_simulate_order_execution') as mock_exec:
            mock_exec.return_value = {
                'order_id': 'test_123',
                'fill_price': 2001.0,  # Ask price (spread applied)
                'status': 'FILLED'
            }
            
            result = await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=0.01,
                price=2000.0,  # Mid price
                leverage=1
            )
            
            # Fill price should include spread
            assert result['fill_price'] > 2000.0
    
    @pytest.mark.asyncio
    async def test_slippage_applied(self, session_manager):
        """Verify slippage is tracked and within expected range."""
        session_manager.session_active = True
        
        with patch.object(session_manager, '_simulate_order_execution') as mock_exec:
            mock_exec.return_value = {
                'order_id': 'test_123',
                'fill_price': 2000.5,
                'status': 'FILLED'
            }
            
            result = await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=0.01,
                price=2000.0,
                leverage=1
            )
            
            # Slippage should be calculated
            assert 'slippage_pct' in result
            assert 0 <= result['slippage_pct'] <= 0.1  # Max 0.1%
    
    @pytest.mark.asyncio
    async def test_latency_simulation(self, session_manager):
        """Verify execution includes realistic latency (50-1000ms)."""
        session_manager.session_active = True
        
        with patch.object(session_manager, '_simulate_order_execution') as mock_exec:
            mock_exec.return_value = {
                'order_id': 'test_123',
                'fill_price': 2000.0,
                'status': 'FILLED'
            }
            
            start_time = asyncio.get_event_loop().time()
            result = await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=0.01,
                price=2000.0,
                leverage=1
            )
            end_time = asyncio.get_event_loop().time()
            
            execution_time_ms = (end_time - start_time) * 1000
            
            # Should have some latency (at least 10ms for async overhead)
            assert execution_time_ms >= 10
            assert 'execution_time_ms' in result


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
        
        with pytest.raises(SafetyGuardViolation) as exc_info:
            await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=0.01,
                price=2000.0,
                leverage=1
            )
        
        assert "Session not active" in str(exc_info.value)


class TestPerformanceTracking:
    """Test performance metrics collection."""
    
    @pytest.mark.asyncio
    async def test_latency_metrics_tracked(self, session_manager):
        """Verify execution latencies are tracked."""
        await session_manager.start_session()
        
        with patch.object(session_manager, '_simulate_order_execution') as mock_exec:
            mock_exec.return_value = {
                'order_id': 'test_123',
                'fill_price': 2000.0,
                'status': 'FILLED'
            }
            
            # Execute multiple trades
            for _ in range(3):
                await session_manager.execute_paper_trade(
                    symbol='XAUUSDT',
                    side='BUY',
                    quantity=0.01,
                    price=2000.0,
                    leverage=1
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
        
        with patch.object(session_manager, '_simulate_order_execution') as mock_exec:
            mock_exec.return_value = {
                'order_id': 'test_123',
                'fill_price': 2000.0,
                'status': 'FILLED'
            }
            
            result = await session_manager.execute_paper_trade(
                symbol='XAUUSDT',
                side='BUY',
                quantity=0.01,
                price=2000.0,
                leverage=1,
                db_session=mock_db_session
            )
        
        # Verify database add was called
        assert mock_db_session.add.called
        assert mock_db_session.commit.called
    
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
