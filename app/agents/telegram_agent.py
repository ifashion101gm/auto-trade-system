"""
Telegram Agent - Event-driven notification system.
Only reads from database events, never directly from strategy.

Subscribes to all trading events and sends formatted Telegram notifications.
"""
from app.infra.telegram_notifier import TelegramNotifier
from app.events.event_bus import event_bus
from app.events.event_types import (
    ORDER_OPENED, ORDER_CLOSED, ORDER_FILLED, ORDER_REJECTED,
    TP_HIT, SL_HIT, POSITION_UPDATED,
    SYNC_MISMATCH, API_ERROR, WEBSOCKET_DISCONNECTED,
    DAILY_SUMMARY_READY
)
import logging

logger = logging.getLogger(__name__)


class TelegramAgent:
    """Event-driven Telegram notification system."""
    
    def __init__(self):
        self.notifier = TelegramNotifier()
        self._setup_subscriptions()
    
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
        event_bus.subscribe(DAILY_SUMMARY_READY, self._on_daily_summary)
    
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
Quantity: {payload.get('quantity', 'N/A')}
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
        """Handle WebSocket disconnection."""
        message = f"""
⚠️ WEBSOCKET DISCONNECTED

{event['payload']['message']}

Attempting automatic reconnection...
        """.strip()
        
        await self.notifier.send_message(message)
    
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
