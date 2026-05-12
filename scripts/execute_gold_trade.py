#!/usr/bin/env python3
"""
Execute Gold futures trade on Binance Testnet with full persistence and notification.
"""
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.infra.binance_client import BinanceClient
from app.storage.db import get_session
from app.storage.models import PaperTrades
from app.notifications.notifier import TelegramNotifier


async def execute_gold_trade():
    """Execute complete Gold futures trade cycle"""
    
    print("\n" + "="*70)
    print("  GOLD FUTURES TRADE EXECUTION")
    print("="*70)
    
    # Initialize components
    binance = BinanceClient(
        api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
        api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
        testnet=True,
        demo_mode='futures_demo'
    )
    
    notifier = TelegramNotifier()
    
    try:
        # Step 1: Fetch current market data
        print("\n1. Fetching Gold market data...")
        print("-" * 70)
        
        ticker = await binance.fetch_ticker(settings.GOLD_SYMBOL_BINANCE)
        current_price = ticker['last_price']
        
        print(f"   Symbol: {settings.GOLD_SYMBOL_BINANCE}")
        print(f"   Current Price: ${current_price:,.2f}")
        print(f"   24h Volume: ${ticker.get('volume_24h', 0):,.2f}")
        
        # Step 2: Define trade parameters (momentum strategy, BUY side)
        print("\n2. Trade Parameters...")
        print("-" * 70)
        
        side = 'BUY'
        leverage = 3
        entry_price = current_price
        
        # Risk management: 2% stop loss, 4% take profit
        stop_loss = entry_price * 0.98
        take_profit = entry_price * 1.04
        
        # Position sizing: $10 risk (1% of $1000 testnet balance)
        account_balance = 1000
        risk_amount = account_balance * 0.01  # 1% risk
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0.01
        
        # Round to valid precision for PAXG
        quantity = round(quantity, 2)
        position_value = quantity * entry_price
        
        print(f"   Side: {side}")
        print(f"   Entry Price: ${entry_price:,.2f}")
        print(f"   Stop Loss: ${stop_loss:,.2f} (-2%)")
        print(f"   Take Profit: ${take_profit:,.2f} (+4%)")
        print(f"   Leverage: {leverage}x")
        print(f"   Quantity: {quantity:.2f}")
        print(f"   Position Value: ${position_value:,.2f}")
        print(f"   Risk Amount: ${risk_amount:.2f}")
        
        # Step 3: Execute market order
        print("\n3. Executing Market Order...")
        print("-" * 70)
        
        order_result = await binance.create_market_order(
            symbol=settings.GOLD_SYMBOL_BINANCE,
            side=side.lower(),
            amount=quantity,
            leverage=leverage
        )
        
        order_id = order_result['order_id']
        filled_price = order_result.get('price') or entry_price
        filled_quantity = order_result.get('filled', quantity)
        status = order_result.get('status', 'NEW')
        
        print(f"   ✅ Order Executed!")
        print(f"   • Order ID: {order_id}")
        print(f"   • Status: {status}")
        print(f"   • Filled Price: ${filled_price:,.2f}")
        print(f"   • Filled Quantity: {filled_quantity:.2f}")
        
        # Calculate slippage
        slippage_pct = abs(filled_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
        slippage_emoji = "✅" if slippage_pct < 0.1 else "⚠️" if slippage_pct < 0.5 else "❌"
        print(f"   • Slippage: {slippage_emoji} {slippage_pct:.4f}%")
        
        # Step 4: Persist to database
        print("\n4. Persisting to Database...")
        print("-" * 70)
        
        # Create paper trade record
        trade_record = PaperTrades(
            ts_open=datetime.utcnow().isoformat(),
            user_id="default_user",
            exchange="binance",
            symbol=settings.GOLD_SYMBOL_BINANCE,
            side=side.upper(),
            leverage=float(leverage),
            qty=filled_quantity,
            entry_price=filled_price,
            exit_price=None,
            stop_loss=stop_loss,
            take_profit=take_profit,
            profit=None,
            profit_pct=None,
            status='open',
            notes=json.dumps({
                'strategy': 'momentum',
                'regime': 'Low-vol',
                'execution_type': 'paper',
                'order_id': order_id,
                'risk_amount': risk_amount,
                'position_value_usd': position_value,
                'slippage_pct': slippage_pct
            }),
            execution_mode='paper'
        )
        
        # Use session properly
        async for db_session in get_session():
            db_session.add(trade_record)
            await db_session.commit()
            
            trade_id = trade_record.id
            print(f"   ✅ Trade persisted to database")
            print(f"   • Trade ID: #{trade_id}")
            print(f"   • Status: open")
            break
        
        # Step 5: Send Telegram notification
        print("\n5. Sending Telegram Notification...")
        print("-" * 70)
        
        telegram_data = {
            'symbol': settings.GOLD_SYMBOL_BINANCE,
            'side': side.upper(),
            'entry_price': entry_price,
            'filled_price': filled_price,
            'qty': filled_quantity,
            'leverage': leverage,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'strategy_name': 'momentum',
            'confidence': 0.70,
            'order_id': order_id,
            'fee': 0,
            'fee_currency': 'USDT',
            'exchange': 'Binance Testnet',
            'regime': 'Low-vol',
            'risk_level': 'MEDIUM',
            'trade_id': trade_id,
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        notification_sent = await notifier.send_trade_entry(telegram_data)
        
        if notification_sent:
            print(f"   ✅ Telegram notification sent successfully")
        else:
            print(f"   ⚠️  Telegram notification failed (check bot token/chat ID)")
        
        # Summary
        print("\n" + "="*70)
        print("  🎉 TRADE EXECUTION COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"\n   Summary:")
        print(f"   • Exchange: Binance Testnet (Futures Demo)")
        print(f"   • Symbol: {settings.GOLD_SYMBOL_BINANCE}")
        print(f"   • Side: {side.upper()}")
        print(f"   • Strategy: momentum")
        print(f"   • Regime: Low-vol")
        print(f"   • Order ID: {order_id}")
        print(f"   • Trade ID: #{trade_id}")
        print(f"   • Entry: ${entry_price:,.2f}")
        print(f"   • Filled: ${filled_price:,.2f}")
        print(f"   • Stop Loss: ${stop_loss:,.2f}")
        print(f"   • Take Profit: ${take_profit:,.2f}")
        print(f"   • Leverage: {leverage}x")
        print(f"   • Quantity: {filled_quantity:.2f}")
        print(f"   • Position Value: ${position_value:,.2f}")
        print(f"   • Risk: ${risk_amount:.2f} (1%)")
        print(f"   • Slippage: {slippage_pct:.4f}%")
        print(f"   • Status: OPEN")
        print(f"   • Telegram: {'✅ Sent' if notification_sent else '⚠️  Failed'}")
        print()
        
        await binance.close()
        
        return {
            'success': True,
            'trade_id': trade_id,
            'order_id': order_id,
            'filled_price': filled_price,
            'quantity': filled_quantity,
            'notification_sent': notification_sent
        }
        
    except Exception as e:
        print(f"\n❌ Trade execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        await binance.close()
        
        return {
            'success': False,
            'error': str(e)
        }


async def main():
    result = await execute_gold_trade()
    
    if result['success']:
        print("\n✅ All operations completed successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ Execution failed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
