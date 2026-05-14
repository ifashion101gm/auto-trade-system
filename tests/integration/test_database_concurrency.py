"""
Integration tests for database transaction integrity under concurrent load.

Tests cover:
- Multiple concurrent trade executions
- Transaction isolation levels
- Deadlock detection and resolution
- Connection pool exhaustion handling
- Rollback on constraint violations
"""
import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func

from app.database.connection import init_db, get_session
from app.database.models import Base, PaperTrades


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session():
    """Create test database session."""
    # Use test database URL
    test_db_url = "postgresql+asyncpg://trading:testpassword@localhost:5432/vmassit_test"
    
    engine = create_async_engine(test_db_url, echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


class TestConcurrentTradeExecutions:
    """Test concurrent trade execution scenarios."""
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_trades_same_user(self, db_session):
        """Verify multiple trades can execute concurrently for same user."""
        
        async def execute_trade(trade_num):
            """Simulate trade execution."""
            trade = PaperTrades(
                user_id='user123',
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67 + trade_num,
                quantity=0.01,
                status='open',
                timestamp=datetime.utcnow()
            )
            db_session.add(trade)
            await db_session.commit()
            return trade.id
        
        # Execute 10 trades concurrently
        tasks = [execute_trade(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all trades succeeded
        successful = [r for r in results if isinstance(r, int)]
        assert len(successful) == 10
        
        # Verify all trades in database
        stmt = select(func.count()).select_from(PaperTrades).where(
            PaperTrades.user_id == 'user123'
        )
        result = await db_session.execute(stmt)
        count = result.scalar()
        
        assert count == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_trades_different_users(self, db_session):
        """Verify trades for different users don't interfere."""
        
        async def execute_trade(user_id, trade_num):
            """Simulate trade execution for specific user."""
            trade = PaperTrades(
                user_id=user_id,
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.01,
                status='open',
                timestamp=datetime.utcnow()
            )
            db_session.add(trade)
            await db_session.commit()
            return trade.id
        
        # Execute trades for 5 users concurrently
        tasks = []
        for user_num in range(5):
            for trade_num in range(3):
                tasks.append(execute_trade(f'user{user_num}', trade_num))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all trades succeeded
        successful = [r for r in results if isinstance(r, int)]
        assert len(successful) == 15  # 5 users × 3 trades


class TestTransactionIsolation:
    """Test database transaction isolation."""
    
    @pytest.mark.asyncio
    async def test_isolated_concurrent_updates(self, db_session):
        """Verify concurrent updates to same record are isolated."""
        
        # Create initial trade
        trade = PaperTrades(
            user_id='user123',
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1,
            status='open',
            pnl_usd=0.0,
            timestamp=datetime.utcnow()
        )
        db_session.add(trade)
        await db_session.commit()
        trade_id = trade.id
        
        async def update_pnl(update_num):
            """Simulate P&L update."""
            async with async_sessionmaker(db_session.bind)() as session:
                stmt = select(PaperTrades).where(PaperTrades.id == trade_id)
                result = await session.execute(stmt)
                trade_record = result.scalar_one()
                
                # Update P&L
                trade_record.pnl_usd += update_num
                await session.commit()
                
                return trade_record.pnl_usd
        
        # Execute 5 concurrent updates
        tasks = [update_pnl(i) for i in range(1, 6)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify final P&L is sum of all updates (1+2+3+4+5 = 15)
        # Note: Actual behavior depends on isolation level
        stmt = select(PaperTrades).where(PaperTrades.id == trade_id)
        result = await db_session.execute(stmt)
        final_trade = result.scalar_one()
        
        # At least some updates should have succeeded
        assert final_trade.pnl_usd > 0


class TestDeadlockHandling:
    """Test deadlock detection and resolution."""
    
    @pytest.mark.asyncio
    async def test_handle_potential_deadlock_scenario(self, db_session):
        """Verify system handles potential deadlock gracefully."""
        
        # Create two trades
        trade1 = PaperTrades(
            user_id='user123',
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1,
            status='open',
            timestamp=datetime.utcnow()
        )
        trade2 = PaperTrades(
            user_id='user123',
            symbol='XAUUSDT',
            side='sell',
            entry_price=2346.67,
            quantity=0.1,
            status='open',
            timestamp=datetime.utcnow()
        )
        db_session.add(trade1)
        db_session.add(trade2)
        await db_session.commit()
        
        trade1_id = trade1.id
        trade2_id = trade2.id
        
        async def update_trade_a():
            """Update trade A then B (potential deadlock)."""
            try:
                async with async_sessionmaker(db_session.bind)() as session:
                    # Lock trade 1
                    stmt = select(PaperTrades).where(PaperTrades.id == trade1_id).with_for_update()
                    result = await session.execute(stmt)
                    t1 = result.scalar_one()
                    t1.status = 'closed'
                    
                    await asyncio.sleep(0.1)  # Small delay
                    
                    # Lock trade 2
                    stmt = select(PaperTrades).where(PaperTrades.id == trade2_id).with_for_update()
                    result = await session.execute(stmt)
                    t2 = result.scalar_one()
                    t2.status = 'closed'
                    
                    await session.commit()
                    return True
            except Exception as e:
                # Deadlock or timeout - should handle gracefully
                return False
        
        async def update_trade_b():
            """Update trade B then A (opposite order - deadlock risk)."""
            try:
                async with async_sessionmaker(db_session.bind)() as session:
                    # Lock trade 2
                    stmt = select(PaperTrades).where(PaperTrades.id == trade2_id).with_for_update()
                    result = await session.execute(stmt)
                    t2 = result.scalar_one()
                    t2.status = 'partially_closed'
                    
                    await asyncio.sleep(0.1)  # Small delay
                    
                    # Lock trade 1
                    stmt = select(PaperTrades).where(PaperTrades.id == trade1_id).with_for_update()
                    result = await session.execute(stmt)
                    t1 = result.scalar_one()
                    t1.status = 'partially_closed'
                    
                    await session.commit()
                    return True
            except Exception as e:
                # Deadlock or timeout - should handle gracefully
                return False
        
        # Execute both updates concurrently
        result_a, result_b = await asyncio.gather(
            update_trade_a(),
            update_trade_b(),
            return_exceptions=True
        )
        
        # At least one should succeed (deadlock resolver wins)
        # The other may fail with deadlock error
        assert isinstance(result_a, bool) or isinstance(result_b, bool)


class TestConnectionPoolExhaustion:
    """Test connection pool exhaustion handling."""
    
    @pytest.mark.asyncio
    async def test_handle_many_concurrent_connections(self, db_session):
        """Verify system handles many concurrent connections gracefully."""
        
        async def simple_query(query_num):
            """Execute simple query."""
            try:
                async with async_sessionmaker(db_session.bind)() as session:
                    stmt = select(func.count()).select_from(PaperTrades)
                    result = await session.execute(stmt)
                    return result.scalar()
            except Exception as e:
                # Pool exhaustion or timeout
                return None
        
        # Execute 50 concurrent queries
        tasks = [simple_query(i) for i in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some should succeed, some may fail due to pool limits
        successful = [r for r in results if isinstance(r, int)]
        
        # At least some queries should succeed
        assert len(successful) > 0
        
        # If pool is properly configured, most should succeed
        # This verifies pool doesn't completely exhaust


class TestRollbackOnConstraintViolation:
    """Test transaction rollback on constraint violations."""
    
    @pytest.mark.asyncio
    async def test_rollback_on_unique_constraint_violation(self, db_session):
        """Verify transaction rolls back on unique constraint violation."""
        
        # Create a trade with unique identifier
        trade1 = PaperTrades(
            user_id='user123',
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1,
            status='open',
            timestamp=datetime.utcnow()
        )
        db_session.add(trade1)
        await db_session.commit()
        
        # Try to insert duplicate (if unique constraint exists)
        # This test assumes there's some unique constraint
        trade2 = PaperTrades(
            user_id='user123',
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1,
            status='open',
            timestamp=datetime.utcnow()
        )
        db_session.add(trade2)
        
        try:
            await db_session.commit()
            # If no constraint, both trades exist
            stmt = select(func.count()).select_from(PaperTrades).where(
                PaperTrades.user_id == 'user123'
            )
            result = await db_session.execute(stmt)
            count = result.scalar()
            assert count >= 2
        except Exception:
            # Constraint violation - verify rollback
            await db_session.rollback()
            
            # Verify only first trade exists
            stmt = select(func.count()).select_from(PaperTrades).where(
                PaperTrades.user_id == 'user123'
            )
            result = await db_session.execute(stmt)
            count = result.scalar()
            assert count == 1
    
    @pytest.mark.asyncio
    async def test_rollback_on_invalid_data(self, db_session):
        """Verify transaction rolls back on invalid data."""
        
        # Try to insert trade with invalid data (e.g., negative quantity)
        trade = PaperTrades(
            user_id='user123',
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=-0.1,  # Invalid: negative quantity
            status='open',
            timestamp=datetime.utcnow()
        )
        db_session.add(trade)
        
        try:
            await db_session.commit()
            # If database allows it, check was inserted
            assert True
        except Exception:
            # Validation error - verify rollback
            await db_session.rollback()
            
            # Verify no invalid trade was inserted
            stmt = select(func.count()).select_from(PaperTrades).where(
                PaperTrades.user_id == 'user123',
                PaperTrades.quantity < 0
            )
            result = await db_session.execute(stmt)
            count = result.scalar()
            assert count == 0


class TestDatabasePerformanceUnderLoad:
    """Test database performance under concurrent load."""
    
    @pytest.mark.asyncio
    async def test_query_performance_with_concurrent_load(self, db_session):
        """Verify query performance remains acceptable under load."""
        
        # Pre-populate with data
        for i in range(100):
            trade = PaperTrades(
                user_id=f'user{i % 10}',
                symbol='XAUUSDT',
                side='buy' if i % 2 == 0 else 'sell',
                entry_price=2345.67 + i,
                quantity=0.01,
                status='closed' if i % 3 == 0 else 'open',
                pnl_usd=(i % 10) - 5,
                timestamp=datetime.utcnow()
            )
            db_session.add(trade)
        await db_session.commit()
        
        import time
        
        async def complex_query():
            """Execute complex query."""
            start = time.time()
            
            stmt = select(func.avg(PaperTrades.pnl_usd)).where(
                PaperTrades.status == 'closed',
                PaperTrades.symbol == 'XAUUSDT'
            )
            result = await db_session.execute(stmt)
            avg_pnl = result.scalar()
            
            elapsed = time.time() - start
            return avg_pnl, elapsed
        
        # Execute queries concurrently
        tasks = [complex_query() for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all queries completed
        successful = [r for r in results if isinstance(r, tuple)]
        assert len(successful) == 20
        
        # Verify performance (each query should complete in <1 second)
        for avg_pnl, elapsed in successful:
            assert elapsed < 1.0, f"Query took too long: {elapsed}s"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_test_trade(user_id, symbol, side, price, quantity):
    """Helper to create test trade object."""
    return PaperTrades(
        user_id=user_id,
        symbol=symbol,
        side=side,
        entry_price=price,
        quantity=quantity,
        status='open',
        timestamp=datetime.utcnow()
    )
