"""Integration tests for concurrent position risk management."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.risk.risk_engine import RiskEngine, RiskDecision
from app.database.models import PaperTrades


@pytest.mark.asyncio
async def test_concurrent_position_limit_enforcement(mock_db_session):
    """Test that new trades are rejected when max positions reached."""
    engine = RiskEngine(db_session=mock_db_session)
    engine.max_concurrent_positions = 2
    
    # Mock 2 existing open positions
    mock_trades = [
        PaperTrades(id="t1", status='open', entry_price=50000, qty=0.01),
        PaperTrades(id="t2", status='open', entry_price=51000, qty=0.01)
    ]
    
    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = mock_trades
        return result
    
    mock_db_session.execute = mock_execute
    
    decision = await engine.check_trade_approval(
        proposal={'symbol': 'BTC/USDT', 'quantity': 0.01, 'leverage': 1},
        user_id='test_user'
    )
    
    assert not decision.approved
    assert any('concurrent' in v.lower() or 'position' in v.lower() for v in decision.violations)


@pytest.mark.asyncio
async def test_total_exposure_limit(mock_db_session):
    """Test rejection when total exposure exceeds 10% of balance."""
    engine = RiskEngine(db_session=mock_db_session)
    engine.current_balance = 10000
    
    # Mock 1 large position ($1500 exposure = 15% of balance)
    mock_trade = PaperTrades(
        id="t1",
        status='open',
        entry_price=50000,
        qty=0.03,  # $1500 position
        leverage=1
    )
    
    async def mock_execute(stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [mock_trade]
        return result
    
    mock_db_session.execute = mock_execute
    
    decision = await engine.check_trade_approval(
        proposal={'symbol': 'ETH/USDT', 'quantity': 0.1, 'leverage': 1},
        user_id='test_user'
    )
    
    assert not decision.approved
    assert any('exposure' in v.lower() for v in decision.violations)


@pytest.mark.asyncio
async def test_position_registration_tracking(mock_db_session):
    """Test that opening positions updates exposure tracking."""
    engine = RiskEngine(db_session=mock_db_session)
    
    await engine.register_open_position(
        trade_id="t1",
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000,
        quantity=0.01,
        leverage=2
    )
    
    assert "t1" in engine.open_positions
    assert engine.total_exposure_usd == 250.0  # $500 / 2 leverage


@pytest.mark.asyncio
async def test_position_closure_updates_tracking(mock_db_session):
    """Test that closing positions reduces exposure."""
    engine = RiskEngine(db_session=mock_db_session)
    
    # Register position
    await engine.register_open_position(
        trade_id="t1",
        symbol="BTC/USDT",
        side="LONG",
        entry_price=50000,
        quantity=0.01,
        leverage=1
    )
    
    initial_exposure = engine.total_exposure_usd
    
    # Close position
    await engine.close_position("t1")
    
    assert "t1" not in engine.open_positions
    assert engine.total_exposure_usd < initial_exposure
    assert engine.total_exposure_usd == 0.0
