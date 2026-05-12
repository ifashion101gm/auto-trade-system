#!/usr/bin/env python3
"""
Simple MEXC Demo Futures Test Trade.
Uses MEXCDemoExchange for paper trading simulation.
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.exchange.mexc_demo import MEXCDemoExchange
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
from app.logging_config import get_logger

logger = get_logger(__name__)


async def execute_demo_trade():
    """Execute a simple demo trade on MEXC."""
    
    logger.info("="*80)
    logger.info("MEXC DEMO FUTURES - SIMPLE TEST TRADE")
    logger.info("="*80)
    
    # Initialize demo exchange (uses real API but simulates trades)
    exchange = MEXCDemoExchange(testnet=False)  # Demo mode, not testnet
    
    try:
        symbol = settings.GOLD_SYMBOL_MEXC
        logger.info(f"\nSymbol: {symbol}")
        
        # Step 1: Check balance
        logger.info("\n1. Checking Balance...")
        balance = await exchange.get_balance()
        logger.info(f"   Total USDT: ${balance['total_usdt']:,.2f}")
        logger.info(f"   Available USDT: ${balance['free_usdt']:,.2f}")
        
        # Step 2: Get ticker
        logger.info("\n2. Fetching Market Data...")
        ticker = await exchange.get_ticker(symbol)
        current_price = ticker['last_price']
        logger.info(f"   Current Price: ${current_price:,.2f}")
        
        # Step 3: Open position
        logger.info("\n3. Opening Position...")
        quantity = 0.01  # Small test quantity
        leverage = 3
        
        order_result = await exchange.open_position(
            symbol=symbol,
            side='buy',
            amount=quantity,
            leverage=leverage,
            stop_loss=current_price * 0.98,
            take_profit=current_price * 1.04
        )
        
        logger.info(f"   ✅ Order Executed!")
        logger.info(f"   • Order ID: {order_result['order_id']}")
        logger.info(f"   • Filled Price: ${order_result['filled_price']:,.2f}")
        logger.info(f"   • Amount: {order_result['filled_amount']}")
        logger.info(f"   • Fee: ${order_result['fee']['cost']:.2f}")
        
        # Step 4: Record in database
        logger.info("\n4. Recording Trade in Database...")
        trade_record = PaperTrades(
            ts_open=datetime.utcnow().isoformat(),
            user_id="demo_user",
            exchange='mexc',
            symbol=symbol,
            side='LONG',
            leverage=leverage,
            qty=quantity,
            entry_price=order_result['filled_price'],
            exit_price=None,
            stop_loss=current_price * 0.98,
            take_profit=current_price * 1.04,
            profit=None,
            profit_pct=None,
            status='open',
            notes=json.dumps({
                'order_id': order_result['order_id'],
                'test_mode': 'demo',
                'validation_step': 'simple_test_trade'
            }),
            execution_mode='demo_test'
        )
        
        async with async_session_maker() as db_session:
            db_session.add(trade_record)
            await db_session.commit()
            trade_id = trade_record.id
        
        logger.info(f"   ✅ Trade recorded (ID: {trade_id})")
        
        # Step 5: Check positions
        logger.info("\n5. Checking Open Positions...")
        positions = await exchange.get_positions()
        logger.info(f"   Found {len(positions)} open position(s)")
        for pos in positions:
            if symbol in pos['symbol']:
                logger.info(f"   • Symbol: {pos['symbol']}")
                logger.info(f"   • Side: {pos['side']}")
                logger.info(f"   • Size: {pos['size']}")
                logger.info(f"   • Entry: ${pos['entry_price']:,.2f}")
                logger.info(f"   • P&L: ${pos.get('unrealized_pnl', 0):+.2f}")
        
        # Step 6: Close position
        logger.info("\n6. Closing Position...")
        await asyncio.sleep(2)  # Wait a moment
        
        close_result = await exchange.close_position(symbol, order_result['order_id'])
        logger.info(f"   ✅ Position Closed!")
        logger.info(f"   • Exit Price: ${close_result['exit_price']:,.2f}")
        logger.info(f"   • P&L: ${close_result['pnl']:+.2f}")
        logger.info(f"   • Fee: ${close_result['fee']:.2f}")
        
        # Step 7: Update database
        logger.info("\n7. Updating Database Record...")
        profit = close_result['pnl']
        profit_pct = (profit / (order_result['filled_price'] * quantity)) * 100
        
        async with async_session_maker() as db_session:
            from sqlalchemy import select
            stmt = select(PaperTrades).where(PaperTrades.id == trade_id)
            result = await db_session.execute(stmt)
            trade = result.scalar_one_or_none()
            
            if trade:
                trade.ts_close = datetime.utcnow().isoformat()
                trade.exit_price = close_result['exit_price']
                trade.profit = profit
                trade.profit_pct = profit_pct
                trade.status = 'closed'
                await db_session.commit()
                logger.info(f"   ✅ Trade updated (ID: {trade_id})")
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("TRADE EXECUTION COMPLETE")
        logger.info("="*80)
        logger.info(f"✅ Order ID: {order_result['order_id']}")
        logger.info(f"✅ Trade ID: {trade_id}")
        logger.info(f"✅ Entry: ${order_result['filled_price']:,.2f}")
        logger.info(f"✅ Exit: ${close_result['exit_price']:,.2f}")
        logger.info(f"✅ P&L: ${profit:+.2f} ({profit_pct:+.2f}%)")
        logger.info(f"✅ Status: CLOSED")
        logger.info("="*80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Trade failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await exchange.client.close()


async def main():
    success = await execute_demo_trade()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
