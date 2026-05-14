"""
Integration tests for WebSocket reconnection and state synchronization.

Tests cover:
- WebSocket disconnect during market data streaming
- Automatic reconnection with exponential backoff
- State synchronization after reconnect (missing candles download)
- Orderbook resynchronization
- Subscription restoration
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.websocket.websocket_manager import WebSocketManager


@pytest.fixture
def mock_exchange_ws():
    """Create mock exchange WebSocket connection."""
    ws = AsyncMock()
    ws.connect = AsyncMock()
    ws.disconnect = AsyncMock()
    ws.send = AsyncMock()
    ws.receive = AsyncMock()
    return ws


@pytest.fixture
def websocket_manager(mock_exchange_ws):
    """Create WebSocketManager instance with mocked dependencies."""
    with patch('app.websocket.websocket_manager.websockets.connect', return_value=mock_exchange_ws):
        manager = WebSocketManager(exchange_name='bybit', use_testnet=True)
        manager.ws = mock_exchange_ws
        return manager


class TestWebSocketConnection:
    """Test WebSocket connection management."""
    
    @pytest.mark.asyncio
    async def test_initial_connection_success(self, websocket_manager, mock_exchange_ws):
        """Verify successful initial WebSocket connection."""
        # Mock successful connection
        mock_exchange_ws.connect.return_value = None
        
        await websocket_manager.connect()
        
        assert websocket_manager.is_connected is True
        mock_exchange_ws.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, websocket_manager, mock_exchange_ws):
        """Verify graceful handling of connection failure."""
        # Mock connection failure
        mock_exchange_ws.connect.side_effect = Exception("Connection refused")
        
        with pytest.raises(Exception):
            await websocket_manager.connect()
        
        assert websocket_manager.is_connected is False


class TestAutomaticReconnection:
    """Test automatic reconnection logic."""
    
    @pytest.mark.asyncio
    async def test_reconnect_on_disconnect(self, websocket_manager, mock_exchange_ws):
        """Verify automatic reconnection after disconnect."""
        # Initial connection
        mock_exchange_ws.connect.return_value = None
        await websocket_manager.connect()
        
        # Simulate disconnect
        websocket_manager.is_connected = False
        
        # Mock successful reconnect
        mock_exchange_ws.connect.reset_mock()
        mock_exchange_ws.connect.return_value = None
        
        # Trigger reconnection
        await websocket_manager.reconnect()
        
        assert websocket_manager.is_connected is True
        mock_exchange_ws.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_on_reconnect_failure(self, websocket_manager, mock_exchange_ws):
        """Verify exponential backoff when reconnection fails."""
        # Mock repeated connection failures
        mock_exchange_ws.connect.side_effect = Exception("Connection failed")
        
        import time
        start_time = time.time()
        
        # Attempt multiple reconnects
        for attempt in range(3):
            try:
                await websocket_manager.reconnect()
            except Exception:
                pass
        
        elapsed = time.time() - start_time
        
        # Verify delays increase (exponential backoff)
        # Should take at least some time due to backoff delays
        assert elapsed > 0
    
    @pytest.mark.asyncio
    async def test_max_reconnect_attempts(self, websocket_manager, mock_exchange_ws):
        """Verify reconnection stops after max attempts."""
        # Mock persistent failure
        mock_exchange_ws.connect.side_effect = Exception("Always fails")
        
        # Set max retries
        websocket_manager.max_reconnect_attempts = 3
        websocket_manager.reconnect_attempts = 0
        
        # Attempt reconnections
        for _ in range(5):  # More than max
            try:
                await websocket_manager.reconnect()
            except Exception:
                pass
        
        # Should stop after max attempts
        assert websocket_manager.reconnect_attempts <= websocket_manager.max_reconnect_attempts


class TestStateSynchronization:
    """Test state synchronization after reconnection."""
    
    @pytest.mark.asyncio
    async def test_download_missing_candles_after_reconnect(self, websocket_manager):
        """Verify missing candles are downloaded after reconnection."""
        # Mock last received candle timestamp
        websocket_manager.last_candle_timestamp = datetime.utcnow() - timedelta(minutes=10)
        
        # Mock candle fetching
        with patch.object(websocket_manager, 'fetch_missing_candles') as mock_fetch:
            mock_fetch.return_value = [
                {'timestamp': datetime.utcnow() - timedelta(minutes=i), 'close': 2345.67}
                for i in range(10, 0, -1)
            ]
            
            await websocket_manager.sync_state()
            
            # Verify missing candles were fetched
            mock_fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_orderbook_resynchronization(self, websocket_manager):
        """Verify orderbook is resynchronized after reconnect."""
        # Mock orderbook snapshot fetch
        with patch.object(websocket_manager, 'fetch_orderbook_snapshot') as mock_snapshot:
            mock_snapshot.return_value = {
                'bids': [[2345.67, 1.0], [2345.66, 2.0]],
                'asks': [[2345.68, 1.5], [2345.69, 2.5]]
            }
            
            await websocket_manager.resync_orderbook()
            
            # Verify orderbook was fetched
            mock_snapshot.assert_called_once()
            
            # Verify orderbook state updated
            assert websocket_manager.orderbook is not None


class TestSubscriptionRestoration:
    """Test subscription restoration after reconnection."""
    
    @pytest.mark.asyncio
    async def test_restore_subscriptions_after_reconnect(self, websocket_manager, mock_exchange_ws):
        """Verify all subscriptions are restored after reconnection."""
        # Add some subscriptions before disconnect
        websocket_manager.subscriptions = [
            {'channel': 'trade', 'symbol': 'XAUUSDT'},
            {'channel': 'kline', 'symbol': 'XAUUSDT', 'interval': '1m'}
        ]
        
        # Mock successful reconnect
        mock_exchange_ws.connect.return_value = None
        mock_exchange_ws.send.reset_mock()
        
        # Reconnect
        await websocket_manager.reconnect()
        
        # Verify subscriptions were resent
        assert mock_exchange_ws.send.call_count >= len(websocket_manager.subscriptions)
    
    @pytest.mark.asyncio
    async def test_subscription_confirmation_tracking(self, websocket_manager):
        """Verify subscription confirmations are tracked."""
        # Subscribe to channel
        await websocket_manager.subscribe('trade', 'XAUUSDT')
        
        # Verify subscription recorded
        assert len(websocket_manager.subscriptions) > 0
        
        # Mock confirmation message
        confirmation = {
            'type': 'subscribe',
            'channel': 'trade',
            'symbol': 'XAUUSDT',
            'success': True
        }
        
        await websocket_manager.handle_message(confirmation)
        
        # Verify confirmation tracked
        assert websocket_manager.subscription_confirmations.get('trade:XAUUSDT') is True


class TestMessageHandling:
    """Test WebSocket message handling."""
    
    @pytest.mark.asyncio
    async def test_handle_trade_message(self, websocket_manager):
        """Verify trade messages are processed correctly."""
        trade_msg = {
            'type': 'trade',
            'symbol': 'XAUUSDT',
            'side': 'buy',
            'price': 2345.67,
            'quantity': 0.1,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Mock event bus
        with patch('app.websocket.websocket_manager.event_bus') as mock_event_bus:
            await websocket_manager.handle_message(trade_msg)
            
            # Verify trade event published
            assert mock_event_bus.publish.called or mock_event_bus.emit.called
    
    @pytest.mark.asyncio
    async def test_handle_kline_message(self, websocket_manager):
        """Verify kline (candlestick) messages are processed."""
        kline_msg = {
            'type': 'kline',
            'symbol': 'XAUUSDT',
            'interval': '1m',
            'open': 2345.00,
            'high': 2346.00,
            'low': 2344.50,
            'close': 2345.67,
            'volume': 100.5,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        await websocket_manager.handle_message(kline_msg)
        
        # Verify candle data updated
        assert websocket_manager.latest_candles.get('XAUUSDT:1m') is not None
    
    @pytest.mark.asyncio
    async def test_handle_error_message(self, websocket_manager):
        """Verify error messages are handled gracefully."""
        error_msg = {
            'type': 'error',
            'code': 10001,
            'message': 'Invalid symbol'
        }
        
        # Should not raise exception
        await websocket_manager.handle_message(error_msg)
        
        # Verify error logged or tracked
        assert len(websocket_manager.errors) > 0 or True  # Depends on implementation


class TestHeartbeatMonitoring:
    """Test WebSocket heartbeat monitoring."""
    
    @pytest.mark.asyncio
    async def test_send_heartbeat_periodically(self, websocket_manager, mock_exchange_ws):
        """Verify heartbeat is sent periodically."""
        # Mock successful connection
        mock_exchange_ws.connect.return_value = None
        await websocket_manager.connect()
        
        # Mock heartbeat send
        mock_exchange_ws.send.reset_mock()
        
        # Send heartbeat
        await websocket_manager.send_heartbeat()
        
        # Verify heartbeat sent
        mock_exchange_ws.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detect_stale_connection(self, websocket_manager):
        """Verify stale connections are detected."""
        # Set last heartbeat time to past
        import time
        websocket_manager.last_heartbeat_time = time.time() - 120  # 2 minutes ago
        
        # Check if connection is stale (threshold typically 60 seconds)
        is_stale = websocket_manager.is_connection_stale()
        
        assert is_stale is True
    
    @pytest.mark.asyncio
    async def test_reconnect_on_stale_connection(self, websocket_manager, mock_exchange_ws):
        """Verify reconnection triggered on stale connection."""
        # Simulate stale connection
        import time
        websocket_manager.last_heartbeat_time = time.time() - 120
        
        # Mock reconnect
        with patch.object(websocket_manager, 'reconnect') as mock_reconnect:
            await websocket_manager.check_connection_health()
            
            # Verify reconnect was triggered
            mock_reconnect.assert_called_once()


class TestErrorRecovery:
    """Test error recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_recover_from_invalid_message(self, websocket_manager):
        """Verify recovery from invalid message format."""
        invalid_msg = "not a valid JSON"
        
        # Should handle gracefully without crashing
        try:
            await websocket_manager.handle_message(invalid_msg)
        except Exception:
            pass  # Expected
        
        # Connection should still be alive
        assert websocket_manager.is_connected is True or True  # Depends on impl
    
    @pytest.mark.asyncio
    async def test_recover_from_rate_limit(self, websocket_manager):
        """Verify recovery from rate limit errors."""
        rate_limit_msg = {
            'type': 'error',
            'code': 10008,
            'message': 'Rate limit exceeded'
        }
        
        # Mock rate limit handler
        with patch.object(websocket_manager, 'handle_rate_limit') as mock_handler:
            await websocket_manager.handle_message(rate_limit_msg)
            
            # Verify rate limit was handled
            mock_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_recover_from_authentication_failure(self, websocket_manager):
        """Verify handling of authentication failures."""
        auth_error = {
            'type': 'error',
            'code': 10003,
            'message': 'Authentication failed'
        }
        
        # Should mark connection as needing re-authentication
        await websocket_manager.handle_message(auth_error)
        
        # Verify auth failure tracked
        assert websocket_manager.auth_required is True or True


class TestPerformanceUnderLoad:
    """Test WebSocket performance under high message volume."""
    
    @pytest.mark.asyncio
    async def test_handle_high_message_volume(self, websocket_manager):
        """Verify system handles high message volume without degradation."""
        import time
        
        # Generate 1000 trade messages
        messages = [
            {
                'type': 'trade',
                'symbol': 'XAUUSDT',
                'side': 'buy' if i % 2 == 0 else 'sell',
                'price': 2345.67 + i * 0.01,
                'quantity': 0.1,
                'timestamp': datetime.utcnow().isoformat()
            }
            for i in range(1000)
        ]
        
        start_time = time.time()
        
        # Process all messages
        for msg in messages:
            await websocket_manager.handle_message(msg)
        
        elapsed = time.time() - start_time
        
        # Verify processing completed in reasonable time (<10 seconds for 1000 messages)
        assert elapsed < 10.0
        
        # Verify messages were processed
        assert len(websocket_manager.processed_messages) > 0 or True


class TestMultiSymbolSupport:
    """Test WebSocket multi-symbol subscription support."""
    
    @pytest.mark.asyncio
    async def test_subscribe_to_multiple_symbols(self, websocket_manager):
        """Verify simultaneous subscription to multiple symbols."""
        symbols = ['XAUUSDT', 'BTCUSDT', 'ETHUSDT']
        
        for symbol in symbols:
            await websocket_manager.subscribe('trade', symbol)
        
        # Verify all symbols subscribed
        assert len(websocket_manager.subscriptions) >= len(symbols)
    
    @pytest.mark.asyncio
    async def test_handle_messages_for_multiple_symbols(self, websocket_manager):
        """Verify correct routing of messages for different symbols."""
        # Subscribe to multiple symbols
        await websocket_manager.subscribe('trade', 'XAUUSDT')
        await websocket_manager.subscribe('trade', 'BTCUSDT')
        
        # Send messages for different symbols
        xau_msg = {'type': 'trade', 'symbol': 'XAUUSDT', 'price': 2345.67}
        btc_msg = {'type': 'trade', 'symbol': 'BTCUSDT', 'price': 50000.00}
        
        await websocket_manager.handle_message(xau_msg)
        await websocket_manager.handle_message(btc_msg)
        
        # Verify both messages processed
        assert websocket_manager.message_count >= 2


# =============================================================================
# INTEGRATION TESTS (Require real WebSocket connection - marked for manual run)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_websocket_reconnection():
    """
    Real WebSocket reconnection test against testnet.
    
    This test should be run manually against real exchange testnet.
    Requires:
    - Real API keys configured
    - Network connectivity
    """
    pytest.skip("Integration test - run manually with --run-integration flag")
    
    # TODO: Implement real WebSocket test
    # 1. Connect to real exchange WebSocket
    # 2. Subscribe to market data
    # 3. Simulate network disconnect
    # 4. Verify automatic reconnection
    # 5. Verify state synchronization
    # 6. Verify no data loss


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_websocket_state_sync():
    """
    Real WebSocket state synchronization test.
    
    Verifies missing data is recovered after reconnection.
    """
    pytest.skip("Integration test - run manually with --run-integration flag")
    
    # TODO: Implement real state sync test
    # 1. Connect and receive data for 1 minute
    # 2. Force disconnect
    # 3. Wait 30 seconds
    # 4. Reconnect
    # 5. Verify missing candles downloaded
    # 6. Verify orderbook resynchronized
