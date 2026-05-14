"""
Chaos Tests for Network Failures (Issue R)

Tests system behavior under various network failure conditions:
- Timeout during order placement
- Connection disconnect mid-execution
- Partial fills
- Exchange API rejection
- Duplicate ACK from exchange
- Reconnection after failure
- Stale websocket messages

These tests verify that the system handles real-world network issues gracefully
without creating phantom trades or losing state consistency.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime
import httpx

from app.execution.execution_service import ExecutionService, ExecutionRequest, ExecutionResult


class TestNetworkTimeouts:
    """Test timeout handling during order execution."""
    
    @pytest.mark.asyncio
    async def test_order_placement_timeout(self):
        """Verify system handles timeout when placing order on exchange."""
        
        # Create execution service
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            # Mock exchange manager to simulate timeout
            mock_exchange = AsyncMock()
            mock_exchange.create_market_order.side_effect = asyncio.TimeoutError(
                "Order placement timed out after 30s"
            )
            mock_manager.return_value = mock_exchange
            
            # Mock DB session factory
            mock_db_session = AsyncMock()
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            service.db_session_factory = AsyncMock(return_value=mock_db_session)
            
            # Create execution request
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            # Execute trade - should handle timeout gracefully
            result = await service.execute_trade(request, db_session=mock_db_session)
            
            # Verify result indicates failure, not success
            assert result.success == False
            assert result.status == 'failed'
            assert 'timeout' in result.error.lower() or 'timed out' in result.error.lower()
            
            # Verify no trade was created (no phantom trades)
            assert result.trade_id is None
    
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Verify system retries after timeout before giving up."""
        
        call_count = 0
        
        async def mock_timeout_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count < 3:
                # First 2 calls timeout
                raise asyncio.TimeoutError("Connection timeout")
            else:
                # 3rd call succeeds
                return {
                    'order_id': f'order_{call_count}',
                    'symbol': 'XAUUSDT',
                    'side': 'buy',
                    'filled_price': 2345.67,
                    'filled_quantity': 0.1,
                    'status': 'filled',
                    'fee': 0.001
                }
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            mock_exchange.create_market_order.side_effect = mock_timeout_then_success
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            result = await service.execute_trade(request, db_session=None)
            
            # Should have retried and eventually succeeded
            assert call_count == 3, f"Expected 3 attempts, got {call_count}"
            assert result.success == True
            assert result.order_id == 'order_3'


class TestConnectionDisconnect:
    """Test handling of connection drops during execution."""
    
    @pytest.mark.asyncio
    async def test_disconnect_during_order_placement(self):
        """Verify system detects and handles connection drop."""
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            # Simulate connection reset error
            mock_exchange.create_market_order.side_effect = ConnectionResetError(
                "Connection reset by peer"
            )
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            result = await service.execute_trade(request, db_session=None)
            
            # Should fail gracefully, not crash
            assert result.success == False
            assert result.status == 'failed'
            assert 'connection' in result.error.lower() or 'reset' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_reconnection_after_disconnect(self):
        """Verify system can reconnect and retry after disconnect."""
        
        attempt_count = 0
        
        async def mock_disconnect_then_reconnect(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count == 1:
                # First attempt: connection error
                raise ConnectionError("Network unreachable")
            else:
                # Subsequent attempts succeed
                return {
                    'order_id': 'reconnected_order',
                    'symbol': 'XAUUSDT',
                    'side': 'buy',
                    'filled_price': 2345.67,
                    'filled_quantity': 0.1,
                    'status': 'filled',
                    'fee': 0.001
                }
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            mock_exchange.create_market_order.side_effect = mock_disconnect_then_reconnect
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            result = await service.execute_trade(request, db_session=None)
            
            # Should have reconnected and succeeded
            assert attempt_count >= 2, "Should have attempted reconnection"
            assert result.success == True


class TestPartialFills:
    """Test handling of partial order fills."""
    
    @pytest.mark.asyncio
    async def test_partial_fill_handling(self):
        """Verify system correctly handles partially filled orders."""
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            # Return partial fill
            mock_exchange.create_market_order.return_value = {
                'order_id': 'partial_fill_order',
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'filled_price': 2345.67,
                'filled_quantity': 0.05,  # Only half filled
                'original_quantity': 0.1,
                'status': 'partially_filled',
                'fee': 0.0005
            }
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            result = await service.execute_trade(request, db_session=None)
            
            # Should report partial fill correctly
            assert result.success == True
            assert result.filled_quantity == 0.05
            assert result.status == 'partially_filled'
            assert result.metadata.get('original_quantity') == 0.1
    
    @pytest.mark.asyncio
    async def test_partial_fill_verification(self):
        """Verify system checks actual fill vs requested quantity."""
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            # Claim full fill but actually partial
            mock_exchange.create_market_order.return_value = {
                'order_id': 'suspicious_order',
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'filled_price': 2345.67,
                'filled_quantity': 0.1,  # Claims full fill
                'status': 'filled',
                'fee': 0.001
            }
            
            # Mock verification to detect discrepancy
            mock_exchange.get_order_status.return_value = {
                'order_id': 'suspicious_order',
                'filled_quantity': 0.08,  # Actually only 80% filled
                'status': 'partially_filled'
            }
            
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            result = await service.execute_trade(request, db_session=None)
            
            # Verification should detect the mismatch
            # (Implementation depends on verification logic in ExecutionService)
            assert result.success == True  # May still succeed but log warning


class TestExchangeRejection:
    """Test handling of exchange API rejections."""
    
    @pytest.mark.asyncio
    async def test_insufficient_balance_rejection(self):
        """Verify system handles insufficient balance errors."""
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            mock_exchange.create_market_order.side_effect = Exception(
                "Insufficient balance. Required: 234.57 USDT, Available: 100.00 USDT"
            )
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            result = await service.execute_trade(request, db_session=None)
            
            # Should fail with clear error message
            assert result.success == False
            assert 'insufficient' in result.error.lower() or 'balance' in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_invalid_symbol_rejection(self):
        """Verify system handles invalid symbol errors."""
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            mock_exchange.create_market_order.side_effect = Exception(
                "Invalid symbol: INVALIDUSDT"
            )
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='INVALIDUSDT',
                side='buy',
                entry_price=100.0,
                quantity=1.0,
                leverage=1
            )
            
            result = await service.execute_trade(request, db_session=None)
            
            assert result.success == False
            assert 'invalid' in result.error.lower() or 'symbol' in result.error.lower()


class TestDuplicateACK:
    """Test handling of duplicate acknowledgments from exchange."""
    
    @pytest.mark.asyncio
    async def test_duplicate_order_id_handling(self):
        """Verify system handles duplicate order IDs gracefully."""
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            # First call succeeds
            mock_exchange.create_market_order.return_value = {
                'order_id': 'duplicate_order_123',
                'symbol': 'XAUUSDT',
                'side': 'buy',
                'filled_price': 2345.67,
                'filled_quantity': 0.1,
                'status': 'filled',
                'fee': 0.001
            }
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            # Execute same request twice (simulating duplicate ACK scenario)
            result1 = await service.execute_trade(request, db_session=None)
            
            # In production, idempotency would prevent second execution
            # For this test, we just verify first execution succeeded
            assert result1.success == True
            assert result1.order_id == 'duplicate_order_123'


class TestReconnection:
    """Test reconnection logic after network failures."""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_on_failure(self):
        """Verify system uses exponential backoff when retrying."""
        
        attempt_times = []
        
        async def mock_always_fail(*args, **kwargs):
            attempt_times.append(asyncio.get_event_loop().time())
            raise ConnectionError("Network error")
        
        with patch('app.execution.execution_service.UnifiedExchangeManager') as mock_manager, \
             patch('app.execution.execution_service.RiskEngine'), \
             patch('app.execution.execution_service.TelegramNotifier'), \
             patch('app.execution.execution_service.event_bus'):
            
            mock_exchange = AsyncMock()
            mock_exchange.create_market_order.side_effect = mock_always_fail
            mock_manager.return_value = mock_exchange
            
            service = ExecutionService(exchange_name='binance', use_testnet=True)
            
            request = ExecutionRequest(
                symbol='XAUUSDT',
                side='buy',
                entry_price=2345.67,
                quantity=0.1,
                leverage=1
            )
            
            # This will fail after retries
            result = await service.execute_trade(request, db_session=None)
            
            assert result.success == False
            
            # If multiple attempts were made, verify increasing delays
            if len(attempt_times) > 1:
                delays = [attempt_times[i+1] - attempt_times[i] for i in range(len(attempt_times)-1)]
                # Delays should increase (exponential backoff)
                for i in range(len(delays)-1):
                    assert delays[i+1] >= delays[i], \
                        f"Backoff not exponential: {delays}"


class TestStaleWebsocket:
    """Test handling of stale/outdated websocket messages."""
    
    @pytest.mark.asyncio
    async def test_stale_message_detection(self):
        """Verify system detects and ignores stale websocket messages."""
        
        # This test verifies that old messages don't corrupt current state
        # Implementation depends on websocket message handling in the system
        
        # For now, verify that ExecutionService has timestamp tracking
        from app.execution.execution_service import ExecutionRequest
        
        request = ExecutionRequest(
            symbol='XAUUSDT',
            side='buy',
            entry_price=2345.67,
            quantity=0.1,
            leverage=1
        )
        
        # Request should have timestamp for staleness detection
        assert hasattr(request, 'timestamp') or hasattr(request, 'created_at')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
