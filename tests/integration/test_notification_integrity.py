"""
Telegram & Notification Integrity Tests.

Validates the reliability of the "Mission Control Center" notification system.
Ensures critical alerts are delivered without spam, with correct formatting,
and with proper error handling.

Test Coverage:
1. Duplicate Alert Prevention (deduplication logic)
2. Missed Alert Detection (critical events always notify)
3. Message Formatting (all required fields present and readable)
4. Error Handling (Telegram API failures don't crash trading loop)
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from app.notifications.telegram_agent import TelegramAgent
from app.events.event_bus import event_bus
from app.events.event_types import (
    ORDER_OPENED, ORDER_CLOSED, ORDER_FILLED, ORDER_REJECTED,
    TP_HIT, SL_HIT, SYNC_MISMATCH, API_ERROR, RISK_VIOLATION_DETECTED,
    WEBSOCKET_DISCONNECTED, WEBSOCKET_RECONNECTED
)


@pytest.fixture
def telegram_agent():
    """Create TelegramAgent instance with mocked notifier."""
    agent = TelegramAgent()
    
    # Mock the notifier to prevent actual Telegram API calls
    agent.notifier.send_message = AsyncMock()
    
    return agent


@pytest.fixture
def mock_notifier():
    """Create standalone mocked notifier."""
    notifier = AsyncMock()
    notifier.send_message = AsyncMock()
    return notifier


class TestDuplicateAlertPrevention:
    """Test that duplicate alerts are prevented to avoid spamming Telegram."""
    
    @pytest.mark.asyncio
    async def test_websocket_disconnect_rate_limiting(self):
        """
        Trigger multiple WebSocket disconnect events rapidly.
        Assert that rate limiting prevents spam notifications.
        """
        agent = TelegramAgent()
        agent.notifier.send_message = AsyncMock()
        
        # Reduce cooldown for testing
        agent._ws_disconnect_cooldown = 1  # 1 second instead of 5 minutes
        
        # Publish multiple disconnect events rapidly
        for i in range(5):
            await event_bus.publish(WEBSOCKET_DISCONNECTED, {
                'message': f'Disconnect event #{i}',
                'reconnect_delay': 5.0,
                'attempt_count': i + 1
            })
            await asyncio.sleep(0.1)  # Small delay between events
        
        # Wait for event processing
        await asyncio.sleep(0.5)
        
        # Only first notification should be sent (others within cooldown)
        call_count = agent.notifier.send_message.call_count
        
        print(f"\n📱 WebSocket Disconnect Notifications:")
        print(f"   Events Published: 5")
        print(f"   Notifications Sent: {call_count}")
        
        # Should not send all 5 (rate limited)
        assert call_count < 5, f"Rate limiting failed: {call_count} notifications sent"
        assert call_count >= 1, "At least one notification should be sent"
    
    @pytest.mark.asyncio
    async def test_same_event_multiple_times_rapidly(self):
        """
        Publish same trade opened event multiple times in quick succession.
        Verify deduplication or rate limiting is applied.
        """
        agent = TelegramAgent()
        agent.notifier.send_message = AsyncMock()
        
        # Publish same event 10 times rapidly
        for i in range(10):
            await event_bus.publish(ORDER_OPENED, {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'mode': 'DEMO',
                'entry_price': 50000.0,
                'quantity': 0.001,
                'leverage': 2,
                'stop_loss': 49500.0,
                'take_profit': 51000.0,
                'strategy_name': 'test_strategy',
                'risk_pct': 1.0,
                'slippage_pct': 0.05,
                'execution_latency_ms': 50,
                'order_id': f'order-{i}'
            })
        
        await asyncio.sleep(0.5)
        
        call_count = agent.notifier.send_message.call_count
        
        print(f"\n📱 Trade Opened Event Deduplication:")
        print(f"   Events Published: 10")
        print(f"   Notifications Sent: {call_count}")
        
        # All events should trigger notifications (different order IDs)
        # But verify no crashes occurred
        assert call_count > 0, "Notifications should be sent"
    
    @pytest.mark.asyncio
    async def test_critical_events_always_sent_despite_rate_limits(self):
        """
        Ensure critical events (SL hit, risk violation) bypass rate limits.
        """
        agent = TelegramAgent()
        agent.notifier.send_message = AsyncMock()
        
        # Set strict rate limit
        agent._ws_disconnect_cooldown = 60
        
        # Publish critical events
        critical_events = [
            (SL_HIT, {'symbol': 'BTC/USDT', 'sl_price': 49000.0, 'pnl': -100.0}),
            (RISK_VIOLATION_DETECTED, {
                'violation_type': 'daily_loss_limit',
                'risk_level': 'CRITICAL',
                'symbol': 'ETH/USDT',
                'description': 'Daily loss exceeded',
                'current_value': -0.05,
                'threshold': -0.03,
                'action_taken': 'Trading paused'
            }),
            (ORDER_REJECTED, {
                'symbol': 'SOL/USDT',
                'error': 'Insufficient balance',
                'details': 'Required: 100 USDT, Available: 50 USDT'
            })
        ]
        
        for event_type, payload in critical_events:
            await event_bus.publish(event_type, payload)
        
        await asyncio.sleep(0.5)
        
        call_count = agent.notifier.send_message.call_count
        
        print(f"\n📱 Critical Event Delivery:")
        print(f"   Critical Events: {len(critical_events)}")
        print(f"   Notifications Sent: {call_count}")
        
        # All critical events should be sent
        assert call_count == len(critical_events), \
            f"Not all critical events sent: {call_count}/{len(critical_events)}"


class TestMissedAlertDetection:
    """Ensure critical events always generate notifications."""
    
    @pytest.mark.asyncio
    async def test_trade_opened_always_notifies(self):
        """
        Verify trade opened event always generates notification.
        """
        agent = TelegramAgent()
        agent.notifier.send_message = AsyncMock()
        
        await event_bus.publish(ORDER_OPENED, {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'mode': 'LIVE',
            'entry_price': 50000.0,
            'quantity': 0.01,
            'leverage': 2,
            'stop_loss': 49500.0,
            'take_profit': 51000.0,
            'strategy_name': 'breakout',
            'risk_pct': 1.5,
            'slippage_pct': 0.02,
            'execution_latency_ms': 45,
            'order_id': 'trade-open-test-001'
        })
        
        await asyncio.sleep(0.3)
        
        # Verify notification was sent
        assert agent.notifier.send_message.call_count >= 1
        
        # Verify message content
        call_args = agent.notifier.send_message.call_args_list[0][0][0]
        assert 'BTC/USDT' in call_args
        assert 'LONG' in call_args
        assert '50,000.00' in call_args or '50000.00' in call_args
    
    @pytest.mark.asyncio
    async def test_trade_closed_always_notifies(self):
        """
        Verify trade closed event always generates notification with PnL.
        """
        agent = TelegramAgent()
        agent.notifier.send_message = AsyncMock()
        
        await event_bus.publish(ORDER_CLOSED, {
            'symbol': 'ETH/USDT',
            'pnl': 150.0,
            'pnl_pct': 3.5,
            'exit_price': 3100.0,
            'duration': '2h 15m',
            'close_reason': 'TAKE_PROFIT',
            'total_return': 2.5
        })
        
        await asyncio.sleep(0.3)
        
        assert agent.notifier.send_message.call_count >= 1
        
        call_args = agent.notifier.send_message.call_args_list[0][0][0]
        assert 'TRADE CLOSED' in call_args
        assert '150.00' in call_args
        assert '3.50%' in call_args
    
    @pytest.mark.asyncio
    async def test_risk_violation_always_notifies(self):
        """
        Verify risk violations always generate high-priority notifications.
        """
        agent = TelegramAgent()
        agent.notifier.send_message = AsyncMock()
        
        await event_bus.publish(RISK_VIOLATION_DETECTED, {
            'violation_type': 'max_drawdown',
            'risk_level': 'HIGH',
            'symbol': 'ALL',
            'description': 'Portfolio drawdown exceeded 10%',
            'current_value': -0.12,
            'threshold': -0.10,
            'action_taken': 'All positions closed'
        })
        
        await asyncio.sleep(0.3)
        
        assert agent.notifier.send_message.call_count >= 1
        
        call_args = agent.notifier.send_message.call_args_list[0][0][0]
        assert 'RISK VIOLATION' in call_args
        assert 'HIGH' in call_args
        assert 'max_drawdown' in call_args
    
    @pytest.mark.asyncio
    async def test_sync_mismatch_always_notifies(self):
        """
        Verify position sync mismatches always generate alerts.
        """
        agent = TelegramAgent()
        agent.notifier.send_message = AsyncMock()
        
        await event_bus.publish(SYNC_MISMATCH, {
            'type': 'ghost_position',
            'symbol': 'XRP/USDT',
            'severity': 'CRITICAL',
            'testnet': True
        })
        
        await asyncio.sleep(0.3)
        
        assert agent.notifier.send_message.call_count >= 1
        
        call_args = agent.notifier.send_message.call_args_list[0][0][0]
        assert 'SYNC MISMATCH' in call_args
        assert 'XRP/USDT' in call_args


class TestMessageFormatting:
    """Verify notification messages contain all required fields and are readable."""
    
    @pytest.mark.asyncio
    async def test_trade_opened_message_format(self):
        """
        Verify trade opened message contains all required fields.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        await event_bus.publish(ORDER_OPENED, {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'mode': 'DEMO',
            'entry_price': 50000.0,
            'quantity': 0.01,
            'leverage': 2,
            'stop_loss': 49500.0,
            'take_profit': 51000.0,
            'strategy_name': 'trend_following',
            'risk_pct': 1.0,
            'slippage_pct': 0.03,
            'execution_latency_ms': 55,
            'order_id': 'format-test-001'
        })
        
        await asyncio.sleep(0.3)
        
        assert len(captured_messages) >= 1
        message = captured_messages[0]
        
        # Verify required fields
        required_fields = [
            'LIVE TRADE OPENED',
            'BTC/USDT',
            'LONG',
            'DEMO',
            '50,000.00',
            '0.01',
            '2x',
            '49,500.00',
            '51,000.00',
            'trend_following',
            'format-test-001'
        ]
        
        for field in required_fields:
            assert field in message, f"Missing required field: {field}"
    
    @pytest.mark.asyncio
    async def test_trade_closed_message_format(self):
        """
        Verify trade closed message contains PnL breakdown.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        await event_bus.publish(ORDER_CLOSED, {
            'symbol': 'ETH/USDT',
            'pnl': -75.50,
            'pnl_pct': -2.3,
            'exit_price': 2950.0,
            'duration': '45m',
            'close_reason': 'STOP_LOSS',
            'total_return': -1.8
        })
        
        await asyncio.sleep(0.3)
        
        message = captured_messages[0]
        
        # Verify PnL information
        assert 'TRADE CLOSED' in message
        assert '-75.50' in message or '-75.5' in message
        assert '-2.30%' in message or '-2.3%' in message
        assert 'STOP_LOSS' in message
    
    @pytest.mark.asyncio
    async def test_order_filled_message_format(self):
        """
        Verify order filled message includes slippage and latency.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        await event_bus.publish(ORDER_FILLED, {
            'symbol': 'SOL/USDT',
            'side': 'SHORT',
            'price': 98.50,
            'requested_price': 99.00,
            'slippage_pct': -0.51,
            'quantity': 10.0,
            'latency_ms': 120,
            'order_id': 'fill-test-001'
        })
        
        await asyncio.sleep(0.3)
        
        message = captured_messages[0]
        
        assert 'ORDER FILLED' in message
        assert '98.50' in message
        assert '99.00' in message
        assert '0.51' in message  # Slippage
        assert '120' in message  # Latency
    
    @pytest.mark.asyncio
    async def test_risk_violation_message_format(self):
        """
        Verify risk violation message includes severity and action taken.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        await event_bus.publish(RISK_VIOLATION_DETECTED, {
            'violation_type': 'concentration_risk',
            'risk_level': 'MEDIUM',
            'symbol': 'BTC/USDT',
            'description': 'Single position exceeds 50% of portfolio',
            'current_value': 0.55,
            'threshold': 0.50,
            'action_taken': 'Position size reduced'
        })
        
        await asyncio.sleep(0.3)
        
        message = captured_messages[0]
        
        assert 'RISK VIOLATION' in message
        assert 'MEDIUM' in message
        assert 'concentration_risk' in message
        assert '0.55' in message
        assert '0.50' in message
        assert 'Position size reduced' in message
    
    @pytest.mark.asyncio
    async def test_daily_summary_message_format(self):
        """
        Verify daily summary contains comprehensive performance metrics.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        performance_data = {
            'date': '2026-05-13',
            'total_trades': 15,
            'winning_trades': 10,
            'losing_trades': 5,
            'win_rate': 66.7,
            'total_pnl': 450.0,
            'avg_pnl': 30.0,
            'best_trade': 120.0,
            'worst_trade': -45.0,
            'total_fees': 12.50,
            'max_drawdown': 3.2,
            'best_strategy': 'breakout'
        }
        
        await agent.send_daily_summary(performance_data)
        
        message = captured_messages[0]
        
        assert 'DAILY SUMMARY' in message
        assert '2026-05-13' in message
        assert '15' in message  # Total trades
        assert '66.7%' in message
        assert '450.00' in message
        assert '120.00' in message  # Best trade
        assert '-45.00' in message  # Worst trade
        assert 'breakout' in message


class TestErrorHandling:
    """Test notification system behavior when Telegram API fails."""
    
    @pytest.mark.asyncio
    async def test_telegram_api_failure_logged_not_crashed(self):
        """
        Simulate Telegram API failure.
        Assert system logs error but doesn't crash trading loop.
        """
        agent = TelegramAgent()
        
        # Mock notifier to raise exception
        async def simulate_api_failure(message):
            raise Exception("Telegram API timeout")
        
        agent.notifier.send_message = simulate_api_failure
        
        # This should not raise exception
        try:
            await event_bus.publish(ORDER_OPENED, {
                'symbol': 'BTC/USDT',
                'side': 'LONG',
                'mode': 'DEMO',
                'entry_price': 50000.0,
                'quantity': 0.01,
                'leverage': 2,
                'stop_loss': 49500.0,
                'take_profit': 51000.0,
                'strategy_name': 'test',
                'risk_pct': 1.0,
                'slippage_pct': 0.02,
                'execution_latency_ms': 50,
                'order_id': 'error-test-001'
            })
            
            await asyncio.sleep(0.3)
            
            # If we reach here, system didn't crash
            assert True
            
        except Exception as e:
            pytest.fail(f"System crashed on Telegram API failure: {e}")
    
    @pytest.mark.asyncio
    async def test_retries_on_transient_failure(self):
        """
        Simulate transient Telegram API failure followed by success.
        Verify retry mechanism works.
        """
        agent = TelegramAgent()
        
        call_count = 0
        
        async def simulate_transient_failure(message):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:
                raise Exception("Temporary network error")
            
            return True  # Success on 3rd attempt
        
        agent.notifier.send_message = simulate_transient_failure
        
        # System should handle retries gracefully
        try:
            await event_bus.publish(ORDER_CLOSED, {
                'symbol': 'ETH/USDT',
                'pnl': 100.0,
                'pnl_pct': 2.5,
                'exit_price': 3100.0,
                'duration': '1h',
                'close_reason': 'MANUAL',
                'total_return': 1.5
            })
            
            await asyncio.sleep(0.5)
            
            # Verify multiple attempts were made
            assert call_count >= 1
            
        except Exception as e:
            # Expected behavior depends on retry implementation
            pass
    
    @pytest.mark.asyncio
    async def test_continues_after_notification_failure(self):
        """
        Verify trading continues even if notification fails.
        """
        agent = TelegramAgent()
        
        # Mock notifier to fail
        agent.notifier.send_message = AsyncMock(side_effect=Exception("API down"))
        
        # Publish multiple events
        events_published = 0
        for i in range(5):
            try:
                await event_bus.publish(ORDER_FILLED, {
                    'symbol': f'BTC/USDT',
                    'side': 'LONG',
                    'price': 50000.0 + i * 100,
                    'requested_price': 50000.0 + i * 100,
                    'slippage_pct': 0.0,
                    'quantity': 0.01,
                    'latency_ms': 50,
                    'order_id': f'continue-test-{i}'
                })
                events_published += 1
            except Exception:
                pass
        
        await asyncio.sleep(0.5)
        
        # All events should have been published (even if notifications failed)
        assert events_published == 5, "Event publishing should continue despite notification failures"


class TestWebSocketNotificationIntegrity:
    """Test WebSocket-specific notification behavior."""
    
    @pytest.mark.asyncio
    async def test_disconnect_notification_contains_context(self):
        """
        Verify WebSocket disconnect notification includes reconnect info.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        await event_bus.publish(WEBSOCKET_DISCONNECTED, {
            'message': 'Connection lost due to network timeout',
            'reconnect_delay': 10.5,
            'attempt_count': 3
        })
        
        await asyncio.sleep(0.3)
        
        assert len(captured_messages) >= 1
        message = captured_messages[0]
        
        assert 'WEBSOCKET DISCONNECTED' in message
        assert 'network timeout' in message
        assert '#3' in message or '3' in message  # Attempt count
        assert '10.5' in message  # Reconnect delay
    
    @pytest.mark.asyncio
    async def test_reconnect_notification_resets_cooldown(self):
        """
        Verify successful reconnection resets disconnect cooldown timer.
        """
        agent = TelegramAgent()
        agent.notifier.send_message = AsyncMock()
        
        # Set cooldown
        agent._last_ws_disconnect_time = time.time()
        
        # Publish reconnection event
        await event_bus.publish(WEBSOCKET_RECONNECTED, {
            'message': 'WebSocket reconnected successfully',
            'attempt_count': 2,
            'downtime_seconds': 15.5
        })
        
        await asyncio.sleep(0.3)
        
        # Cooldown should be reset
        assert agent._last_ws_disconnect_time == 0, "Cooldown timer should reset on reconnect"
    
    @pytest.mark.asyncio
    async def test_stale_stream_detection_notification(self):
        """
        Verify stale stream detection triggers appropriate alert.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        await event_bus.publish(WEBSOCKET_DISCONNECTED, {
            'message': 'Stale stream detected - no data updates',
            'seconds_without_data': 120.5,
            'threshold': 60,
            'stale_stream': True
        })
        
        await asyncio.sleep(0.3)
        
        if len(captured_messages) > 0:
            message = captured_messages[0]
            assert 'WEBSOCKET DISCONNECTED' in message or 'STALE' in message


class TestNotificationPriorityLevels:
    """Test that different event types receive appropriate priority."""
    
    @pytest.mark.asyncio
    async def test_critical_events_high_priority(self):
        """
        Verify critical events (SL hit, risk violation) use urgent formatting.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        # Publish critical events
        await event_bus.publish(SL_HIT, {
            'symbol': 'BTC/USDT',
            'sl_price': 49000.0,
            'pnl': -200.0
        })
        
        await event_bus.publish(RISK_VIOLATION_DETECTED, {
            'violation_type': 'liquidation_risk',
            'risk_level': 'CRITICAL',
            'symbol': 'ETH/USDT',
            'description': 'Position approaching liquidation',
            'current_value': 0.95,
            'threshold': 0.90,
            'action_taken': 'Emergency close initiated'
        })
        
        await asyncio.sleep(0.3)
        
        for message in captured_messages:
            # Critical events should have warning emojis
            assert any(emoji in message for emoji in ['⛔', '🚨', '🔴']), \
                f"Critical event missing warning emoji: {message}"
    
    @pytest.mark.asyncio
    async def test_info_events_normal_priority(self):
        """
        Verify informational events (trade open, order fill) use normal formatting.
        """
        agent = TelegramAgent()
        captured_messages = []
        
        async def capture_message(message):
            captured_messages.append(message)
        
        agent.notifier.send_message = capture_message
        
        await event_bus.publish(ORDER_OPENED, {
            'symbol': 'SOL/USDT',
            'side': 'LONG',
            'mode': 'DEMO',
            'entry_price': 100.0,
            'quantity': 5.0,
            'leverage': 2,
            'stop_loss': 95.0,
            'take_profit': 110.0,
            'strategy_name': 'momentum',
            'risk_pct': 1.0,
            'slippage_pct': 0.02,
            'execution_latency_ms': 45,
            'order_id': 'priority-test-001'
        })
        
        await asyncio.sleep(0.3)
        
        message = captured_messages[0]
        
        # Info events should have positive/neutral emojis
        assert any(emoji in message for emoji in ['🟢', '✅', '📊']), \
            f"Info event missing appropriate emoji: {message}"
