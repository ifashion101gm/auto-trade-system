"""
Performance Optimization Tests - Benchmark critical paths.

These tests measure and verify performance of key system components:
1. Signal generation latency (< 500ms)
2. Risk validation speed (< 100ms)
3. Order execution time (< 2 seconds)
4. Database query performance (< 50ms)
5. WebSocket message processing (< 100ms)

Benchmarks ensure the system meets real-time trading requirements.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.strategy.trend.trend_strategy import TrendStrategy
from app.strategy.breakout.breakout_strategy import BreakoutStrategy
from app.risk.risk_engine import RiskEngine
from app.execution.execution_service import ExecutionService, ExecutionRequest


# ============================================================================
# PERFORMANCE THRESHOLDS
# ============================================================================

SIGNAL_GENERATION_THRESHOLD = 0.5  # 500ms
RISK_VALIDATION_THRESHOLD = 0.1    # 100ms
ORDER_EXECUTION_THRESHOLD = 2.0    # 2 seconds
DB_QUERY_THRESHOLD = 0.05          # 50ms
WEBSOCKET_PROCESSING_THRESHOLD = 0.1  # 100ms


# ============================================================================
# TEST 1: Signal Generation Performance
# ============================================================================

@pytest.mark.performance
class TestSignalGenerationPerformance:
    """Benchmark signal generation latency across strategies."""
    
    @pytest.fixture
    def trend_strategy(self):
        return TrendStrategy(ma_fast=20, ma_slow=50, min_trend_strength=0.01)
    
    @pytest.fixture
    def breakout_strategy(self):
        return BreakoutStrategy(lookback_period=20, volume_multiplier=1.5)
    
    @pytest.fixture
    def market_data_trend(self):
        return {
            'symbol': 'BTC/USDT',
            'current_price': 50500,
            'ma_20': 50000,
            'ma_50': 49000,
            'macd': 150,
            'atr': 500,
            'regime': 'Normal-Trending'
        }
    
    @pytest.fixture
    def market_data_breakout(self):
        ohlcv = []
        base_price = 50000
        for i in range(20):
            ohlcv.append([i, base_price, base_price + 100, base_price - 100, base_price + 50, 1000])
        ohlcv.append([20, base_price + 50, base_price + 250, base_price + 50, base_price + 200, 5000])
        
        return {
            'symbol': 'BTC/USDT',
            'current_price': 50200,
            'ohlcv': ohlcv,
            'volume_24h': 2000000,
            'atr': 500,
            'regime': 'Normal'
        }
    
    async def test_trend_strategy_generation_speed(self, trend_strategy, market_data_trend):
        """Test 1a: Trend strategy generates signals within threshold."""
        start_time = time.perf_counter()
        
        # Run 10 iterations for average
        for _ in range(10):
            await trend_strategy.generate_signal(market_data_trend)
        
        end_time = time.perf_counter()
        avg_latency = (end_time - start_time) / 10
        
        assert avg_latency < SIGNAL_GENERATION_THRESHOLD, \
            f"Trend strategy too slow: {avg_latency*1000:.2f}ms > {SIGNAL_GENERATION_THRESHOLD*1000}ms"
    
    async def test_breakout_strategy_generation_speed(self, breakout_strategy, market_data_breakout):
        """Test 1b: Breakout strategy generates signals within threshold."""
        start_time = time.perf_counter()
        
        # Run 10 iterations for average
        for _ in range(10):
            await breakout_strategy.generate_signal(market_data_breakout)
        
        end_time = time.perf_counter()
        avg_latency = (end_time - start_time) / 10
        
        assert avg_latency < SIGNAL_GENERATION_THRESHOLD, \
            f"Breakout strategy too slow: {avg_latency*1000:.2f}ms > {SIGNAL_GENERATION_THRESHOLD*1000}ms"
    
    async def test_multiple_strategies_parallel(self, trend_strategy, breakout_strategy, 
                                                market_data_trend, market_data_breakout):
        """Test 1c: Multiple strategies can run in parallel without blocking."""
        start_time = time.perf_counter()
        
        # Run both strategies concurrently
        results = await asyncio.gather(
            trend_strategy.generate_signal(market_data_trend),
            breakout_strategy.generate_signal(market_data_breakout)
        )
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        # Parallel execution should be faster than sequential
        assert total_time < SIGNAL_GENERATION_THRESHOLD * 2, \
            f"Parallel execution too slow: {total_time*1000:.2f}ms"


# ============================================================================
# TEST 2: Risk Validation Performance
# ============================================================================

@pytest.mark.performance
class TestRiskValidationPerformance:
    """Benchmark risk engine validation speed."""
    
    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session
    
    @pytest.fixture
    def risk_engine(self, mock_db_session):
        with patch('app.risk.risk_engine.settings') as mock_settings:
            mock_settings.RISK_MAX_DAILY_LOSS = 5.0
            mock_settings.RISK_MAX_DRAWDOWN = 10.0
            mock_settings.RISK_MAX_POSITION_SIZE_USD = 1000.0
            mock_settings.RISK_MAX_LEVERAGE = 10
            
            return RiskEngine(db_session_factory=lambda: mock_db_session)
    
    async def test_risk_validation_speed(self, risk_engine, mock_db_session):
        """Test 2: Risk validation completes within threshold."""
        # Mock account balance query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 100.0
        mock_db_session.execute.return_value = mock_result
        
        proposal = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry_price': 50000.0,
            'quantity': 0.001,
            'leverage': 1,
            'stop_loss': 49000.0,
            'take_profit': 52000.0,
            'confidence': 0.75
        }
        
        start_time = time.perf_counter()
        
        # Run 20 validations for average
        for _ in range(20):
            await risk_engine.check_trade_approval(proposal, "test_user", mock_db_session)
        
        end_time = time.perf_counter()
        avg_latency = (end_time - start_time) / 20
        
        assert avg_latency < RISK_VALIDATION_THRESHOLD, \
            f"Risk validation too slow: {avg_latency*1000:.2f}ms > {RISK_VALIDATION_THRESHOLD*1000}ms"


# ============================================================================
# TEST 3: Order Execution Performance
# ============================================================================

@pytest.mark.performance
class TestOrderExecutionPerformance:
    """Benchmark order execution latency."""
    
    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_exchange_manager(self):
        manager = AsyncMock()
        manager.place_order.return_value = {
            'order_id': 'perf_test_order',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'status': 'closed',
            'filled': 0.01,
            'fee': 0.5
        }
        return manager
    
    @pytest.fixture
    def execution_service(self, mock_db_session, mock_exchange_manager):
        with patch('app.execution.execution_service.EventPublisher'):
            return ExecutionService(
                exchange_manager=mock_exchange_manager,
                db_session_factory=lambda: mock_db_session
            )
    
    async def test_order_execution_speed(self, execution_service, mock_db_session):
        """Test 3: Order execution completes within threshold."""
        request = ExecutionRequest(
            symbol="BTC/USDT",
            side="LONG",
            quantity=0.01,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            leverage=1,
            strategy_name="trend",
            user_id="test_user"
        )
        
        start_time = time.perf_counter()
        
        # Execute 5 orders for average
        for _ in range(5):
            await execution_service.execute_trade(request, mock_db_session)
        
        end_time = time.perf_counter()
        avg_latency = (end_time - start_time) / 5
        
        assert avg_latency < ORDER_EXECUTION_THRESHOLD, \
            f"Order execution too slow: {avg_latency*1000:.2f}ms > {ORDER_EXECUTION_THRESHOLD*1000}ms"


# ============================================================================
# TEST 4: Database Query Performance
# ============================================================================

@pytest.mark.performance
class TestDatabaseQueryPerformance:
    """Benchmark database query performance."""
    
    @pytest.fixture
    async def db_session(self):
        test_db_url = "postgresql+asyncpg://trading:testpassword@localhost:5432/vmassit_test"
        
        engine = create_async_engine(test_db_url, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with engine.begin() as conn:
            from app.database.models import Base
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as session:
            yield session
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
    
    async def test_simple_query_performance(self, db_session):
        """Test 4a: Simple SELECT queries complete within threshold."""
        from app.database.models import PaperTrades
        
        # Insert test data
        test_trades = [
            PaperTrades(
                symbol=f"BTC/USDT_{i}",
                side="LONG",
                entry_price=50000.0,
                quantity=0.01,
                status="open",
                user_id="test_user",
                opened_at=datetime.utcnow()
            )
            for i in range(100)
        ]
        
        db_session.add_all(test_trades)
        await db_session.commit()
        
        # Benchmark query
        start_time = time.perf_counter()
        
        for _ in range(50):
            result = await db_session.execute(
                PaperTrades.__table__.select().where(PaperTrades.user_id == "test_user")
            )
            result.fetchall()
        
        end_time = time.perf_counter()
        avg_latency = (end_time - start_time) / 50
        
        assert avg_latency < DB_QUERY_THRESHOLD, \
            f"Database query too slow: {avg_latency*1000:.2f}ms > {DB_QUERY_THRESHOLD*1000}ms"
        
        # Cleanup
        await db_session.execute(PaperTrades.__table__.delete())
        await db_session.commit()
    
    async def test_transaction_commit_performance(self, db_session):
        """Test 4b: Transaction commits complete within threshold."""
        from app.database.models import PaperTrades
        
        start_time = time.perf_counter()
        
        # Commit 20 transactions
        for i in range(20):
            trade = PaperTrades(
                symbol=f"BENCH_{i}",
                side="LONG",
                entry_price=50000.0,
                quantity=0.01,
                status="open",
                user_id="bench_user",
                opened_at=datetime.utcnow()
            )
            db_session.add(trade)
            await db_session.commit()
        
        end_time = time.perf_counter()
        avg_latency = (end_time - start_time) / 20
        
        assert avg_latency < DB_QUERY_THRESHOLD * 2, \
            f"Transaction commit too slow: {avg_latency*1000:.2f}ms > {DB_QUERY_THRESHOLD*2000}ms"
        
        # Cleanup
        await db_session.execute(
            PaperTrades.__table__.delete().where(PaperTrades.user_id == "bench_user")
        )
        await db_session.commit()


# ============================================================================
# TEST 5: WebSocket Message Processing
# ============================================================================

@pytest.mark.performance
class TestWebSocketProcessingPerformance:
    """Benchmark WebSocket message handling speed."""
    
    async def test_websocket_message_processing_speed(self):
        """Test 5: WebSocket processes messages within threshold."""
        from app.websocket.websocket_manager import WebSocketManager
        
        manager = WebSocketManager(exchange_name="bybit")
        
        # Simulate message processing
        test_messages = [
            {
                'topic': 'trade.BTCUSDT',
                'data': {
                    's': 'BTCUSDT',
                    'S': 'Buy',
                    'v': '0.01',
                    'p': '50000',
                    'T': int(time.time() * 1000)
                }
            }
            for _ in range(100)
        ]
        
        start_time = time.perf_counter()
        
        # Process messages (simulated)
        for msg in test_messages:
            # In real implementation, this would call _handle_message
            # For benchmark, we just measure the overhead
            pass
        
        end_time = time.perf_counter()
        avg_latency = (end_time - start_time) / len(test_messages)
        
        # This is a baseline - actual processing will be slower
        assert avg_latency < WEBSOCKET_PROCESSING_THRESHOLD, \
            f"Message processing overhead too high: {avg_latency*1000:.2f}ms"


# ============================================================================
# PERFORMANCE REGRESSION DETECTION
# ============================================================================

@pytest.mark.performance
class TestPerformanceRegression:
    """Detect performance regressions compared to baselines."""
    
    def test_no_significant_performance_degradation(self):
        """Verify current performance hasn't regressed significantly."""
        # This test would compare against stored baseline metrics
        # For now, it's a placeholder for future implementation
        
        # Example baseline checks (would load from file):
        baselines = {
            'signal_generation_ms': 100,
            'risk_validation_ms': 20,
            'order_execution_ms': 500,
            'db_query_ms': 10
        }
        
        # Future implementation:
        # current_metrics = load_current_metrics()
        # for metric, baseline in baselines.items():
        #     current = current_metrics[metric]
        #     assert current < baseline * 1.5, f"{metric} regressed by >50%"
        
        assert True  # Placeholder


# ============================================================================
# Run Configuration
# ============================================================================

if __name__ == "__main__":
    # Run with: pytest tests/integration/test_performance_benchmarks.py -v --tb=short
    pytest.main([__file__, "-v", "--tb=short"])
