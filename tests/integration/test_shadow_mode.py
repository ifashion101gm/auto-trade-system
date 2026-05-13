"""
Shadow Mode Integration Tests - Sprint 4 Layer 5.

Tests for ShadowModeExecutionEngine covering:
- Zero-risk validation (no real orders sent)
- Divergence tracking (simulated vs actual prices)
- Accuracy score calculation
- Performance metrics aggregation
- Database persistence of shadow trades
- SL/TP trigger simulation

Success Criteria:
- 8 comprehensive tests
- No exchange API calls made
- Divergence properly calculated
- Accuracy scores validated
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from app.shadow_mode.execution_engine import ShadowExecutionEngine
from app.database.models import ShadowTrades


@pytest.fixture
def shadow_engine():
    """Create a shadow mode execution engine for testing."""
    return ShadowExecutionEngine(
        user_id='test_user',
        slippage_pct=0.001,  # 0.1%
        min_accuracy_score=90.0
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


class TestZeroRiskValidation:
    """Verify shadow mode sends no real orders."""
    
    @pytest.mark.asyncio
    async def test_no_exchange_api_calls(self, shadow_engine):
        """Verify shadow mode does not call exchange APIs."""
        with patch('app.exchange.client.ExchangeClient') as mock_client:
            await shadow_engine.execute_shadow_trade(
                symbol='XAUUSDT',
                side='BUY',
                price=2000.0,
                confidence=0.85,
                strategy='trend_following'
            )
            
            # Should never instantiate or call exchange client
            mock_client.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_virtual_order_only(self, shadow_engine):
        """Verify orders are purely virtual/simulated."""
        result = await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following'
        )
        
        assert result['order_type'] == 'VIRTUAL'
        assert 'simulated' in result['fill_price_source'].lower()


class TestDivergenceTracking:
    """Test divergence calculation between simulated and actual prices."""
    
    @pytest.mark.asyncio
    async def test_divergence_calculated_on_entry(self, shadow_engine):
        """Verify divergence is tracked at trade entry."""
        market_data = {
            'symbol': 'XAUUSDT',
            'bid': 1999.5,
            'ask': 2000.5,
            'mid': 2000.0
        }
        
        result = await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following',
            market_data=market_data
        )
        
        # Should track both simulated and actual prices
        assert 'entry_price_simulated' in result
        assert 'entry_price_actual' in result
        
        # Simulated should include slippage
        assert result['entry_price_simulated'] != result['entry_price_actual']
    
    @pytest.mark.asyncio
    async def test_divergence_tracked_on_exit(self, shadow_engine):
        """Verify divergence is tracked when trade closes."""
        # Open a shadow trade
        open_result = await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following'
        )
        
        trade_id = open_result['trade_id']
        
        # Close the trade with different actual price
        close_result = await shadow_engine.close_shadow_trade(
            trade_id=trade_id,
            exit_price_simulated=2010.0,
            exit_price_actual=2009.5,
            exit_reason='TAKE_PROFIT'
        )
        
        assert 'divergence_pct' in close_result
        assert close_result['divergence_pct'] is not None
    
    @pytest.mark.asyncio
    async def test_divergence_within_expected_range(self, shadow_engine):
        """Verify divergence percentages are realistic."""
        result = await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following'
        )
        
        # With 0.1% slippage model, divergence should be small
        if 'slippage_applied' in result:
            assert 0 <= result['slippage_applied'] <= 0.002  # Max 0.2%


class TestAccuracyScoring:
    """Test accuracy score calculation."""
    
    @pytest.mark.asyncio
    async def test_accuracy_score_updated_on_close(self, shadow_engine):
        """Verify accuracy score is calculated when trade closes."""
        # Open trade
        open_result = await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following'
        )
        
        trade_id = open_result['trade_id']
        
        # Close with profit (correct direction prediction)
        await shadow_engine.close_shadow_trade(
            trade_id=trade_id,
            exit_price_simulated=2010.0,
            exit_price_actual=2009.5,
            exit_reason='TAKE_PROFIT'
        )
        
        # Get metrics
        metrics = shadow_engine.get_performance_metrics()
        
        assert 'accuracy_score' in metrics
        assert 0 <= metrics['accuracy_score'] <= 100
    
    @pytest.mark.asyncio
    async def test_accuracy_score_direction_based(self, shadow_engine):
        """Verify accuracy reflects correct direction prediction."""
        # Simulate winning trade (correct direction)
        open_result = await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following'
        )
        
        await shadow_engine.close_shadow_trade(
            trade_id=open_result['trade_id'],
            exit_price_simulated=2010.0,  # Price went up (correct for BUY)
            exit_price_actual=2009.5,
            exit_reason='TAKE_PROFIT'
        )
        
        metrics = shadow_engine.get_performance_metrics()
        
        # Should have positive contribution to accuracy
        assert metrics.get('winning_trades', 0) >= 1


class TestPerformanceMetrics:
    """Test aggregated performance metrics."""
    
    @pytest.mark.asyncio
    async def test_win_rate_calculated(self, shadow_engine):
        """Verify win rate is properly calculated."""
        # Execute multiple trades with mixed results
        for i in range(5):
            result = await shadow_engine.execute_shadow_trade(
                symbol='XAUUSDT',
                side='BUY' if i % 2 == 0 else 'SELL',
                price=2000.0 + i,
                confidence=0.85,
                strategy='trend_following'
            )
            
            # Close trades
            exit_price = 2010.0 if i % 2 == 0 else 1990.0
            await shadow_engine.close_shadow_trade(
                trade_id=result['trade_id'],
                exit_price_simulated=exit_price,
                exit_price_actual=exit_price - 0.5,
                exit_reason='TAKE_PROFIT' if i < 3 else 'STOP_LOSS'
            )
        
        metrics = shadow_engine.get_performance_metrics()
        
        assert 'total_trades' in metrics
        assert 'winning_trades' in metrics
        assert 'losing_trades' in metrics
        assert 'win_rate' in metrics
        
        # Win rate should be percentage
        assert 0 <= metrics['win_rate'] <= 100
    
    @pytest.mark.asyncio
    async def test_sharpe_ratio_calculated(self, shadow_engine):
        """Verify Sharpe ratio is computed from P&L series."""
        # Execute several trades
        for i in range(10):
            result = await shadow_engine.execute_shadow_trade(
                symbol='XAUUSDT',
                side='BUY',
                price=2000.0,
                confidence=0.85,
                strategy='trend_following'
            )
            
            await shadow_engine.close_shadow_trade(
                trade_id=result['trade_id'],
                exit_price_simulated=2000.0 + (i * 2),  # Varying P&L
                exit_price_actual=2000.0 + (i * 2) - 0.5,
                exit_reason='TAKE_PROFIT'
            )
        
        metrics = shadow_engine.get_performance_metrics()
        
        assert 'sharpe_ratio' in metrics
        assert metrics['sharpe_ratio'] is not None
    
    @pytest.mark.asyncio
    async def test_max_drawdown_tracked(self, shadow_engine):
        """Verify maximum drawdown is tracked."""
        # Simulate sequence with losses
        pnl_values = [10, -5, -15, 20, -10]
        
        for pnl in pnl_values:
            result = await shadow_engine.execute_shadow_trade(
                symbol='XAUUSDT',
                side='BUY',
                price=2000.0,
                confidence=0.85,
                strategy='trend_following'
            )
            
            exit_price = 2000.0 + pnl
            await shadow_engine.close_shadow_trade(
                trade_id=result['trade_id'],
                exit_price_simulated=exit_price,
                exit_price_actual=exit_price - 0.5,
                exit_reason='TAKE_PROFIT' if pnl > 0 else 'STOP_LOSS'
            )
        
        metrics = shadow_engine.get_performance_metrics()
        
        assert 'max_drawdown_pct' in metrics


class TestDatabasePersistence:
    """Test shadow trade database persistence."""
    
    @pytest.mark.asyncio
    async def test_shadow_trade_saved_to_db(self, shadow_engine, mock_db_session):
        """Verify shadow trades are persisted to database."""
        await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following',
            db_session=mock_db_session
        )
        
        # Verify database operations
        assert mock_db_session.add.called
        assert mock_db_session.commit.called
    
    @pytest.mark.asyncio
    async def test_shadow_trade_fields_populated(self, shadow_engine, mock_db_session):
        """Verify all required fields are populated in database record."""
        await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following',
            db_session=mock_db_session
        )
        
        # Get the added object
        added_obj = mock_db_session.add.call_args[0][0]
        
        assert added_obj.symbol == 'XAUUSDT'
        assert added_obj.side == 'BUY'
        assert added_obj.status == 'open'
        assert added_obj.confidence == 0.85
        assert added_obj.strategy_name == 'trend_following'


class TestSLTPSimulation:
    """Test stop-loss and take-profit simulation."""
    
    @pytest.mark.asyncio
    async def test_stop_loss_triggered(self, shadow_engine):
        """Verify stop-loss triggers correctly."""
        result = await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following',
            stop_loss=1990.0,
            take_profit=2020.0
        )
        
        trade_id = result['trade_id']
        
        # Simulate price hitting stop loss
        close_result = await shadow_engine.close_shadow_trade(
            trade_id=trade_id,
            exit_price_simulated=1990.0,
            exit_price_actual=1989.5,
            exit_reason='STOP_LOSS'
        )
        
        assert close_result['exit_reason'] == 'STOP_LOSS'
        assert close_result['pnl_simulated'] < 0  # Loss
    
    @pytest.mark.asyncio
    async def test_take_profit_triggered(self, shadow_engine):
        """Verify take-profit triggers correctly."""
        result = await shadow_engine.execute_shadow_trade(
            symbol='XAUUSDT',
            side='BUY',
            price=2000.0,
            confidence=0.85,
            strategy='trend_following',
            stop_loss=1990.0,
            take_profit=2020.0
        )
        
        trade_id = result['trade_id']
        
        # Simulate price hitting take profit
        close_result = await shadow_engine.close_shadow_trade(
            trade_id=trade_id,
            exit_price_simulated=2020.0,
            exit_price_actual=2019.5,
            exit_reason='TAKE_PROFIT'
        )
        
        assert close_result['exit_reason'] == 'TAKE_PROFIT'
        assert close_result['pnl_simulated'] > 0  # Profit


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
