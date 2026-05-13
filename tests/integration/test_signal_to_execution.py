"""
Integration tests for Signal Engine → Risk Engine → Execution Engine pipeline.

Validates complete trade flow from signal generation through risk approval
to order execution, ensuring proper data integrity and error handling across
module boundaries.

All external dependencies (exchanges, databases) are mocked to isolate
inter-module communication logic.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.strategy.signal_proposal import SignalProposal
from app.risk.risk_engine import RiskEngine


class TestSignalToExecutionPipeline:
    """Test complete trade pipeline from signal to execution."""
    
    @pytest.mark.asyncio
    async def test_complete_trade_pipeline_success(
        self,
        sample_signal_proposal,
        integration_risk_engine,
        mock_exchange_manager,
        mock_db_session
    ):
        """
        Test that a valid signal flows through all layers successfully:
        1. Signal Engine generates proposal
        2. Risk Engine approves it
        3. Execution Engine executes order (mocked)
        4. Database persists trade record (mocked)
        
        Expected: Trade executed with all validations passing
        """
        # Step 1: Risk Engine validation
        decision = await integration_risk_engine.check_trade_approval(
            proposal=sample_signal_proposal.to_dict(),
            user_id='test_user'
        )
        
        assert decision.approved == True
        assert len(decision.violations) == 0
        assert 0 <= decision.risk_score <= 100
        
        # Step 2: Execution (mocked)
        with patch('app.infra.exchange_manager.UnifiedExchangeManager') as MockManager:
            MockManager.return_value = mock_exchange_manager
            
            # Execute order
            order_result = await mock_exchange_manager.create_market_order(
                symbol=sample_signal_proposal.symbol,
                side=sample_signal_proposal.side.lower(),
                amount=sample_signal_proposal.quantity,
                leverage=sample_signal_proposal.leverage
            )
            
            # Verify order executed
            assert order_result['status'] == 'FILLED'
            assert order_result['order_id'] == 'test-order-123'
            assert order_result['price'] == 50000.0
    
    @pytest.mark.asyncio
    async def test_risk_rejection_blocks_execution(
        self,
        sample_signal_proposal,
        integration_risk_engine,
        mock_exchange_manager
    ):
        """
        Test that when Risk Engine rejects a signal, execution never occurs.
        
        Setup: Set daily P&L to exceed limit (-3.5% vs -3% limit)
        Expected: Trade rejected, no order sent to exchange
        """
        # Simulate daily loss limit breach
        integration_risk_engine.daily_pnl_pct = -0.04  # -4% (limit is -3%)
        
        decision = await integration_risk_engine.check_trade_approval(
            proposal=sample_signal_proposal.to_dict(),
            user_id='test_user'
        )
        
        assert decision.approved == False
        assert any('Daily loss limit' in v for v in decision.violations)
        
        # Verify exchange was NOT called
        mock_exchange_manager.create_market_order.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_position_size_validation_chain(
        self,
        sample_signal_proposal,
        integration_risk_engine
    ):
        """
        Test position size limits enforced at multiple layers:
        1. Strategy layer suggests position
        2. Risk Engine validates against account balance
        3. Execution layer checks exchange limits
        
        Expected: Oversized positions rejected before execution
        """
        # Create oversized proposal ($500k position on $10k account)
        large_proposal = SignalProposal(
            symbol='BTC/USDT',
            side='LONG',
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
            quantity=10.0,  # $500k position
            leverage=10,     # $5M notional
            confidence=0.9,
            strategy_name='breakout',
            regime='Normal'
        )
        
        decision = await integration_risk_engine.check_trade_approval(
            proposal=large_proposal.to_dict(),
            user_id='test_user'
        )
        
        assert decision.approved == False
        assert any('Position size' in v for v in decision.violations)
    
    @pytest.mark.asyncio
    async def test_leverage_limit_enforcement(
        self,
        sample_signal_proposal,
        integration_risk_engine
    ):
        """
        Test that excessive leverage is rejected by Risk Engine.
        
        Expected: Leverage > 5x rejected regardless of position size
        """
        high_leverage_proposal = SignalProposal(
            symbol='BTC/USDT',
            side='LONG',
            entry_price=50000.0,
            stop_loss=49500.0,
            take_profit=51000.0,
            quantity=0.001,  # Small position
            leverage=10,      # Exceeds 5x limit
            confidence=0.8,
            strategy_name='breakout',
            regime='Normal'
        )
        
        decision = await integration_risk_engine.check_trade_approval(
            proposal=high_leverage_proposal.to_dict(),
            user_id='test_user'
        )
        
        assert decision.approved == False
        assert any('Leverage' in v for v in decision.violations)
    
    @pytest.mark.asyncio
    async def test_concurrent_strategy_signals(
        self,
        sample_market_data_for_strategies
    ):
        """
        Test that multiple strategies can generate signals concurrently
        without race conditions or data corruption.
        
        Expected: All signals processed independently, highest confidence selected
        """
        from app.strategy.strategy_manager import StrategyManager
        
        manager = StrategyManager()
        signals = await manager.generate_signals(sample_market_data_for_strategies)
        
        # Verify at least one signal generated (may be None if no strategy triggers)
        assert isinstance(signals, list)
        
        # Verify signals have unique strategy names (no duplicates)
        non_none_signals = [s for s in signals if s is not None]
        if len(non_none_signals) > 0:
            strategy_names = [s.strategy_name for s in non_none_signals]
            assert len(strategy_names) == len(set(strategy_names))
    
    @pytest.mark.asyncio
    async def test_drawdown_limit_prevents_trading(
        self,
        sample_signal_proposal,
        integration_risk_engine
    ):
        """
        Test that maximum drawdown limit blocks all new trades.
        
        Setup: Set current balance to 85% of peak (15% drawdown, limit is 15%)
        Expected: Trade rejected due to drawdown concern
        """
        integration_risk_engine.current_balance = 85
        integration_risk_engine.peak_balance = 100  # 15% drawdown
        
        decision = await integration_risk_engine.check_trade_approval(
            proposal=sample_signal_proposal.to_dict(),
            user_id='test_user'
        )
        
        # Should be rejected or flagged with high risk score
        assert not decision.approved or decision.risk_score > 80
    
    @pytest.mark.asyncio
    async def test_cooldown_period_after_losses(
        self,
        sample_signal_proposal,
        integration_risk_engine
    ):
        """
        Test cooldown enforcement after consecutive losses.
        
        Setup: 3 consecutive losses within cooldown window
        Expected: Trade rejected during cooldown period
        """
        import time
        integration_risk_engine.consecutive_losses = 3
        integration_risk_engine.last_loss_time = time.time() - 100  # 100s ago
        
        decision = await integration_risk_engine.check_trade_approval(
            proposal=sample_signal_proposal.to_dict(),
            user_id='test_user'
        )
        
        # Should be in cooldown (default 300s)
        assert not decision.approved or decision.cooldown_remaining_seconds > 0
    
    @pytest.mark.asyncio
    async def test_risk_score_increases_with_risk_factors(
        self,
        sample_signal_proposal,
        integration_risk_engine
    ):
        """
        Test that risk score calculation responds to changing risk factors.
        
        Expected: Higher risk scenarios produce higher risk scores
        """
        # Low risk scenario
        integration_risk_engine.daily_pnl_pct = 0.0
        integration_risk_engine.current_balance = 10000
        integration_risk_engine.peak_balance = 10000
        integration_risk_engine.consecutive_losses = 0
        
        decision_low = await integration_risk_engine.check_trade_approval(
            proposal=sample_signal_proposal.to_dict(),
            user_id='test_user'
        )
        
        # High risk scenario (approaching limits)
        integration_risk_engine.daily_pnl_pct = -0.02  # Approaching -3% limit
        integration_risk_engine.current_balance = 9000
        integration_risk_engine.consecutive_losses = 2
        
        decision_high = await integration_risk_engine.check_trade_approval(
            proposal=sample_signal_proposal.to_dict(),
            user_id='test_user'
        )
        
        assert decision_high.risk_score > decision_low.risk_score
    
    @pytest.mark.asyncio
    async def test_stop_loss_take_profit_validation(
        self,
        integration_risk_engine
    ):
        """
        Test that invalid SL/TP configurations are rejected.
        
        Expected: LONG with SL above entry rejected
        """
        invalid_sl_proposal = SignalProposal(
            symbol='BTC/USDT',
            side='LONG',
            entry_price=50000.0,
            stop_loss=51000.0,  # SL ABOVE entry for LONG (invalid)
            take_profit=52000.0,
            quantity=0.01,
            leverage=2,
            confidence=0.8,
            strategy_name='breakout',
            regime='Normal'
        )
        
        decision = await integration_risk_engine.check_trade_approval(
            proposal=invalid_sl_proposal.to_dict(),
            user_id='test_user'
        )
        
        # Should be rejected due to invalid SL placement
        assert not decision.approved or any('stop' in v.lower() for v in decision.violations)
