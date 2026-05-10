"""
Telegram notification service for trade alerts and system updates.
Sends structured trade reports to Telegram upon trade events.
"""
import httpx
from typing import Optional, Dict, Any
from app.config import settings


class TelegramNotifier:
    """
    Sends notifications to Telegram bot.
    
    Features:
    - Trade entry/exit alerts with P&L
    - System status updates
    - Error alerts
    - Formatted messages with emojis for readability
    """
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token (from BotFather)
            chat_id: Target chat ID for notifications
        """
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            print("⚠️  Telegram notifications disabled (missing BOT_TOKEN or CHAT_ID)")
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to Telegram chat.
        
        Args:
            text: Message text (supports HTML formatting)
            parse_mode: Message format ("HTML" or "Markdown")
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True
                    },
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    return True
                else:
                    print(f"⚠️  Telegram API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            print(f"⚠️  Telegram notification failed: {e}")
            return False
    
    async def send_trade_entry(self, trade_data: Dict[str, Any]) -> bool:
        """
        Send trade entry notification with real order details.
        
        Args:
            trade_data: Dictionary with trade details including order info
            
        Returns:
            True if sent successfully
        """
        symbol = trade_data.get('symbol', 'UNKNOWN')
        side = trade_data.get('side', 'UNKNOWN').upper()
        entry_price = trade_data.get('entry_price', 0)
        filled_price = trade_data.get('filled_price', entry_price)
        qty = trade_data.get('qty', 0) or trade_data.get('quantity', 0)
        leverage = trade_data.get('leverage', 1)
        stop_loss = trade_data.get('stop_loss', None)
        take_profit = trade_data.get('take_profit', None)
        strategy = trade_data.get('strategy_name') or trade_data.get('strategy', 'Unknown')
        confidence = trade_data.get('confidence', 0)
        order_id = trade_data.get('order_id', 'N/A')
        fee = trade_data.get('fee', 0)
        fee_currency = trade_data.get('fee_currency', 'USDT')
        exchange = trade_data.get('exchange', 'Binance')
        regime = trade_data.get('regime', 'Unknown')
        risk_level = trade_data.get('risk_level', 'medium')
        
        # Format stop loss and take profit
        sl_text = f"${stop_loss:.2f}" if stop_loss else "N/A"
        tp_text = f"${take_profit:.2f}" if take_profit else "N/A"
        
        # Emoji based on side
        emoji = "🟢" if side == "LONG" else "🔴"
        
        # Calculate slippage
        slippage = abs(filled_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
        slippage_emoji = "✅" if slippage < 0.1 else "⚠️" if slippage < 0.5 else "❌"

        message = f"""
<b>{emoji} NEW TRADE EXECUTED ON {exchange.upper()}</b>

<b>Symbol:</b> {symbol}
<b>Side:</b> {side}
<b>Strategy:</b> {strategy}
<b>Regime:</b> {regime}

<b>Order Details:</b>
• Order ID: <code>{order_id}</code>
• Requested Price: ${entry_price:,.2f}
• Filled Price: ${filled_price:,.2f}
• Slippage: {slippage_emoji} {slippage:.4f}%
• Quantity: {qty}
• Leverage: {leverage}x
• Fee: ${fee:.4f} {fee_currency}

<b>Risk Management:</b>
• Stop Loss: {sl_text}
• Take Profit: {tp_text}
• Risk Level: {risk_level.upper()}

<b>AI Confidence:</b> {confidence:.0%}
<b>Trade ID:</b> #{trade_data.get('trade_id', 'N/A')}
<b>Time:</b> {trade_data.get('timestamp', 'Now')}
        """.strip()
        
        return await self.send_message(message)
    
    async def send_trade_exit(self, trade_data: Dict[str, Any]) -> bool:
        """
        Send trade exit notification with P&L summary.
        
        Args:
            trade_data: Dictionary with trade details including exit info
            
        Returns:
            True if sent successfully
        """
        symbol = trade_data.get('symbol', 'UNKNOWN')
        side = trade_data.get('side', 'UNKNOWN').upper()
        entry_price = trade_data.get('entry_price', 0)
        exit_price = trade_data.get('exit_price', 0)
        profit = trade_data.get('profit', 0)
        profit_pct = trade_data.get('profit_pct', 0)
        status = trade_data.get('status', 'closed')
        notes = trade_data.get('notes', '')
        order_id = trade_data.get('order_id', 'N/A')
        duration = trade_data.get('duration', '')
        
        # Determine emoji based on profit/loss
        if profit > 0:
            emoji = "✅"
            result_text = "PROFIT"
        elif profit < 0:
            emoji = "❌"
            result_text = "LOSS"
        else:
            emoji = "➖"
            result_text = "BREAKEVEN"
        
        message = f"""
<b>{emoji} TRADE CLOSED - {result_text}</b>

<b>Symbol:</b> {symbol}
<b>Side:</b> {side}
<b>Entry:</b> ${entry_price:,.2f}
<b>Exit:</b> ${exit_price:,.2f}

<b>P&L Summary:</b>
• Profit: ${profit:+.2f}
• Return: {profit_pct:+.2f}%
• Status: {status.upper()}
• Order ID: <code>{order_id}</code>

<b>Duration:</b> {duration if duration else 'N/A'}
<b>Notes:</b> {notes if notes else 'N/A'}
<b>Trade ID:</b> #{trade_data.get('trade_id', 'N/A')}
        """.strip()
        
        return await self.send_message(message)
    
    async def send_system_alert(self, title: str, message: str, level: str = "info") -> bool:
        """
        Send system alert notification.
        
        Args:
            title: Alert title
            message: Alert message
            level: Alert level ("info", "warning", "error")
            
        Returns:
            True if sent successfully
        """
        # Emoji based on level
        emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨"
        }
        emoji = emojis.get(level, "ℹ️")
        
        text = f"<b>{emoji} {title}</b>\n\n{message}"
        return await self.send_message(text)
    
    async def send_daily_summary(self, summary_data: Dict[str, Any]) -> bool:
        """
        Send daily trading summary.
        
        Args:
            summary_data: Dictionary with daily statistics
            
        Returns:
            True if sent successfully
        """
        total_trades = summary_data.get('total_trades', 0)
        winning_trades = summary_data.get('winning_trades', 0)
        losing_trades = summary_data.get('losing_trades', 0)
        win_rate = summary_data.get('win_rate', 0)
        total_profit = summary_data.get('total_profit', 0)
        avg_profit = summary_data.get('avg_profit_per_trade', 0)
        max_drawdown = summary_data.get('max_drawdown_pct', 0)
        
        # Determine overall sentiment
        if total_profit > 0:
            emoji = "📈"
            sentiment = "PROFITABLE"
        elif total_profit < 0:
            emoji = "📉"
            sentiment = "LOSS"
        else:
            emoji = "➖"
            sentiment = "NEUTRAL"
        
        message = f"""
<b>{emoji} DAILY TRADING SUMMARY</b>

<b>Performance:</b> {sentiment}
<b>Total P&L:</b> ${total_profit:.2f}

<b>Trade Statistics:</b>
• Total Trades: {total_trades}
• Winning: {winning_trades}
• Losing: {losing_trades}
• Win Rate: {win_rate:.1f}%
• Avg Profit/Trade: ${avg_profit:.2f}

<b>Risk Metrics:</b>
• Max Drawdown: {max_drawdown:.2f}%

<b>Date:</b> {summary_data.get('date', 'Today')}
        """.strip()
        
        return await self.send_message(message)
    
    async def send_gold_dual_trade_alert(
        self,
        trade_data: Dict[str, Any]
    ) -> bool:
        """
        Send specialized alert for Gold dual trades (Binance paper + MEXC live).
        
        Args:
            trade_data: Dictionary with dual execution results
            
        Returns:
            True if sent successfully
        """
        binance_result = trade_data.get('binance', {})
        mexc_result = trade_data.get('mexc', {})
        comparison = trade_data.get('comparison', {})
        
        # Extract Binance info
        binance_status = binance_result.get('status', 'N/A') if binance_result else 'N/A'
        binance_price = None
        if binance_result and binance_result.get('order'):
            binance_price = binance_result['order'].get('price')
        
        # Extract MEXC info
        mexc_status = mexc_result.get('status', 'N/A') if mexc_result else 'N/A'
        mexc_price = None
        if mexc_result and mexc_result.get('order'):
            mexc_price = mexc_result['order'].get('price')
        
        # Calculate price difference
        price_diff = comparison.get('price_difference')
        position_value = comparison.get('position_value_usd', 0)
        strategy = comparison.get('strategy', 'Unknown')
        regime = comparison.get('regime', 'Unknown')
        confidence = comparison.get('confidence', 0)
        
        # Status emojis
        binance_emoji = "✅" if binance_status == 'success' else "❌"
        mexc_emoji = "✅" if mexc_status == 'success' else "❌"
        
        message = f"""
<b>🥇 GOLD DUAL TRADE EXECUTED</b>

<b>Strategy:</b> {strategy}
<b>Regime:</b> {regime}
<b>Confidence:</b> {confidence*100:.1f}%

<b>Binance Testnet (Paper):</b> {binance_emoji} {binance_status.upper()}
• Symbol: PAXG/USDT
• Price: ${binance_price:,.2f if binance_price else 'N/A'}

<b>MEXC Live (Real):</b> {mexc_emoji} {mexc_status.upper()}
• Symbol: XAUT/USDT
• Price: ${mexc_price:,.2f if mexc_price else 'N/A'}

<b>Comparison:</b>
• Position Value: ${position_value:,.2f}
• Price Difference: ${price_diff:,.2f if price_diff else 'N/A'}

<i>Paper vs Live execution comparison for Gold futures</i>
        """.strip()
        
        return await self.send_message(message)
