"""
Telegram notification service for trade alerts and system updates.
Sends structured trade reports to Telegram upon trade events.
"""
import httpx
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.config import settings


def _format_usd(value: Any, default: str = "N/A") -> str:
    """Format numeric values as USD while tolerating missing optional fields."""
    if value is None or value == "":
        return default
    return f"${float(value):,.2f}"


class TelegramNotifier:
    """
    Sends notifications to Telegram bot.
    
    Features:
    - Trade entry/exit alerts with P&L
    - System status updates
    - Error alerts
    - Formatted messages with emojis for readability
    - Deduplication for rejection reports
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
        
        # Deduplication tracking for rejection reports
        # Key: (symbol, reason_category, score_range), Value: timestamp of last sent message
        self._rejection_cooldowns: Dict[tuple, datetime] = {}
        self._rejection_cooldown_seconds = 600  # 10 minutes default cooldown
        
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
        
        # Enhanced fields for institutional-grade reporting
        session = trade_data.get('session', 'N/A')
        rr_ratio = trade_data.get('expected_reward_risk_ratio', 2.0)
        quality_score = trade_data.get('quality_score', 'N/A')
        ai_engine = trade_data.get('ai_engine', 'GPT-4o-mini')
        raw_confidence = trade_data.get('raw_confidence', confidence)
        position_value = qty * filled_price
        
        # Calculate R:R ratio display
        if stop_loss and take_profit:
            risk_distance = abs(entry_price - stop_loss)
            reward_distance = abs(take_profit - entry_price)
            actual_rr = reward_distance / risk_distance if risk_distance > 0 else 0
            rr_display = f"{actual_rr:.1f}:1"
        else:
            rr_display = f"{rr_ratio:.1f}:1"

        message = f"""
<b>{emoji} NEW TRADE EXECUTED ON {exchange.upper()}</b>

<b>Trade #{trade_data.get('trade_id', 'N/A')}</b>
<b>Symbol:</b> {symbol}
<b>Side:</b> {side}
<b>Strategy:</b> {strategy}
<b>Regime:</b> {regime}
<b>Session:</b> {session if session != 'N/A' else 'N/A'}

<b>Order Details:</b>
• Order ID: <code>{order_id}</code>
• Requested Price: ${entry_price:,.2f}
• Filled Price: ${filled_price:,.2f}
• Slippage: {slippage_emoji} {slippage:.4f}%
• Quantity: {qty}
• Position Value: ${position_value:,.2f}
• Leverage: {leverage}x
• Fee: ${fee:.4f} {fee_currency}

<b>Risk Management:</b>
• Stop Loss: {sl_text}
• Take Profit: {tp_text}
• R:R Ratio: {rr_display}
• Risk Level: {risk_level.upper()}

<b>AI Analysis:</b>
• Engine: {ai_engine}
• Raw Confidence: {raw_confidence:.0%}
• Calibrated Confidence: {confidence:.0%}
• Quality Score: {quality_score}/100

<b>Metadata:</b>
• Time: {trade_data.get('timestamp', 'Now')}
• Exchange: {exchange}
        """.strip()
        
        return await self.send_message(message)
    
    async def trade_opened(self, order_details: Dict[str, Any]) -> bool:
        """
        Send notification when a trade position is successfully opened.
        
        This is a semantic wrapper around send_trade_entry with standardized
        field extraction and formatting for position opening events.
        
        Args:
            order_details: Dictionary containing:
                - order_id: Exchange order ID
                - symbol: Trading pair (e.g., 'BTC/USDT')
                - side: 'buy' or 'sell' (or 'long'/'short')
                - price: Fill price
                - quantity: Position size
                - leverage: Leverage multiplier (futures)
                - timestamp: Execution time
                - exchange: Exchange name
                - status: Order status ('filled', 'partially_filled')
                
        Returns:
            True if notification sent successfully
        """
        # Normalize fields
        symbol = order_details.get('symbol', 'UNKNOWN')
        side = order_details.get('side', 'UNKNOWN').upper()
        price = order_details.get('price', order_details.get('fill_price', 0))
        quantity = order_details.get('quantity', order_details.get('amount', 0))
        order_id = order_details.get('order_id', 'N/A')
        exchange = order_details.get('exchange', 'Unknown')
        status = order_details.get('status', 'filled')
        timestamp = order_details.get('timestamp', datetime.utcnow().isoformat())
        
        # Determine emoji based on side
        emoji = "🟢" if side in ['BUY', 'LONG'] else "🔴"
        
        message = (
            f"\n"
            f"<b>{emoji} TRADE OPENED on {exchange.upper()}</b>\n"
            f"\n"
            f"<b>Order ID:</b> <code>{order_id}</code>\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Price:</b> ${price:,.2f}\n"
            f"<b>Quantity:</b> {quantity}\n"
            f"<b>Status:</b> {status.upper()}\n"
            f"\n"
            f"<b>Time:</b> {timestamp}\n"
        ).strip()
        
        return await self.send_message(message)
    
    async def trade_closed(self, order_details: Dict[str, Any], pnl: float) -> bool:
        """
        Send notification when a trade position is closed with P&L summary.
        
        This is a semantic wrapper around send_trade_exit focused on position
        closure events with explicit P&L reporting.
        
        Args:
            order_details: Dictionary containing:
                - order_id: Closing order ID
                - symbol: Trading pair
                - side: Original position side ('buy'/'sell' or 'long'/'short')
                - entry_price: Original entry price
                - exit_price: Closing fill price
                - quantity: Position size closed
                - duration: Position hold time (optional)
                - reason: Close reason ('take_profit', 'stop_loss', 'manual')
                - exchange: Exchange name
                
            pnl: Profit/Loss amount (positive = profit, negative = loss)
            
        Returns:
            True if notification sent successfully
        """
        symbol = order_details.get('symbol', 'UNKNOWN')
        side = order_details.get('side', 'UNKNOWN').upper()
        entry_price = order_details.get('entry_price', 0)
        exit_price = order_details.get('exit_price', order_details.get('price', 0))
        quantity = order_details.get('quantity', order_details.get('amount', 0))
        order_id = order_details.get('order_id', 'N/A')
        exchange = order_details.get('exchange', 'Unknown')
        reason = order_details.get('reason', 'closed')
        duration = order_details.get('duration', 'N/A')
        
        # Calculate P&L percentage if we have entry/exit prices
        if entry_price > 0:
            pnl_pct = (pnl / (entry_price * quantity)) * 100
        else:
            pnl_pct = 0
        
        # Determine emoji and result text
        if pnl > 0:
            emoji = "✅"
            result_text = "PROFIT"
        elif pnl < 0:
            emoji = "❌"
            result_text = "LOSS"
        else:
            emoji = "➖"
            result_text = "BREAKEVEN"
        
        message = (
            f"\n"
            f"<b>{emoji} TRADE CLOSED - {result_text}</b>\n"
            f"\n"
            f"<b>Order ID:</b> <code>{order_id}</code>\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Entry:</b> ${entry_price:,.2f}\n"
            f"<b>Exit:</b> ${exit_price:,.2f}\n"
            f"\n"
            f"<b>P&L Summary:</b>\n"
            f"• Amount: ${pnl:+.2f}\n"
            f"• Return: {pnl_pct:+.2f}%\n"
            f"• Reason: {reason.replace('_', ' ').title()}\n"
            f"\n"
            f"<b>Duration:</b> {duration}\n"
            f"<b>Exchange:</b> {exchange}\n"
        ).strip()
        
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
        
        message = (
            f"<b>{emoji} TRADE CLOSED - {result_text}</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Entry:</b> {_format_usd(entry_price)}\n"
            f"<b>Exit:</b> {_format_usd(exit_price)}\n\n"
            f"<b>P&L Summary:</b>\n"
            f"• Profit: ${profit:+.2f}\n"
            f"• Return: {profit_pct:+.2f}%\n"
            f"• Status: {status.upper()}\n"
            f"• Order ID: <code>{order_id}</code>\n\n"
            f"<b>Duration:</b> {duration if duration else 'N/A'}\n"
            f"<b>Notes:</b> {notes if notes else 'N/A'}\n"
            f"<b>Trade ID:</b> #{trade_data.get('trade_id', 'N/A')}"
        )
        
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
        
        message = (
            f"<b>{emoji} DAILY TRADING SUMMARY</b>\n\n"
            f"<b>Performance:</b> {sentiment}\n"
            f"<b>Total P&L:</b> {_format_usd(total_profit)}\n\n"
            f"<b>Trade Statistics:</b>\n"
            f"• Total Trades: {total_trades}\n"
            f"• Winning: {winning_trades}\n"
            f"• Losing: {losing_trades}\n"
            f"• Win Rate: {win_rate:.1f}%\n"
            f"• Avg Profit/Trade: {_format_usd(avg_profit)}\n\n"
            f"<b>Risk Metrics:</b>\n"
            f"• Max Drawdown: {max_drawdown:.2f}%\n\n"
            f"<b>Date:</b> {summary_data.get('date', 'Today')}"
        )
        
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
        
        message = (
            f"<b>🥇 GOLD DUAL TRADE EXECUTED</b>\n\n"
            f"<b>Strategy:</b> {strategy}\n"
            f"<b>Regime:</b> {regime}\n"
            f"<b>Confidence:</b> {confidence*100:.1f}%\n\n"
            f"<b>Binance Testnet (Paper):</b> {binance_emoji} {binance_status.upper()}\n"
            f"• Symbol: PAXG/USDT\n"
            f"• Price: {_format_usd(binance_price)}\n\n"
            f"<b>MEXC Live (Real):</b> {mexc_emoji} {mexc_status.upper()}\n"
            f"• Symbol: XAUT/USDT\n"
            f"• Price: {_format_usd(mexc_price)}\n\n"
            f"<b>Comparison:</b>\n"
            f"• Position Value: {_format_usd(position_value)}\n"
            f"• Price Difference: {_format_usd(price_diff)}\n\n"
            f"<i>Paper vs Live execution comparison for Gold futures</i>"
        )
        
        return await self.send_message(message)
    
    async def send_trade_validation_report(
        self,
        validation_result: Any,
        proposal: Dict[str, Any]
    ) -> bool:
        """
        Send detailed validation report for trade attempt.
        
        Args:
            validation_result: ValidationResult object with validation data
            proposal: Original trade proposal dictionary
            
        Returns:
            True if sent successfully
        """
        symbol = validation_result.proposed_trade.get('symbol', 'UNKNOWN')
        side = validation_result.proposed_trade.get('side', 'UNKNOWN').upper()
        entry_price = validation_result.proposed_trade.get('entry_price', 0)
        quantity = validation_result.proposed_trade.get('quantity', 0)
        leverage = validation_result.proposed_trade.get('leverage', 1)
        confidence = validation_result.proposed_trade.get('confidence', 0)
        
        # Determine approval status and emoji
        if validation_result.approved:
            emoji = "✅"
            status_text = "APPROVED"
        else:
            emoji = "❌"
            status_text = "REJECTED"
        
        # Build message based on approval status
        if validation_result.approved:
            # APPROVED trade message
            message = (
                f"<b>{emoji} TRADE VALIDATION: {status_text}</b>\n\n"
                f"<b>Trade Details:</b>\n"
                f"• Symbol: {symbol}\n"
                f"• Side: {side}\n"
                f"• Entry Price: {_format_usd(entry_price)}\n"
                f"• Quantity: {quantity}\n"
                f"• Leverage: {leverage}x\n"
                f"• Position Value: {_format_usd(validation_result.position_value)}\n\n"
                f"<b>Validation Results:</b>\n"
                f"• Confidence: {confidence:.0%} (threshold: {validation_result.confidence_threshold:.0%}) ✅\n"
                f"• Risk Amount: {_format_usd(validation_result.risk_amount)} (limit: {validation_result.risk_threshold:.0%}) ✅\n"
                f"• Open Positions: {validation_result.open_positions_count} ✅\n"
                f"• Daily Drawdown: {validation_result.daily_drawdown_pct:.2f}% ✅\n"
            )
            # Add warnings if any
            if validation_result.warnings:
                message += f"\n<b>Warnings:</b>\n"
                for warning in validation_result.warnings:
                    message += f"️  {warning}\n"
            
            # Add metadata
            message += f"\n<b>Profile:</b> {settings.TRADING_PROFILE}\n"
            message += f"<b>Execution Mode:</b> {settings.EXECUTION_MODE}"
        
        else:
            # REJECTED trade message
            message = (
                f"<b>{emoji} TRADE VALIDATION: {status_text}</b>\n\n"
                f"<b>Trade Proposal:</b>\n"
                f"• Symbol: {symbol}\n"
                f"• Side: {side}\n"
                f"• Entry Price: {_format_usd(entry_price)}\n"
                f"• Quantity: {quantity}\n"
                f"• Leverage: {leverage}x\n"
                f"• Confidence: {confidence:.0%}\n\n"
                f"<b> VIOLATIONS ({len(validation_result.violations)}):</b>\n"
            )
            # List all violations
            for i, violation in enumerate(validation_result.violations, 1):
                message += f"{i}. {violation}\n"
            
            # Add comparison details
            message += f"\n<b>Required vs Proposed:</b>\n"
            message += f"• Confidence: {confidence:.0%} ≥ {validation_result.confidence_threshold:.0%} required\n"
            message += f"• Risk: ${validation_result.risk_amount:.2f} ≤ {validation_result.risk_threshold:.0%} of position required\n"
            message += f"• Open Positions: {validation_result.open_positions_count} (max: {validation_result.open_positions_count})\n"
            
            # Add warnings if any
            if validation_result.warnings:
                message += f"\n<b>Additional Warnings:</b>\n"
                for warning in validation_result.warnings:
                    message += f"⚠️  {warning}\n"
            
            # Add metadata
            message += f"\n<b>Profile:</b> {settings.TRADING_PROFILE}\n"
            message += f"<b>Execution Mode:</b> {settings.EXECUTION_MODE}"
        
        message = message.strip()
        return await self.send_message(message)
    
    async def send_order_state_alert(
        self,
        order_id: str,
        symbol: str,
        from_state: str,
        to_state: str,
        trade_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send alert for critical order state changes.
        
        Args:
            order_id: Exchange order ID
            symbol: Trading pair symbol
            from_state: Previous order state
            to_state: New order state
            trade_id: Associated trade ID (optional)
            details: Additional context (optional)
            
        Returns:
            True if sent successfully
        """
        # Determine severity based on state transition
        critical_states = ['REJECTED', 'CANCELED', 'EXPIRED', 'RECOVERY_REQUIRED']
        is_critical = to_state in critical_states
        
        emoji = "🚨" if is_critical else "ℹ️"
        severity = "CRITICAL" if is_critical else "INFO"
        
        message = f"""
<b>{emoji} ORDER STATE CHANGE - {severity}</b>

<b>Order ID:</b> <code>{order_id}</code>
<b>Symbol:</b> {symbol}
<b>Trade ID:</b> #{trade_id if trade_id else 'N/A'}

<b>State Transition:</b>
• From: {from_state.upper()}
• To: {to_state.upper()}
"""
        
        if details:
            message += f"\n<b>Details:</b>\n"
            for key, value in details.items():
                message += f"• {key}: {value}\n"
        
        message += f"\n<b>Timestamp:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        return await self.send_message(message)
    
    async def send_reconciliation_alert(
        self,
        action: str,
        symbol: str,
        exchange: str,
        mismatch_type: str,
        old_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        requires_review: bool = False
    ) -> bool:
        """
        Send alert for position mismatches detected during reconciliation.
        
        Args:
            action: Reconciliation action taken
            symbol: Trading pair symbol
            exchange: Exchange name
            mismatch_type: Type of mismatch (e.g., 'GHOST_POSITION', 'ORPHANED_ORDER')
            old_state: State before reconciliation (optional)
            new_state: State after reconciliation (optional)
            requires_review: Whether manual review is needed
            
        Returns:
            True if sent successfully
        """
        # Determine severity
        if requires_review:
            emoji = "⚠️"
            severity = "REQUIRES REVIEW"
        elif 'closed' in action.lower() or 'repair' in action.lower():
            emoji = "🔧"
            severity = "AUTO-REPAIRED"
        else:
            emoji = "ℹ️"
            severity = "INFO"
        
        message = f"""
<b>{emoji} RECONCILIATION ALERT - {severity}</b>

<b>Action:</b> {action}
<b>Symbol:</b> {symbol}
<b>Exchange:</b> {exchange.upper()}
<b>Mismatch Type:</b> {mismatch_type}
"""
        
        if old_state:
            message += f"\n<b>Previous State:</b>\n"
            for key, value in old_state.items():
                message += f"• {key}: {value}\n"
        
        if new_state:
            message += f"\n<b>New State:</b>\n"
            for key, value in new_state.items():
                message += f"• {key}: {value}\n"
        
        if requires_review:
            message += f"\n<b>⚠️ Manual review required!</b>"
        
        message += f"\n<b>Timestamp:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        return await self.send_message(message)
    
    async def send_risk_violation_alert(
        self,
        violation_type: str,
        symbol: str,
        risk_level: str,
        description: str,
        metrics: Optional[Dict[str, Any]] = None,
        action_taken: Optional[str] = None,
        trade_id: Optional[str] = None
    ) -> bool:
        """
        Send alert for risk limit breaches.
        
        Args:
            violation_type: Type of risk violation
            symbol: Trading pair symbol
            risk_level: Risk level ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
            description: Description of the violation
            metrics: Risk metrics at time of violation (optional)
            action_taken: Action taken in response (optional)
            trade_id: Associated trade ID (optional)
            
        Returns:
            True if sent successfully
        """
        # Determine emoji based on risk level
        emojis = {
            'LOW': '⚠️',
            'MEDIUM': '🟡',
            'HIGH': '🔴',
            'CRITICAL': '🚨'
        }
        emoji = emojis.get(risk_level.upper(), '⚠️')
        
        message = f"""
<b>{emoji} RISK VIOLATION DETECTED - {risk_level.upper()}</b>

<b>Type:</b> {violation_type}
<b>Symbol:</b> {symbol}
<b>Trade ID:</b> #{trade_id if trade_id else 'N/A'}

<b>Description:</b>
{description}
"""
        
        if metrics:
            message += f"\n<b>Risk Metrics:</b>\n"
            for key, value in metrics.items():
                if isinstance(value, float):
                    message += f"• {key}: {value:.2f}\n"
                else:
                    message += f"• {key}: {value}\n"
        
        if action_taken:
            message += f"\n<b>Action Taken:</b> {action_taken}"
        
        message += f"\n<b>Timestamp:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        return await self.send_message(message)
    
    async def send_trade_rejection_report(
        self,
        symbol: str,
        reason: str,
        quality_score: int,
        cycle_time_ms: float
    ) -> bool:
        """
        Send trade rejection report when AI quality filter blocks a trade.
        
        Implements deduplication to prevent spamming identical notifications.
        Reports with same symbol, similar score range, and same reason category
        are suppressed within the cooldown period (default 10 minutes).
        
        Args:
            symbol: Trading pair symbol
            reason: Rejection reason from quality filter
            quality_score: Quality score (0-100)
            cycle_time_ms: Cycle execution time in milliseconds
            
        Returns:
            True if sent successfully, False if suppressed by deduplication
        """
        # Check deduplication before sending
        if not self._should_send_rejection(symbol, reason, quality_score):
            return False
        
        # Determine emoji based on score
        if quality_score >= 80:
            emoji = "⚠️"
            severity = "MARGINAL"
        elif quality_score >= 60:
            emoji = "🟡"
            severity = "LOW QUALITY"
        else:
            emoji = "🔴"
            severity = "POOR QUALITY"
        
        message = f"""
<b>{emoji} Trade Proposal REJECTED by Quality Filter</b>

<b>Symbol:</b> {symbol}
<b>Severity:</b> {severity}
<b>Quality Score:</b> {quality_score}/100

<b>Rejection Reason:</b>
{reason}

<b>Cycle Time:</b> {cycle_time_ms:.0f}ms
<b>Timestamp:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

<i>This trade did not meet minimum quality standards and was blocked before validation.</i>
        """.strip()
        
        result = await self.send_message(message)
        
        # Record this rejection for deduplication tracking
        if result:
            self._record_rejection(symbol, reason, quality_score)
        
        return result
    
    def _get_reason_category(self, reason: str) -> str:
        """
        Extract a normalized category from the rejection reason.
        This allows grouping similar reasons while distinguishing different issues.
        
        Args:
            reason: Full rejection reason text
            
        Returns:
            Normalized reason category
        """
        reason_lower = reason.lower()
        
        # Categorize common rejection reasons
        if 'quality score below threshold' in reason_lower or 'quality score' in reason_lower:
            return 'quality_threshold'
        elif 'confidence' in reason_lower:
            return 'confidence_low'
        elif 'risk' in reason_lower:
            return 'risk_exceeded'
        elif 'volatility' in reason_lower:
            return 'volatility_high'
        elif 'liquidity' in reason_lower:
            return 'liquidity_insufficient'
        elif 'spread' in reason_lower:
            return 'spread_too_wide'
        else:
            # Return first few words as category for unknown reasons
            words = reason_lower.split()[:3]
            return '_'.join(words) if words else 'unknown'
    
    def _get_score_range(self, quality_score: int) -> str:
        """
        Group quality scores into ranges to avoid near-duplicate notifications.
        
        Args:
            quality_score: Quality score (0-100)
            
        Returns:
            Score range string (e.g., '70-79', '80-89')
        """
        # Group by tens to allow some variation but catch exact duplicates
        range_start = (quality_score // 10) * 10
        range_end = range_start + 9
        return f"{range_start}-{range_end}"
    
    def _should_send_rejection(self, symbol: str, reason: str, quality_score: int) -> bool:
        """
        Check if a rejection report should be sent based on deduplication rules.
        
        Args:
            symbol: Trading pair symbol
            reason: Rejection reason
            quality_score: Quality score
            
        Returns:
            True if should send, False if suppressed by cooldown
        """
        now = datetime.utcnow()
        reason_category = self._get_reason_category(reason)
        score_range = self._get_score_range(quality_score)
        
        # Create deduplication key
        dedup_key = (symbol, reason_category, score_range)
        
        # Check if we have a recent rejection with same characteristics
        if dedup_key in self._rejection_cooldowns:
            last_sent = self._rejection_cooldowns[dedup_key]
            elapsed = (now - last_sent).total_seconds()
            
            if elapsed < self._rejection_cooldown_seconds:
                remaining = self._rejection_cooldown_seconds - elapsed
                print(f"⚠️  Rejection report suppressed (cooldown): {symbol} - {reason_category} "
                      f"(score: {score_range}, {remaining:.0f}s remaining)")
                return False
        
        return True
    
    def _record_rejection(self, symbol: str, reason: str, quality_score: int):
        """
        Record a rejection report for deduplication tracking.
        
        Args:
            symbol: Trading pair symbol
            reason: Rejection reason
            quality_score: Quality score
        """
        now = datetime.utcnow()
        reason_category = self._get_reason_category(reason)
        score_range = self._get_score_range(quality_score)
        
        dedup_key = (symbol, reason_category, score_range)
        self._rejection_cooldowns[dedup_key] = now
        
        # Clean up old entries to prevent memory leaks
        self._cleanup_old_cooldowns(now)
    
    def _cleanup_old_cooldowns(self, now: datetime):
        """
        Remove expired cooldown entries to prevent memory leaks.
        
        Args:
            now: Current timestamp
        """
        expired_keys = [
            key for key, timestamp in self._rejection_cooldowns.items()
            if (now - timestamp).total_seconds() > self._rejection_cooldown_seconds * 2
        ]
        for key in expired_keys:
            del self._rejection_cooldowns[key]

    async def send_risk_alert(self, alert_type: str, details: Dict[str, Any]) -> bool:
        """
        Send risk management alert.
        
        Args:
            alert_type: Type of risk alert (daily_loss, drawdown, cooldown, etc.)
            details: Alert details dictionary
            
        Returns:
            True if sent successfully
        """
        icons = {
            'daily_loss': '📉',
            'drawdown': '📊',
            'cooldown': '⏸️ ',
            'volatility': '🌪️ ',
            'position_limit': '⚖️ ',
            'leverage_limit': '🔒'
        }
        
        icon = icons.get(alert_type, '⚠️ ')
        title = alert_type.replace('_', ' ').title()
        
        message = f"{icon} <b>Risk Alert: {title}</b>\n\n"
        for key, value in details.items():
            formatted_key = key.replace('_', ' ').title()
            message += f"• {formatted_key}: {value}\n"
        
        message += f"\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        
        return await self.send_message(message)

    async def send_circuit_breaker_alert(self, state: str, reason: str, 
                                         metrics: Dict[str, Any]) -> bool:
        """
        Send circuit breaker activation/recovery alert.
        
        Args:
            state: Circuit state (OPEN, CLOSED, HALF_OPEN)
            reason: Reason for state change
            metrics: System health metrics snapshot
            
        Returns:
            True if sent successfully
        """
        state_icons = {
            'OPEN': '🚨',
            'HALF_OPEN': '🔧',
            'CLOSED': '✅'
        }
        
        icon = state_icons.get(state, '⚠️ ')
        severity = "CRITICAL" if state == 'OPEN' else "WARNING" if state == 'HALF_OPEN' else "INFO"
        
        message = f"{icon} <b>Circuit Breaker {severity}</b>\n\n"
        message += f"<b>State:</b> {state}\n"
        message += f"<b>Reason:</b> {reason}\n\n"
        
        if metrics:
            message += "<b>System Metrics:</b>\n"
            if 'api_failures' in metrics:
                message += f"• API Failures: {metrics['api_failures']}\n"
            if 'avg_slippage' in metrics:
                message += f"• Avg Slippage: {metrics['avg_slippage']:.3%}\n"
            if 'avg_latency' in metrics:
                message += f"• Avg Latency: {metrics['avg_latency']:.0f}ms\n"
            if 'position_sync' in metrics:
                message += f"• Position Sync: {'✅ OK' if metrics['position_sync'] else '❌ MISMATCH'}\n"
        
        message += f"\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        
        return await self.send_message(message)

    async def send_emergency_position_closure(self, closed_positions: List[Dict], 
                                              reason: str) -> bool:
        """
        Send alert for emergency position closures.
        
        Args:
            closed_positions: List of closed position details
            reason: Reason for emergency closure
            
        Returns:
            True if sent successfully
        """
        message = f"🚨 <b>EMERGENCY: Positions Closed</b>\n\n"
        message += f"<b>Reason:</b> {reason}\n\n"
        message += f"<b>Closed Positions ({len(closed_positions)}):</b>\n"
        
        total_pnl = 0
        for pos in closed_positions:
            pnl = pos.get('pnl', 0)
            total_pnl += pnl
            message += f"• {pos['symbol']} {pos['side']}: ${abs(pnl):.2f} {'profit' if pnl > 0 else 'loss'}\n"
        
        message += f"\n<b>Total P&L:</b> ${total_pnl:.2f}\n"
        message += f"\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        
        return await self.send_message(message)
