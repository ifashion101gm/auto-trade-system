"""
Telegram Agent - Event-driven notification system.
Only reads from database events, never directly from strategy.

Subscribes to all trading events and sends formatted Telegram notifications.
"""
from app.notifications.notifier import TelegramNotifier
from app.events.event_bus import event_bus
from app.events.event_types import (
    ORDER_OPENED, ORDER_CLOSED, ORDER_FILLED, ORDER_REJECTED,
    TP_HIT, SL_HIT, POSITION_UPDATED,
    SYNC_MISMATCH, API_ERROR, WEBSOCKET_DISCONNECTED, WEBSOCKET_RECONNECTED,
    DAILY_SUMMARY_READY, ORDER_STATE_CHANGED, RISK_VIOLATION_DETECTED,
    RECOVERY_ACTION_TAKEN, RECONCILIATION_ACTION, SYNC_REPAIRED
)
import logging

logger = logging.getLogger(__name__)


class TelegramAgent:
    """Event-driven Telegram notification system."""
    
    def __init__(self):
        self.notifier = TelegramNotifier()
        self._setup_subscriptions()
        
        # Rate limiting for WebSocket notifications
        self._last_ws_disconnect_time = 0
        self._ws_disconnect_cooldown = 300  # 5 minutes cooldown between disconnect notifications
    
    def _setup_subscriptions(self):
        """Subscribe to all relevant events."""
        event_bus.subscribe(ORDER_OPENED, self._on_trade_opened)
        event_bus.subscribe(ORDER_FILLED, self._on_order_filled)
        event_bus.subscribe(ORDER_CLOSED, self._on_trade_closed)
        event_bus.subscribe(ORDER_REJECTED, self._on_order_rejected)
        event_bus.subscribe(TP_HIT, self._on_tp_hit)
        event_bus.subscribe(SL_HIT, self._on_sl_hit)
        event_bus.subscribe(SYNC_MISMATCH, self._on_sync_mismatch)
        event_bus.subscribe(API_ERROR, self._on_api_error)
        event_bus.subscribe(WEBSOCKET_DISCONNECTED, self._on_websocket_disconnected)
        event_bus.subscribe(WEBSOCKET_RECONNECTED, self._on_websocket_reconnected)
        event_bus.subscribe(DAILY_SUMMARY_READY, self._on_daily_summary)
        event_bus.subscribe(ORDER_STATE_CHANGED, self._on_order_state_changed)
        event_bus.subscribe(RISK_VIOLATION_DETECTED, self._on_risk_violation)
        event_bus.subscribe(RECOVERY_ACTION_TAKEN, self._on_recovery_action)
        event_bus.subscribe(RECONCILIATION_ACTION, self._on_reconciliation_action)
        event_bus.subscribe(SYNC_REPAIRED, self._on_sync_repaired)
    
    async def _on_trade_opened(self, event):
        """Handle trade opened event with detailed info."""
        payload = event['payload']
        
        message = f"""
🟢 LIVE TRADE OPENED

Symbol: {payload['symbol']}
Side: {payload['side'].upper()}
Mode: {payload['mode']}
Entry: ${payload['entry_price']:,.2f}
Quantity: {payload.get('quantity', 'N/A')}
Leverage: {payload.get('leverage', 'N/A')}x
Stop Loss: ${payload.get('stop_loss', 'N/A')}
Take Profit: ${payload.get('take_profit', 'N/A')}
Strategy: {payload.get('strategy_name', 'Unknown')}
Risk: {payload.get('risk_pct', 'N/A')}%
Slippage: {payload.get('slippage_pct', 'N/A')}%
Latency: {payload.get('execution_latency_ms', 'N/A')}ms
Order ID: {payload['order_id']}
        """.strip()
        
        await self.notifier.send_message(message)
        logger.info("📱 Telegram: Trade opened notification sent")
    
    async def _on_order_filled(self, event):
        """Handle order filled confirmation."""
        payload = event['payload']
        
        message = f"""
✅ ORDER FILLED

Symbol: {payload['symbol']}
Side: {payload.get('side', 'N/A').upper()}
Fill Price: ${payload['price']:,.2f}
Requested Price: ${payload.get('requested_price', payload['price']):,.2f}
Slippage: {payload.get('slippage_pct', 0):.4f}%
Quantity: {payload.get('quantity', 'N/A')}
Latency: {payload.get('latency_ms', 'N/A')}ms
Order ID: {payload['order_id']}
        """.strip()
        
        await self.notifier.send_message(message)
    
    async def _on_trade_closed(self, event):
        """Handle trade closed with PnL breakdown."""
        payload = event['payload']
        pnl = payload.get('pnl', 0)
        emoji = "✅" if pnl > 0 else "❌"
        
        message = f"""
{emoji} TRADE CLOSED

PnL: ${pnl:,.2f} ({payload.get('pnl_pct', 0):.2f}%)
Exit Price: ${payload.get('exit_price', 0):,.2f}
Duration: {payload.get('duration', 'N/A')}
Reason: {payload.get('close_reason', 'Manual')}
Total Return: {payload.get('total_return', 'N/A')}R
        """.strip()
        
        await self.notifier.send_message(message)
        logger.info("📱 Telegram: Trade closed notification sent")
    
    async def _on_order_rejected(self, event):
        """Handle order rejection alert."""
        payload = event['payload']
        
        message = f"""
🚨 ORDER REJECTED

Symbol: {payload.get('symbol', 'Unknown')}
Reason: {payload.get('error', 'Unknown error')}
Details: {payload.get('details', 'N/A')}
        """.strip()
        
        await self.notifier.send_message(message)
        logger.warning("📱 Telegram: Order rejection alert sent")
    
    async def _on_tp_hit(self, event):
        """Handle take profit hit."""
        payload = event['payload']
        
        message = f"""
🎯 TAKE PROFIT HIT

Symbol: {payload['symbol']}
TP Price: ${payload['tp_price']:,.2f}
PnL: ${payload.get('pnl', 0):,.2f}
        """.strip()
        
        await self.notifier.send_message(message)
    
    async def _on_sl_hit(self, event):
        """Handle stop loss hit."""
        payload = event['payload']
        
        message = f"""
⛔ STOP LOSS HIT

Symbol: {payload['symbol']}
SL Price: ${payload['sl_price']:,.2f}
Loss: ${payload.get('pnl', 0):,.2f}
        """.strip()
        
        await self.notifier.send_message(message)
    
    async def _on_sync_mismatch(self, event):
        """Handle sync mismatch alert."""
        message = f"""
⚠️ SYNC MISMATCH DETECTED

{event['payload']}

Action: Auto-repair initiated
        """.strip()
        
        await self.notifier.send_message(message)
        logger.warning("📱 Telegram: Sync mismatch alert sent")
    
    async def _on_api_error(self, event):
        """Handle API error alert."""
        message = f"""
🚨 API ERROR

Error: {event['payload']['error']}
Context: {event['payload'].get('context', 'unknown')}
Timestamp: {event['timestamp']}
        """.strip()
        
        await self.notifier.send_message(message)
        logger.error("📱 Telegram: API error alert sent")
    
    async def _on_websocket_disconnected(self, event):
        """Handle WebSocket disconnection with improved messaging and rate limiting."""
        import time
        
        current_time = time.time()
        
        # Check if we're in cooldown period
        if current_time - self._last_ws_disconnect_time < self._ws_disconnect_cooldown:
            logger.debug(f"Skipping WebSocket disconnect notification (cooldown active, {int(current_time - self._last_ws_disconnect_time)}s since last)")
            return
        
        # Update last notification time
        self._last_ws_disconnect_time = current_time
        
        payload = event['payload']
        message = payload.get('message', 'WebSocket disconnected')
        
        # Extract additional context if available
        reconnect_delay = payload.get('reconnect_delay', 'unknown')
        attempt_count = payload.get('attempt_count', 1)
        
        message_text = f"""
⚠️ WEBSOCKET DISCONNECTED

{message}
Reconnect attempt #{attempt_count}
Next retry in: {reconnect_delay}s

System will automatically attempt to reconnect.
        """.strip()
        
        await self.notifier.send_message(message_text)
        logger.warning(f"📱 Telegram: WebSocket disconnection alert sent (attempt #{attempt_count})")
    
    async def _on_websocket_reconnected(self, event):
        """Handle successful WebSocket reconnection."""
        import time
        
        # Reset the disconnect cooldown timer on successful reconnection
        self._last_ws_disconnect_time = 0
        
        payload = event['payload']
        message = payload.get('message', 'WebSocket reconnected successfully')
        
        message_text = f"""
✅ WEBSOCKET RECONNECTED

{message}

Trading system is back online and monitoring positions.
        """.strip()
        
        await self.notifier.send_message(message_text)
        logger.info("📱 Telegram: WebSocket reconnection confirmation sent")
    
    async def _on_daily_summary(self, event):
        """Handle daily summary ready event."""
        payload = event['payload']
        await self.send_daily_summary(payload)
    
    async def send_daily_summary(self, performance_data):
        """Send comprehensive daily summary."""
        total_trades = performance_data['total_trades']
        win_rate = performance_data['win_rate']
        total_pnl = performance_data['total_pnl']
        
        message = f"""
📊 DAILY SUMMARY

Date: {performance_data['date']}
Total Trades: {total_trades}
Winning Trades: {performance_data['winning_trades']}
Losing Trades: {performance_data['losing_trades']}
Win Rate: {win_rate:.1f}%
Total PnL: ${total_pnl:,.2f}
Avg PnL per Trade: ${performance_data['avg_pnl']:,.2f}
Best Trade: ${performance_data.get('best_trade', 0):,.2f}
Worst Trade: ${performance_data.get('worst_trade', 0):,.2f}
Total Fees: ${performance_data.get('total_fees', 0):,.2f}
Max Drawdown: {performance_data.get('max_drawdown', 0):.2f}%

Top Strategy: {performance_data.get('best_strategy', 'N/A')}
        """.strip()
        
        await self.notifier.send_message(message)
    
    async def _on_order_state_changed(self, event):
        """Handle critical order state changes."""
        payload = event['payload']
        from_state = payload.get('from_state', 'UNKNOWN')
        to_state = payload.get('to_state', 'UNKNOWN')
        
        # Only alert on critical transitions
        critical_states = ['REJECTED', 'CANCELED', 'EXPIRED', 'FAILED']
        if to_state not in critical_states:
            return
        
        message = f"""
🚨 CRITICAL ORDER STATE CHANGE

Symbol: {payload.get('symbol', 'Unknown')}
Order ID: {payload.get('order_id', 'N/A')}
Transition: {from_state} → {to_state}
Reason: {payload.get('reason', 'N/A')}
Exchange: {payload.get('exchange', 'Unknown')}
        """.strip()
        
        await self.notifier.send_message(message)
        logger.warning(f"📱 Telegram: Critical order state change alert sent")
    
    async def _on_risk_violation(self, event):
        """Handle risk threshold breaches."""
        payload = event['payload']
        violation_type = payload.get('violation_type', 'Unknown')
        risk_level = payload.get('risk_level', 'MEDIUM')
        
        emoji_map = {'LOW': '⚠️', 'MEDIUM': '🟡', 'HIGH': '🔴', 'CRITICAL': '🚨'}
        emoji = emoji_map.get(risk_level, '⚠️')
        
        message = f"""
{emoji} RISK VIOLATION DETECTED - {risk_level}

Type: {violation_type}
Symbol: {payload.get('symbol', 'N/A')}
Description: {payload.get('description', 'N/A')}

Metrics:
• Current Value: {payload.get('current_value', 'N/A')}
• Threshold: {payload.get('threshold', 'N/A')}
• Action Taken: {payload.get('action_taken', 'None')}
        """.strip()
        
        await self.notifier.send_message(message)
        logger.warning(f"📱 Telegram: Risk violation alert sent ({risk_level})")
    
    async def _on_recovery_action(self, event):
        """Handle automatic recovery actions."""
        payload = event['payload']
        
        message = f"""
🔧 AUTOMATIC RECOVERY ACTION

Action: {payload.get('action', 'Unknown')}
Context: {payload.get('context', 'N/A')}
Status: {payload.get('status', 'N/A')}

Details: {payload.get('details', 'N/A')}
        """.strip()
        
        await self.notifier.send_message(message)
        logger.info("📱 Telegram: Recovery action notification sent")
    
    async def _on_reconciliation_action(self, event):
        """Handle position reconciliation events."""
        payload = event['payload']
        requires_review = payload.get('requires_review', False)
        
        emoji = "⚠️" if requires_review else "✅"
        severity = "REQUIRES REVIEW" if requires_review else "AUTO-REPAIRED"
        
        message = f"""
{emoji} RECONCILIATION - {severity}

Symbol: {payload.get('symbol', 'N/A')}
Exchange: {payload.get('exchange', 'Unknown')}
Mismatch Type: {payload.get('mismatch_type', 'Unknown')}
Action: {payload.get('action', 'N/A')}
        """.strip()
        
        if payload.get('old_state'):
            message += f"\nPrevious State: {payload['old_state']}"
        if payload.get('new_state'):
            message += f"\nNew State: {payload['new_state']}"
        
        await self.notifier.send_message(message)
        logger.info(f"📱 Telegram: Reconciliation action notification sent ({severity})")
    
    async def _on_sync_repaired(self, event):
        """Handle successful sync repair."""
        payload = event['payload']
        
        message = f"""
✅ SYNC REPAIRED

Symbol: {payload.get('symbol', 'N/A')}
Issue: {payload.get('issue', 'Unknown')}
Resolution: {payload.get('resolution', 'Auto-repaired')}
        """.strip()
        
        await self.notifier.send_message(message)
        logger.info("📱 Telegram: Sync repair notification sent")
