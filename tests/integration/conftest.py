"""
Integration test fixtures for Auto Trade System.

Provides mocked external services and shared fixtures for testing
inter-module communication while maintaining isolation from real APIs.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.strategy.signal_proposal import SignalProposal
from app.risk.risk_engine import RiskEngine


@pytest.fixture
def mock_exchange_manager():
    """
    Mock exchange manager that simulates successful order execution.
    
    Returns predefined responses for common exchange operations without
    making actual API calls.
    """
    mock = AsyncMock()
    
    # Simulate successful ticker fetch
    mock.fetch_ticker.return_value = {
        'symbol': 'BTC/USDT',
        'last_price': 50000.0,
        'bid': 49999.0,
        'ask': 50001.0,
        'volume_24h': 1000000
    }
    
    # Simulate successful order creation
    mock.create_market_order.return_value = {
        'order_id': 'test-order-123',
        'status': 'FILLED',
        'price': 50000.0,
        'filled': 0.01,
        'fee': {'cost': 0.5, 'currency': 'USDT'}
    }
    
    # Simulate position fetching
    mock.fetch_positions.return_value = [
        {
            'symbol': 'BTC/USDT',
            'size': 0.5,
            'entry_price': 49500.0,
            'mark_price': 50000.0,
            'unrealized_pnl': 250.0
        }
    ]
    
    return mock


@pytest.fixture
def mock_db_session():
    """
    Mock async database session for integration tests.
    
    Simulates database operations without actual persistence.
    """
    mock = AsyncMock()
    mock.execute.return_value = MagicMock()
    mock.execute.return_value.scalar_one_or_none.return_value = None
    mock.flush = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.add = MagicMock()
    mock.merge = MagicMock()
    return mock


@pytest.fixture
def sample_signal_proposal():
    """
    Standard signal proposal for integration tests.
    
    Represents a typical breakout strategy signal with realistic parameters.
    """
    return SignalProposal(
        symbol='BTC/USDT',
        side='LONG',
        entry_price=50000.0,
        stop_loss=49000.0,
        take_profit=52000.0,
        quantity=0.01,
        leverage=2,
        confidence=0.85,
        strategy_name='breakout',
        regime='Normal'
    )


@pytest.fixture
def integration_risk_engine(mock_db_session):
    """
    Risk engine with mocked database for integration tests.
    
    Pre-configured with realistic balance to allow most trades through
    unless explicitly testing rejection scenarios.
    """
    engine = RiskEngine(db_session=mock_db_session)
    # Set realistic balance for testing
    engine.current_balance = 10000
    engine.peak_balance = 10000
    engine.daily_pnl_pct = 0.0
    engine.consecutive_losses = 0
    return engine


@pytest.fixture
def mock_telegram_notifier():
    """Mock Telegram notifier that captures sent messages."""
    mock = AsyncMock()
    mock.send_message = AsyncMock()
    mock.send_alert = AsyncMock()
    return mock


@pytest.fixture
def sample_webhook_payload():
    """
    Standard webhook payload for integration tests.
    
    Mimics the structure sent by external signal sources.
    """
    return {
        'strategy': 'breakout',
        'symbol': 'BTCUSDT',
        'side': 'buy',
        'price': 50000.0,
        'quantity': 0.01,
        'stop_loss': 49000.0,
        'take_profit': 52000.0,
        'leverage': 2,
        'confidence': 0.85
    }


@pytest.fixture
def sample_market_data_for_strategies():
    """
    Complete market data snapshot for strategy signal generation tests.
    
    Includes OHLCV data and all technical indicators.
    """
    return {
        'symbol': 'BTC/USDT',
        'current_price': 50000.0,
        'rsi': 65.0,
        'ma_20': 49500.0,
        'ma_50': 48800.0,
        'macd': 150.0,
        'atr': 500.0,
        'volume_24h': 1000000,
        'bb_upper': 51000.0,
        'bb_middle': 50000.0,
        'bb_lower': 49000.0,
        'regime': 'Normal-Trending',
        'ohlcv': [[i, 50000+i*10, 50100+i*10, 49900+i*10, 50050+i*10, 1000] 
                  for i in range(50)]
    }
