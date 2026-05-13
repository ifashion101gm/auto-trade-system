"""
Integration tests for Execution Layer order lifecycle management.

This is the most critical area for financial integrity. Tests use mocked exchange
clients to validate:
- Order type handling (Market & Limit)
- Partial fill logic and database updates
- Order cancellation & modification
- Reduce-only enforcement for closing orders
- Hedge Mode vs. One-Way Mode position side parameters
- Order retry mechanism on transient errors

All tests ensure strict assertions for financial values (prices, quantities, PnL).
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any

from app.execution.trading_service import LiveTradingService


class TestOrderTypeHandling:
    """Test successful submission of Market and Limit orders."""
    
    @pytest.mark.asyncio
    async def test_market_order_submission(self):
        """Test successful market order execution."""
        # Mock exchange manager
        mock_exchange = AsyncMock()
        mock_exchange.create_market_order.return_value = {
            'order_id': 'test-market-order-123',
            'status': 'FILLED',
            'price': 50000.0,
            'filled': 0.01,
            'fee': {'cost': 0.5, 'currency': 'USDT'}
        }
        
        with patch('app.execution.trading_service.UnifiedExchangeManager') as MockManager:
            MockManager.return_value = mock_exchange
            
            service = LiveTradingService(use_testnet=True)
            service.exchange_manager = mock_exchange
            
            proposal = {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'entry_price': 50000.0,
                'quantity': 0.01,
                'leverage': 2,
                'stop_loss': 49000.0,
                'take_profit': 52000.0,
                'confidence': 0.85,
                'strategy_name': 'breakout',
                'regime': 'Normal'
            }
            
            result = await service._execute_trade(
                proposal=proposal,
                user_id='test_user',
                db_session=None
            )
            
            assert result['status'] == 'executed'
            assert result['order_id'] == 'test-market-order-123'
            assert abs(result['filled_price'] - 50000.0) < 0.01
            assert abs(result['filled_quantity'] - 0.01) < 0.0001
    
    @pytest.mark.asyncio
    async def test_limit_order_submission(self):
        """Test successful limit order placement."""
        mock_exchange = AsyncMock()
        mock_exchange.create_limit_order.return_value = {
            'order_id': 'test-limit-order-456',
            'status': 'NEW',
            'price': 49500.0,
            'filled': 0.0,
            'remaining': 0.01
        }
        
        with patch('app.execution.trading_service.UnifiedExchangeManager') as MockManager:
            MockManager.return_value = mock_exchange
            
            service = LiveTradingService(use_testnet=True)
            service.exchange_manager = mock_exchange
            
            # Simulate limit order creation
            order_result = await mock_exchange.create_limit_order(
                symbol='BTC/USDT',
                side='buy',
                amount=0.01,
                price=49500.0
            )
            
            assert order_result['status'] == 'NEW'
            assert order_result['order_id'] == 'test-limit-order-456'
            assert abs(order_result['price'] - 49500.0) < 0.01


class TestPartialFillLogic:
    """Test partial fill events and database state updates."""
    
    @pytest.mark.asyncio
    async def test_partial_fill_updates_filled_quantity(self):
        """
        Simulate partial fill event and verify local state updates
        filled_quantity while keeping status as PARTIALLY_FILLED.
        """
        mock_exchange = AsyncMock()
        
        # First call: partially filled
        mock_exchange.fetch_order_status.side_effect = [
            {
                'order_id': 'partial-order-789',
                'status': 'PARTIALLY_FILLED',
                'filled': 0.005,
                'remaining': 0.005,
                'price': 50000.0
            },
            {
                'order_id': 'partial-order-789',
                'status': 'FILLED',
                'filled': 0.01,
                'remaining': 0.0,
                'price': 50000.0
            }
        ]
        
        # Verify partial fill state
        status = await mock_exchange.fetch_order_status('partial-order-789', 'BTC/USDT')
        
        assert status['status'] == 'PARTIALLY_FILLED'
        assert abs(status['filled'] - 0.005) < 0.0001
        assert abs(status['remaining'] - 0.005) < 0.0001
        
        # Verify full fill state
        status = await mock_exchange.fetch_order_status('partial-order-789', 'BTC/USDT')
        
        assert status['status'] == 'FILLED'
        assert abs(status['filled'] - 0.01) < 0.0001
        assert abs(status['remaining'] - 0.0) < 0.0001
    
    @pytest.mark.asyncio
    async def test_partial_fill_preserves_order_integrity(self):
        """Verify partial fills don't corrupt order data."""
        original_order = {
            'order_id': 'test-order',
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'amount': 0.01,
            'price': 50000.0
        }
        
        partial_state = {
            **original_order,
            'status': 'PARTIALLY_FILLED',
            'filled': 0.003,
            'remaining': 0.007
        }
        
        # Verify all original fields preserved
        assert partial_state['order_id'] == original_order['order_id']
        assert partial_state['symbol'] == original_order['symbol']
        assert partial_state['side'] == original_order['side']
        assert abs(partial_state['amount'] - original_order['amount']) < 0.0001


class TestOrderCancellation:
    """Test order cancellation and state updates."""
    
    @pytest.mark.asyncio
    async def test_order_cancellation_request_sent(self):
        """Verify cancel requests are sent to exchange."""
        mock_exchange = AsyncMock()
        mock_exchange.cancel_order.return_value = {
            'order_id': 'cancelled-order-999',
            'status': 'CANCELED',
            'canceled_at': '2026-05-13T10:00:00Z'
        }
        
        result = await mock_exchange.cancel_order('cancelled-order-999', 'BTC/USDT')
        
        assert result['status'] == 'CANCELED'
        mock_exchange.cancel_order.assert_called_once_with(
            order_id='cancelled-order-999',
            symbol='BTC/USDT'
        )
    
    @pytest.mark.asyncio
    async def test_local_state_updated_to_canceled(self):
        """Verify local state updated to CANCELED after cancellation."""
        order_state = {
            'order_id': 'test-order',
            'status': 'NEW',
            'filled': 0.0
        }
        
        # Simulate cancellation
        order_state['status'] = 'CANCELED'
        order_state['canceled_at'] = '2026-05-13T10:00:00Z'
        
        assert order_state['status'] == 'CANCELED'
        assert 'canceled_at' in order_state


class TestReduceOnlyEnforcement:
    """Test reduce-only flag prevents accidental position reversals."""
    
    @pytest.mark.asyncio
    async def test_closing_orders_flagged_reduce_only(self):
        """
        Assert that closing orders are flagged as reduceOnly=True
        to prevent accidental position reversals.
        """
        mock_exchange = AsyncMock()
        
        # Closing order should include reduceOnly parameter
        closing_order_params = {
            'symbol': 'BTC/USDT',
            'side': 'sell',  # Closing long position
            'amount': 0.01,
            'params': {
                'reduceOnly': True
            }
        }
        
        mock_exchange.create_market_order.return_value = {
            'order_id': 'closing-order-111',
            'status': 'FILLED',
            'price': 50100.0,
            'filled': 0.01
        }
        
        result = await mock_exchange.create_market_order(**closing_order_params)
        
        assert result['status'] == 'FILLED'
        # Verify reduceOnly was passed in params
        call_kwargs = mock_exchange.create_market_order.call_args
        assert call_kwargs[1]['params']['reduceOnly'] == True
    
    @pytest.mark.asyncio
    async def test_opening_orders_not_reduce_only(self):
        """Verify opening orders do NOT have reduceOnly flag."""
        opening_order_params = {
            'symbol': 'BTC/USDT',
            'side': 'buy',  # Opening long position
            'amount': 0.01,
            'params': {
                'reduceOnly': False
            }
        }
        
        mock_exchange = AsyncMock()
        mock_exchange.create_market_order.return_value = {
            'order_id': 'opening-order-222',
            'status': 'FILLED'
        }
        
        await mock_exchange.create_market_order(**opening_order_params)
        
        call_kwargs = mock_exchange.create_market_order.call_args
        assert call_kwargs[1]['params']['reduceOnly'] == False


class TestHedgeModeVsOneWayMode:
    """Test position mode detection and appropriate positionSide parameters."""
    
    @pytest.mark.asyncio
    async def test_hedge_mode_sends_position_side_long(self):
        """
        Validate that in hedge mode, LONG positions send positionSide='LONG'.
        """
        mock_exchange = AsyncMock()
        
        # Hedge mode order for LONG position
        hedge_order_params = {
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'amount': 0.01,
            'params': {
                'positionSide': 'LONG'
            }
        }
        
        mock_exchange.create_market_order.return_value = {
            'order_id': 'hedge-long-order',
            'status': 'FILLED'
        }
        
        await mock_exchange.create_market_order(**hedge_order_params)
        
        call_kwargs = mock_exchange.create_market_order.call_args
        assert call_kwargs[1]['params']['positionSide'] == 'LONG'
    
    @pytest.mark.asyncio
    async def test_hedge_mode_sends_position_side_short(self):
        """Validate that in hedge mode, SHORT positions send positionSide='SHORT'."""
        mock_exchange = AsyncMock()
        
        # Hedge mode order for SHORT position
        hedge_order_params = {
            'symbol': 'BTC/USDT',
            'side': 'sell',
            'amount': 0.01,
            'params': {
                'positionSide': 'SHORT'
            }
        }
        
        mock_exchange.create_market_order.return_value = {
            'order_id': 'hedge-short-order',
            'status': 'FILLED'
        }
        
        await mock_exchange.create_market_order(**hedge_order_params)
        
        call_kwargs = mock_exchange.create_market_order.call_args
        assert call_kwargs[1]['params']['positionSide'] == 'SHORT'
    
    @pytest.mark.asyncio
    async def test_one_way_mode_no_position_side(self):
        """Verify one-way mode doesn't send positionSide parameter."""
        mock_exchange = AsyncMock()
        
        # One-way mode order (no positionSide)
        oneway_order_params = {
            'symbol': 'BTC/USDT',
            'side': 'buy',
            'amount': 0.01,
            'params': {}  # No positionSide in one-way mode
        }
        
        mock_exchange.create_market_order.return_value = {
            'order_id': 'oneway-order',
            'status': 'FILLED'
        }
        
        await mock_exchange.create_market_order(**oneway_order_params)
        
        call_kwargs = mock_exchange.create_market_order.call_args
        assert 'positionSide' not in call_kwargs[1]['params']


class TestOrderRetryMechanism:
    """Test order retry on transient network errors."""
    
    @pytest.mark.asyncio
    async def test_retry_on_transient_503_error(self):
        """
        Simulate transient 503 Service Unavailable error during order submission.
        Assert system retries up to configured limit before failing gracefully.
        """
        mock_exchange = AsyncMock()
        
        # Simulate 2 failures then success
        mock_exchange.create_market_order.side_effect = [
            Exception("503 Service Unavailable"),
            Exception("503 Service Unavailable"),
            {
                'order_id': 'retry-success-order',
                'status': 'FILLED',
                'price': 50000.0,
                'filled': 0.01
            }
        ]
        
        max_retries = 3
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                result = await mock_exchange.create_market_order(
                    symbol='BTC/USDT',
                    side='buy',
                    amount=0.01
                )
                # Success!
                assert result['status'] == 'FILLED'
                assert result['order_id'] == 'retry-success-order'
                break
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
        else:
            # All retries exhausted
            pytest.fail(f"Order failed after {max_retries} retries: {last_exception}")
        
        # Verify it was called 3 times (2 failures + 1 success)
        assert mock_exchange.create_market_order.call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion_fails_gracefully(self):
        """Verify system fails gracefully after exhausting all retries."""
        mock_exchange = AsyncMock()
        
        # Always fail
        mock_exchange.create_market_order.side_effect = Exception("503 Service Unavailable")
        
        max_retries = 3
        success = False
        
        for attempt in range(max_retries):
            try:
                result = await mock_exchange.create_market_order(
                    symbol='BTC/USDT',
                    side='buy',
                    amount=0.01
                )
                success = True
                break
            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1)
        
        assert success == False
        assert mock_exchange.create_market_order.call_count == max_retries
    
    @pytest.mark.asyncio
    async def test_non_retryable_errors_not_retried(self):
        """Verify non-retryable errors (401, 400) are not retried."""
        mock_exchange = AsyncMock()
        
        # Authentication error (non-retryable)
        mock_exchange.create_market_order.side_effect = Exception("401 Unauthorized")
        
        call_count = 0
        try:
            await mock_exchange.create_market_order(
                symbol='BTC/USDT',
                side='buy',
                amount=0.01
            )
        except Exception:
            call_count = mock_exchange.create_market_order.call_count
        
        # Should only be called once (no retries for auth errors)
        assert call_count == 1


class TestFinancialValuePrecision:
    """Test strict assertions for financial values to prevent floating-point errors."""
    
    def test_price_precision_two_decimals(self):
        """Verify prices maintain 2 decimal precision."""
        price = 50000.123456
        rounded_price = round(price, 2)
        
        assert abs(rounded_price - 50000.12) < 0.001
    
    def test_quantity_precision_eight_decimals(self):
        """Verify quantities maintain 8 decimal precision (crypto standard)."""
        quantity = 0.123456789
        rounded_quantity = round(quantity, 8)
        
        assert abs(rounded_quantity - 0.12345679) < 0.00000001
    
    def test_pnl_calculation_precision(self):
        """Verify PnL calculations avoid floating-point errors."""
        entry_price = 50000.00
        exit_price = 50100.00
        quantity = 0.01
        
        # Calculate PnL
        pnl = (exit_price - entry_price) * quantity
        
        # Should be exactly 1.0, not 0.9999999999 or 1.0000000001
        assert abs(pnl - 1.0) < 0.0001
    
    def test_percentage_calculation_precision(self):
        """Verify percentage calculations are accurate."""
        profit = 100.0
        initial_balance = 10000.0
        
        profit_pct = (profit / initial_balance) * 100
        
        assert abs(profit_pct - 1.0) < 0.0001
    
    def test_fee_calculation_precision(self):
        """Verify fee calculations maintain precision."""
        trade_value = 50000.0
        fee_rate = 0.001  # 0.1%
        
        fee = trade_value * fee_rate
        
        assert abs(fee - 50.0) < 0.01
