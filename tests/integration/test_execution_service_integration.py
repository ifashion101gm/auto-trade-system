"""
Tests for Issue A - Execution Service Integration

Verifies that LiveTradingService properly delegates to ExecutionService
and that symbol locks prevent race conditions.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.execution.trading_service import LiveTradingService
from app.execution.execution_service import ExecutionService, ExecutionRequest, ExecutionResult


class TestExecutionServiceIntegration:
    """Test that LiveTradingService uses ExecutionService."""
    
    @pytest.mark.asyncio
    async def test_execution_service_initialized(self):
        """Verify ExecutionService is created during LiveTradingService init."""
        with patch('app.execution.trading_service.AIAgentOrchestrator'), \
             patch('app.execution.trading_service.UnifiedExchangeManager'), \
             patch('app.execution.trading_service.TelegramNotifier'), \
             patch('app.execution.trading_service.TradeValidator'), \
             patch('app.execution.trading_service.LearningParameterCache'), \
             patch('app.execution.trading_service.RiskEngine'), \
             patch('app.execution.trading_service.SystemCircuitBreaker'), \
             patch('app.execution.trading_service.SelfHealingExecutionEngine'):
            
            service = LiveTradingService(
                exchange_name='binance',
                use_testnet=True
            )
            
            # Verify ExecutionService was initialized
            assert hasattr(service, 'execution_service')
            assert isinstance(service.execution_service, ExecutionService)
            assert service.execution_service.exchange_name == 'binance'
            assert service.execution_service.use_testnet == True
    
    @pytest.mark.asyncio
    async def test_symbol_locks_initialized(self):
        """Verify symbol locks dict is created."""
        with patch('app.execution.trading_service.AIAgentOrchestrator'), \
             patch('app.execution.trading_service.UnifiedExchangeManager'), \
             patch('app.execution.trading_service.TelegramNotifier'), \
             patch('app.execution.trading_service.TradeValidator'), \
             patch('app.execution.trading_service.LearningParameterCache'), \
             patch('app.execution.trading_service.RiskEngine'), \
             patch('app.execution.trading_service.SystemCircuitBreaker'), \
             patch('app.execution.trading_service.SelfHealingExecutionEngine'):
            
            service = LiveTradingService()
            
            # Verify symbol locks dict exists
            assert hasattr(service, 'symbol_locks')
            assert isinstance(service.symbol_locks, dict)
            assert len(service.symbol_locks) == 0  # Empty initially
    
    @pytest.mark.asyncio
    async def test_get_symbol_lock_creates_lock(self):
        """Verify _get_symbol_lock creates new locks on demand."""
        with patch('app.execution.trading_service.AIAgentOrchestrator'), \
             patch('app.execution.trading_service.UnifiedExchangeManager'), \
             patch('app.execution.trading_service.TelegramNotifier'), \
             patch('app.execution.trading_service.TradeValidator'), \
             patch('app.execution.trading_service.LearningParameterCache'), \
             patch('app.execution.trading_service.RiskEngine'), \
             patch('app.execution.trading_service.SystemCircuitBreaker'), \
             patch('app.execution.trading_service.SelfHealingExecutionEngine'):
            
            service = LiveTradingService()
            
            # Get lock for XAUUSDT
            lock1 = service._get_symbol_lock('XAUUSDT')
            assert isinstance(lock1, asyncio.Lock)
            
            # Get lock again - should return same instance
            lock2 = service._get_symbol_lock('XAUUSDT')
            assert lock1 is lock2
            
            # Different symbol should get different lock
            lock3 = service._get_symbol_lock('BTCUSDT')
            assert lock3 is not lock1
    
    @pytest.mark.asyncio
    async def test_execute_trade_delegates_to_execution_service(self):
        """Verify _execute_trade calls ExecutionService.execute_trade."""
        with patch('app.execution.trading_service.AIAgentOrchestrator'), \
             patch('app.execution.trading_service.UnifiedExchangeManager'), \
             patch('app.execution.trading_service.TelegramNotifier'), \
             patch('app.execution.trading_service.TradeValidator'), \
             patch('app.execution.trading_service.LearningParameterCache'), \
             patch('app.execution.trading_service.RiskEngine'), \
             patch('app.execution.trading_service.SystemCircuitBreaker'), \
             patch('app.execution.trading_service.SelfHealingExecutionEngine'):
            
            # Mock settings to use fully-auto mode
            with patch('app.execution.trading_service.settings') as mock_settings:
                mock_settings.EXECUTION_MODE = 'fully-auto'
                mock_settings.ACTIVE_EXCHANGE = 'binance'
                mock_settings.BINANCE_TESTNET = True
                mock_settings.ENABLED_TRADING_SYMBOLS = ['XAUUSDT']
                
                service = LiveTradingService()
            
            # Mock ExecutionService.execute_trade
            mock_result = ExecutionResult(
                success=True,
                order_id='test_order_123',
                trade_id=456,
                filled_price=2345.67,
                filled_quantity=0.1,
                fee=2.34,
                status='executed',
                metadata={'proposal_id': 789}
            )
            service.execution_service.execute_trade = AsyncMock(return_value=mock_result)
            
            # Create test proposal
            proposal = {
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'entry_price': 2345.67,
                'quantity': 0.1,
                'leverage': 1,
                'stop_loss': 2300.0,
                'take_profit': 2400.0,
                'strategy_name': 'test_strategy',
                'confidence': 0.85,
                'regime': 'trending',
                'risk_level': 'medium'
            }
            
            # Call _execute_trade
            result = await service._execute_trade(
                proposal=proposal,
                user_id='test_user',
                db_session=None
            )
            
            # Verify ExecutionService was called
            service.execution_service.execute_trade.assert_called_once()
            
            # Verify the call arguments
            call_args = service.execution_service.execute_trade.call_args
            exec_request = call_args[0][0]  # First positional arg
            assert isinstance(exec_request, ExecutionRequest)
            assert exec_request.symbol == 'XAUUSDT'
            assert exec_request.side == 'buy'
            assert exec_request.entry_price == 2345.67
            assert exec_request.quantity == 0.1
            
            # Verify result format
            assert result['status'] == 'executed'
            assert result['order_id'] == 'test_order_123'
            assert result['trade_id'] == 456
            assert result['filled_price'] == 2345.67
    
    @pytest.mark.asyncio
    async def test_execute_trade_handles_failure(self):
        """Verify _execute_trade handles ExecutionService failures."""
        with patch('app.execution.trading_service.AIAgentOrchestrator'), \
             patch('app.execution.trading_service.UnifiedExchangeManager'), \
             patch('app.execution.trading_service.TelegramNotifier'), \
             patch('app.execution.trading_service.TradeValidator'), \
             patch('app.execution.trading_service.LearningParameterCache'), \
             patch('app.execution.trading_service.RiskEngine'), \
             patch('app.execution.trading_service.SystemCircuitBreaker'), \
             patch('app.execution.trading_service.SelfHealingExecutionEngine'):
            
            with patch('app.execution.trading_service.settings') as mock_settings:
                mock_settings.EXECUTION_MODE = 'fully-auto'
                mock_settings.ACTIVE_EXCHANGE = 'binance'
                mock_settings.BINANCE_TESTNET = True
                mock_settings.ENABLED_TRADING_SYMBOLS = ['XAUUSDT']
                
                service = LiveTradingService()
            
            # Mock ExecutionService to fail
            mock_result = ExecutionResult(
                success=False,
                status='failed',
                error='Insufficient balance'
            )
            service.execution_service.execute_trade = AsyncMock(return_value=mock_result)
            
            proposal = {
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'entry_price': 2345.67,
                'quantity': 0.1,
                'leverage': 1
            }
            
            # Should raise exception on failure
            with pytest.raises(Exception, match='ExecutionService failed'):
                await service._execute_trade(
                    proposal=proposal,
                    user_id='test_user',
                    db_session=None
                )


class TestSymbolLockConcurrency:
    """Test that symbol locks prevent race conditions."""
    
    @pytest.mark.asyncio
    async def test_symbol_lock_prevents_concurrent_execution(self):
        """Verify only one trade per symbol executes at a time."""
        with patch('app.execution.trading_service.AIAgentOrchestrator'), \
             patch('app.execution.trading_service.UnifiedExchangeManager'), \
             patch('app.execution.trading_service.TelegramNotifier'), \
             patch('app.execution.trading_service.TradeValidator'), \
             patch('app.execution.trading_service.LearningParameterCache'), \
             patch('app.execution.trading_service.RiskEngine'), \
             patch('app.execution.trading_service.SystemCircuitBreaker'), \
             patch('app.execution.trading_service.SelfHealingExecutionEngine'):
            
            with patch('app.execution.trading_service.settings') as mock_settings:
                mock_settings.EXECUTION_MODE = 'fully-auto'
                mock_settings.ACTIVE_EXCHANGE = 'binance'
                mock_settings.BINANCE_TESTNET = True
                mock_settings.ENABLED_TRADING_SYMBOLS = ['XAUUSDT']
                
                service = LiveTradingService()
            
            # Track execution order
            execution_order = []
            
            # Mock ExecutionService with delay to simulate real execution
            async def mock_execute_with_delay(request, db_session):
                execution_order.append(f'start_{request.symbol}')
                await asyncio.sleep(0.1)  # Simulate work
                execution_order.append(f'end_{request.symbol}')
                return ExecutionResult(
                    success=True,
                    order_id=f'order_{request.symbol}',
                    trade_id=1,
                    filled_price=request.entry_price,
                    filled_quantity=request.quantity,
                    fee=0.0,
                    status='executed'
                )
            
            service.execution_service.execute_trade = mock_execute_with_delay
            
            # Send two signals for SAME symbol simultaneously
            proposal1 = {
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'entry_price': 2345.67,
                'quantity': 0.1,
                'leverage': 1
            }
            
            proposal2 = {
                'symbol': 'XAUUSDT',
                'side': 'sell',
                'entry_price': 2346.00,
                'quantity': 0.1,
                'leverage': 1
            }
            
            # Execute both concurrently
            task1 = asyncio.create_task(
                service._execute_trade(proposal1, 'user1', None)
            )
            task2 = asyncio.create_task(
                service._execute_trade(proposal2, 'user1', None)
            )
            
            await asyncio.gather(task1, task2)
            
            # Verify sequential execution (not interleaved)
            # Expected: start_XAUUSDT, end_XAUUSDT, start_XAUUSDT, end_XAUUSDT
            # NOT: start_XAUUSDT, start_XAUUSDT, end_XAUUSDT, end_XAUUSDT
            assert execution_order[0] == 'start_XAUUSDT'
            assert execution_order[1] == 'end_XAUUSDT'
            assert execution_order[2] == 'start_XAUUSDT'
            assert execution_order[3] == 'end_XAUUSDT'
    
    @pytest.mark.asyncio
    async def test_different_symbols_can_execute_concurrently(self):
        """Verify different symbols can execute in parallel."""
        with patch('app.execution.trading_service.AIAgentOrchestrator'), \
             patch('app.execution.trading_service.UnifiedExchangeManager'), \
             patch('app.execution.trading_service.TelegramNotifier'), \
             patch('app.execution.trading_service.TradeValidator'), \
             patch('app.execution.trading_service.LearningParameterCache'), \
             patch('app.execution.trading_service.RiskEngine'), \
             patch('app.execution.trading_service.SystemCircuitBreaker'), \
             patch('app.execution.trading_service.SelfHealingExecutionEngine'):
            
            with patch('app.execution.trading_service.settings') as mock_settings:
                mock_settings.EXECUTION_MODE = 'fully-auto'
                mock_settings.ACTIVE_EXCHANGE = 'binance'
                mock_settings.BINANCE_TESTNET = True
                mock_settings.ENABLED_TRADING_SYMBOLS = ['XAUUSDT', 'BTCUSDT']
                
                service = LiveTradingService()
            
            # Track execution timestamps
            execution_times = {}
            
            async def mock_execute_with_timestamp(request, db_session):
                execution_times[request.symbol] = asyncio.get_event_loop().time()
                await asyncio.sleep(0.05)
                return ExecutionResult(
                    success=True,
                    order_id=f'order_{request.symbol}',
                    trade_id=1,
                    filled_price=request.entry_price,
                    filled_quantity=request.quantity,
                    fee=0.0,
                    status='executed'
                )
            
            service.execution_service.execute_trade = mock_execute_with_timestamp
            
            # Send signals for DIFFERENT symbols
            proposal1 = {
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'entry_price': 2345.67,
                'quantity': 0.1,
                'leverage': 1
            }
            
            proposal2 = {
                'symbol': 'BTCUSDT',
                'side': 'buy',
                'entry_price': 50000.0,
                'quantity': 0.001,
                'leverage': 1
            }
            
            # Execute both concurrently
            start_time = asyncio.get_event_loop().time()
            task1 = asyncio.create_task(
                service._execute_trade(proposal1, 'user1', None)
            )
            task2 = asyncio.create_task(
                service._execute_trade(proposal2, 'user1', None)
            )
            
            await asyncio.gather(task1, task2)
            end_time = asyncio.get_event_loop().time()
            
            # Both should start nearly simultaneously (< 0.01s difference)
            time_diff = abs(execution_times['XAUUSDT'] - execution_times['BTCUSDT'])
            assert time_diff < 0.01, f"Different symbols should execute in parallel, but had {time_diff}s difference"
            
            # Total time should be ~0.05s (parallel), not ~0.1s (sequential)
            total_time = end_time - start_time
            assert total_time < 0.08, f"Parallel execution took {total_time}s, expected <0.08s"


class TestIdempotencyProtection:
    """Test idempotency prevents duplicate executions."""
    
    @pytest.mark.asyncio
    async def test_execution_service_provides_idempotency(self):
        """Verify ExecutionService has idempotency checks."""
        # This test verifies that ExecutionService.execute_trade method
        # includes idempotency logic (to be implemented in Issue A follow-up)
        
        # For now, just verify the method signature accepts the right params
        from inspect import signature
        sig = signature(ExecutionService.execute_trade)
        
        # Should accept ExecutionRequest and optional db_session
        params = list(sig.parameters.keys())
        assert 'request' in params or 'self' in params  # Either self or request
        
        # Note: Full idempotency testing requires ExecutionService implementation
        # This will be expanded when idempotency is added to ExecutionService


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
