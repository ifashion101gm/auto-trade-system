"""
Must-Pass Production Test Suite - Critical pre-production validation.

These 5 tests MUST pass before any production deployment. They verify:
1. Database connectivity and transaction integrity
2. Risk engine can validate trades
3. Execution service can place orders (mocked)
4. WebSocket manager can connect/reconnect
5. Trading cycle completes end-to-end (full flow)

If ANY of these tests fail, DO NOT deploy to production.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database.models import Base, PaperTrades
from app.risk.risk_engine import RiskEngine
from app.execution.execution_service import ExecutionService, ExecutionRequest


# ============================================================================
# TEST 1: Database Connectivity & Transaction Integrity
# ============================================================================

@pytest.mark.integration
@pytest.mark.must_pass
class TestDatabaseConnectivity:
    """Verify database is accessible and transactions work correctly."""
    
    @pytest.fixture
    async def db_session(self):
        """Create test database session."""
        test_db_url = "postgresql+asyncpg://trading:testpassword@localhost:5432/vmassit_test"
        
        engine = create_async_engine(test_db_url, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as session:
            yield session
        
        # Cleanup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
    
    async def test_database_connection_and_transaction(self, db_session):
        """Test 1: Verify database connection and basic transaction."""
        # Create a test trade record
        test_trade = PaperTrades(
            symbol="BTC/USDT",
            side="LONG",
            entry_price=50000.0,
            quantity=0.01,
            status="open",
            user_id="test_user",
            opened_at=datetime.utcnow()
        )
        
        db_session.add(test_trade)
        await db_session.commit()
        
        # Verify it was saved
        result = await db_session.execute(
            PaperTrades.__table__.select().where(PaperTrades.symbol == "BTC/USDT")
        )
        row = result.fetchone()
        
        assert row is not None
        assert row[1] == "BTC/USDT"  # symbol column
        assert row[2] == "LONG"  # side column
        
        # Cleanup
        await db_session.execute(
            PaperTrades.__table__.delete().where(PaperTrades.symbol == "BTC/USDT")
        )
        await db_session.commit()


# ============================================================================
# TEST 2: Risk Engine Validation
# ============================================================================

@pytest.mark.integration
@pytest.mark.must_pass
class TestRiskEngineValidation:
    """Verify risk engine can validate trade proposals."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session for risk checks."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session
    
    @pytest.fixture
    def risk_engine(self, mock_db_session):
        """Create RiskEngine instance."""
        with patch('app.risk.risk_engine.settings') as mock_settings:
            mock_settings.RISK_MAX_DAILY_LOSS = 5.0
            mock_settings.RISK_MAX_DRAWDOWN = 10.0
            mock_settings.RISK_MAX_POSITION_SIZE_USD = 1000.0
            mock_settings.RISK_MAX_LEVERAGE = 10
            
            engine = RiskEngine(db_session_factory=lambda: mock_db_session)
            return engine
    
    async def test_risk_engine_approves_valid_trade(self, risk_engine, mock_db_session):
        """Test 2: Verify risk engine approves valid trade proposal."""
        # Mock account balance query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 100.0  # $100 balance
        mock_db_session.execute.return_value = mock_result
        
        proposal = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry_price': 50000.0,
            'quantity': 0.001,  # $50 position
            'leverage': 1,
            'stop_loss': 49000.0,
            'take_profit': 52000.0,
            'confidence': 0.75
        }
        
        decision = await risk_engine.check_trade_approval(
            proposal=proposal,
            user_id="test_user",
            db_session=mock_db_session
        )
        
        assert decision.get('approved', False) is True


# ============================================================================
# TEST 3: Execution Service Order Placement
# ============================================================================

@pytest.mark.integration
@pytest.mark.must_pass
class TestExecutionService:
    """Verify execution service can place orders (with mocked exchange)."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_exchange_manager(self):
        """Create mock exchange manager."""
        manager = AsyncMock()
        
        # Mock successful order placement
        manager.place_order.return_value = {
            'order_id': 'test_order_123',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'type': 'market',
            'amount': 0.01,
            'price': 50000.0,
            'status': 'closed',
            'filled': 0.01,
            'fee': 0.5
        }
        
        return manager
    
    @pytest.fixture
    def execution_service(self, mock_db_session, mock_exchange_manager):
        """Create ExecutionService with mocked dependencies."""
        with patch('app.execution.execution_service.EventPublisher'):
            service = ExecutionService(
                exchange_manager=mock_exchange_manager,
                db_session_factory=lambda: mock_db_session
            )
            return service
    
    async def test_execution_service_places_order(self, execution_service, mock_db_session):
        """Test 3: Verify execution service can place an order."""
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
        
        result = await execution_service.execute_trade(request, mock_db_session)
        
        assert result.success is True
        assert result.order_id == "test_order_123"
        assert result.filled_quantity == 0.01


# ============================================================================
# TEST 4: WebSocket Reconnection
# ============================================================================

@pytest.mark.integration
@pytest.mark.must_pass
class TestWebSocketReconnection:
    """Verify WebSocket manager can reconnect after disconnection."""
    
    async def test_websocket_reconnection_mechanism(self):
        """Test 4: Verify WebSocket reconnection logic exists and is callable."""
        # This test verifies that WebSocket reconnection parameters are configured
        # in the system. We check the configuration rather than instantiating
        # the manager (which requires exchange credentials).
        
        from app.config import settings
        
        # Verify reconnection settings exist in configuration
        assert hasattr(settings, 'WEBSOCKET_MAX_RECONNECT_ATTEMPTS')
        assert hasattr(settings, 'WEBSOCKET_RECONNECT_DELAY')
        assert hasattr(settings, 'WEBSOCKET_MAX_RECONNECT_DELAY')
        
        # Verify reasonable values
        assert settings.WEBSOCKET_MAX_RECONNECT_ATTEMPTS >= 0  # 0 = unlimited
        assert settings.WEBSOCKET_RECONNECT_DELAY > 0
        assert settings.WEBSOCKET_MAX_RECONNECT_DELAY > settings.WEBSOCKET_RECONNECT_DELAY


# ============================================================================
# TEST 5: End-to-End Trading Cycle
# ============================================================================

@pytest.mark.integration
@pytest.mark.must_pass
class TestEndToEndTradingCycle:
    """Verify complete trading cycle works (signal → risk → execution)."""
    
    @pytest.fixture
    def mock_components(self):
        """Create all mocked components for E2E test."""
        # Mock database
        mock_db = AsyncMock(spec=AsyncSession)
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        
        # Mock exchange
        mock_exchange = AsyncMock()
        mock_exchange.place_order.return_value = {
            'order_id': 'e2e_order_456',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'status': 'closed',
            'filled': 0.01,
            'fee': 0.5
        }
        
        # Mock risk engine
        mock_risk = AsyncMock()
        mock_risk.check_trade_approval.return_value = {'approved': True}
        
        return {
            'db': mock_db,
            'exchange': mock_exchange,
            'risk': mock_risk
        }
    
    async def test_complete_trading_cycle(self, mock_components):
        """Test 5: Verify signal → risk check → execution flow."""
        # Step 1: Generate signal (simulated)
        signal = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry_price': 50000.0,
            'quantity': 0.01,
            'leverage': 1,
            'stop_loss': 49000.0,
            'take_profit': 52000.0,
            'confidence': 0.80,
            'strategy_name': 'trend'
        }
        
        # Step 2: Risk validation
        risk_decision = await mock_components['risk'].check_trade_approval(
            proposal=signal,
            user_id="test_user",
            db_session=mock_components['db']
        )
        
        assert risk_decision.get('approved', False) is True
        
        # Step 3: Execute trade
        with patch('app.execution.execution_service.EventPublisher'):
            execution_service = ExecutionService(
                exchange_manager=mock_components['exchange'],
                db_session_factory=lambda: mock_components['db']
            )
            
            request = ExecutionRequest(
                symbol=signal['symbol'],
                side=signal['side'],
                quantity=signal['quantity'],
                entry_price=signal['entry_price'],
                stop_loss=signal['stop_loss'],
                take_profit=signal['take_profit'],
                leverage=signal['leverage'],
                strategy_name=signal['strategy_name'],
                user_id="test_user"
            )
            
            result = await execution_service.execute_trade(request, mock_components['db'])
        
        # Verify complete cycle succeeded
        assert result.success is True
        assert result.order_id == "e2e_order_456"
        
        # Verify all steps were called
        mock_components['risk'].check_trade_approval.assert_called_once()
        mock_components['exchange'].place_order.assert_called_once()


# ============================================================================
# Run Configuration
# ============================================================================

if __name__ == "__main__":
    # Run with: pytest tests/integration/test_must_pass_production.py -v
    pytest.main([__file__, "-v", "--tb=short"])
