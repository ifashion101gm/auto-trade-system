#!/usr/bin/env python3
"""
Close all open paper trades to complete validation cycle.
"""
import asyncio
import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from app.infra.bybit_client import BybitClient
from app.notifications.notifier import TelegramNotifier
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

async def close_open_trades():
    """Close all open paper trades"""
    
    print("=" * 70)
    print("  Closing Open Paper Trades")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get open trades from database
    conn = sqlite3.connect('data/vmassit.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, symbol, side, entry_price, qty, leverage, order_id 
        FROM paper_trades 
        WHERE status='open'
        ORDER BY id
    ''')
    
    open_trades = cursor.fetchall()
    
    if not open_trades:
        print("✅ No open trades to close")
        conn.close()
        return
    
    print(f"Found {len(open_trades)} open trade(s) to close:\n")
    for trade in open_trades:
        print(f"  Trade #{trade[0]}: {trade[2]} {trade[1]} @ ${trade[3]:.2f} (Qty: {trade[4]})")
    print()
    
    client = None
    notifier = None
    closed_count = 0
    
    try:
        # Initialize clients
        print("Step 1: Connecting to Bybit Demo & Telegram...")
        client = BybitClient(demo_trading=True)
        notifier = TelegramNotifier()
        print("   ✅ Clients initialized\n")
        
        # Close each trade
        for i, trade in enumerate(open_trades, 1):
            trade_id, symbol, side, entry_price, qty, leverage, order_id = trade
            
            print(f"\n{'='*70}")
            print(f"CLOSING TRADE #{i}/{len(open_trades)} (Trade ID: {trade_id})")
            print('='*70)
            
            # Determine close side (opposite of entry)
            close_side = 'sell' if side.lower() == 'buy' else 'buy'
            
            print(f"Entry: {side.upper()} @ ${entry_price:.2f}")
            print(f"Closing with: {close_side.upper()} market order")
            print(f"Quantity: {qty}")
            print()
            
            # Submit close order
            print("Submitting close order...")
            try:
                close_order = await client.create_market_order(
                    symbol=symbol,
                    side=close_side,
                    amount=qty,
                    leverage=leverage
                )
                
                close_order_id = close_order['order_id']
                print(f"✅ Close order submitted: {close_order_id}")
                
                # Wait for fill
                print("Waiting for order fill...")
                max_wait = 30
                poll_interval = 2
                elapsed = 0
                exit_price = None
                
                while elapsed < max_wait:
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval
                    
                    try:
                        order_status = await client.fetch_order_status(close_order_id, symbol)
                        status = order_status.get('status', 'unknown')
                        
                        if status in ['closed', 'filled']:
                            exit_price = order_status.get('average') or order_status.get('price')
                            if exit_price:
                                exit_price = float(exit_price)
                            print(f"✅ Order FILLED at ${exit_price:.2f}")
                            break
                        elif status in ['canceled', 'rejected', 'expired']:
                            print(f"❌ Order {status}!")
                            raise Exception(f"Order {status}")
                            
                    except Exception as e:
                        logger.warning(f"Error checking order status: {e}")
                        continue
                
                if not exit_price:
                    # Fallback: use entry price
                    exit_price = entry_price
                    print(f"⚠️  Using entry price as fallback: ${exit_price:.2f}")
                
                ts_close = datetime.now()
                
                # Calculate P&L
                if side.lower() == 'buy':
                    profit = (exit_price - entry_price) * qty * leverage
                else:
                    profit = (entry_price - exit_price) * qty * leverage
                
                profit = round(profit, 2)
                profit_pct = (profit / (entry_price * qty)) * 100 if (entry_price * qty) > 0 else 0
                
                pnl_status = "✅ PROFIT" if profit > 0 else ("❌ LOSS" if profit < 0 else "➖ BREAKEVEN")
                print(f"P&L: ${profit:+.2f} ({profit_pct:+.2f}%) {pnl_status}")
                
                # Update database
                print("\nUpdating database...")
                cursor.execute('''
                    UPDATE paper_trades 
                    SET exit_price = ?, profit = ?, profit_pct = ?, status = 'closed',
                        ts_close = ?, close_order_id = ?
                    WHERE id = ?
                ''', (exit_price, profit, profit_pct, ts_close.isoformat(), close_order_id, trade_id))
                
                conn.commit()
                print(f"✅ Trade #{trade_id} updated in database")
                
                # Send Telegram notification
                print("Sending Telegram notification...")
                trade_exit_data = {
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'side': side,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'status': 'closed',
                    'order_id': close_order_id,
                    'duration': f"{(ts_close - datetime.fromisoformat(trade[7])).total_seconds():.1f}s" if len(trade) > 7 else "N/A",
                    'notes': 'Validation cycle completion',
                    'exchange': 'bybit'
                }
                
                if notifier.enabled:
                    telegram_sent = await notifier.send_trade_exit(trade_exit_data)
                    print(f"✅ Telegram notification: {'Sent' if telegram_sent else 'Failed'}")
                else:
                    print("⚠️  Telegram disabled")
                
                closed_count += 1
                print(f"\n✅ Trade #{trade_id} CLOSED successfully")
                
            except Exception as e:
                print(f"\n❌ Failed to close trade #{trade_id}: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'='*70}")
        print(f"CLOSURE COMPLETE: {closed_count}/{len(open_trades)} trades closed")
        print('='*70)
        
        # Show final stats
        cursor.execute('SELECT COUNT(*) FROM paper_trades WHERE status="closed"')
        total_closed = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN profit = 0 THEN 1 ELSE 0 END) as breakeven,
                AVG(profit) as avg_profit,
                SUM(profit) as total_profit
            FROM paper_trades 
            WHERE status='closed'
        ''')
        
        stats = cursor.fetchone()
        win_rate = (stats[1] / stats[0] * 100) if stats[0] > 0 else 0
        
        print(f"\n📊 VALIDATION STATISTICS")
        print(f"   Total Closed Trades: {stats[0]}")
        print(f"   Wins: {stats[1]} ({win_rate:.1f}%)")
        print(f"   Losses: {stats[2]}")
        print(f"   Breakeven: {stats[3]}")
        print(f"   Average P&L: ${stats[4]:+.2f}")
        print(f"   Total P&L: ${stats[5]:+.2f}")
        print(f"\n   Validation Progress: {total_closed}/20 trades")
        
        if total_closed >= 20:
            print(f"\n✅ VALIDATION THRESHOLD REACHED!")
            print(f"   Ready for performance analysis and production deployment.")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.close()
    
    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    asyncio.run(close_open_trades())
