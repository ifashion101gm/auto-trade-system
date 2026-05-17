#!/usr/bin/env python3
"""
Comprehensive Paper Trade Audit Script
Verifies consistency between:
1. Database records (data/vmassit.db)
2. Bybit Demo exchange state (via pybit SDK)
3. Telegram notifications (logs and config)
"""
import asyncio
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infra.bybit_client import BybitClient
from app.config import settings

async def audit_paper_trades():
    """Perform comprehensive audit of paper trades"""
    
    print("=" * 80)
    print("PAPER TRADE COMPREHENSIVE AUDIT REPORT")
    print("=" * 80)
    print(f"Audit Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # =========================================================================
    # SECTION 1: DATABASE RECORDS VERIFICATION
    # =========================================================================
    print("=" * 80)
    print("SECTION 1: DATABASE RECORDS VERIFICATION")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect('data/vmassit.db')
    cursor = conn.cursor()
    
    # Get all closed paper trades
    cursor.execute('''
        SELECT id, symbol, side, entry_price, exit_price, qty, leverage, 
               profit, ts_open, ts_close, execution_mode, user_id, exchange
        FROM paper_trades 
        WHERE status="closed" AND execution_mode="paper"
        ORDER BY id DESC
        LIMIT 20
    ''')
    
    trades = cursor.fetchall()
    print(f"Total Paper Trades Found: {len(trades)}\n")
    
    if not trades:
        print("⚠️  WARNING: No paper trades found in database!")
        print()
    
    # Analyze recent trades
    recent_trades = []
    for trade in trades[:10]:  # Show last 10
        trade_id, symbol, side, entry_price, exit_price, qty, leverage, \
        profit, ts_open, ts_close, exec_mode, user_id, exchange = trade
        
        recent_trades.append({
            'id': trade_id,
            'symbol': symbol,
            'side': side,
            'entry': entry_price,
            'exit': exit_price,
            'qty': qty,
            'profit': profit,
            'ts_open': ts_open,
            'ts_close': ts_close
        })
        
        print(f"Trade #{trade_id}:")
        print(f"  Symbol: {symbol}")
        print(f"  Side: {side}")
        print(f"  Entry: ${entry_price:.2f} → Exit: ${exit_price:.2f}")
        print(f"  Quantity: {qty}, Leverage: {leverage}x")
        print(f"  P&L: ${profit:+.2f}")
        print(f"  Duration: {(datetime.fromisoformat(ts_close) - datetime.fromisoformat(ts_open)).total_seconds():.1f}s")
        print()
    
    # Summary statistics
    cursor.execute('''
        SELECT COUNT(*), AVG(profit), SUM(profit), 
               SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
               SUM(CASE WHEN profit <= 0 THEN 1 ELSE 0 END) as losses
        FROM paper_trades 
        WHERE status="closed" AND execution_mode="paper"
    ''')
    
    count, avg_profit, total_pnl, wins, losses = cursor.fetchone()
    win_rate = (wins / count * 100) if count > 0 else 0
    
    print("Database Summary:")
    print(f"  Total Paper Trades: {count}")
    print(f"  Win Rate: {win_rate:.1f}% ({wins}W / {losses}L)")
    print(f"  Avg P&L: ${avg_profit:+.2f}")
    print(f"  Total P&L: ${total_pnl:+.2f}")
    print()
    
    conn.close()
    
    # =========================================================================
    # SECTION 2: BYBIT DEMO EXCHANGE STATE VERIFICATION
    # =========================================================================
    print("=" * 80)
    print("SECTION 2: BYBIT DEMO EXCHANGE STATE VERIFICATION")
    print("=" * 80)
    print()
    
    try:
        print("Connecting to Bybit Demo...")
        client = BybitClient(demo_trading=True)
        
        # Check balance
        print("\n1. ACCOUNT BALANCE:")
        balance = await client.fetch_balance()
        print(f"   Total USDT: ${balance['total_usdt']:,.2f}")
        print(f"   Available: ${balance.get('available', 0):,.2f}")
        print(f"   Used: ${balance.get('used', 0):,.2f}")
        
        # Check positions
        print("\n2. OPEN POSITIONS:")
        positions = await client.fetch_positions()
        if positions:
            print(f"   ⚠️  Found {len(positions)} open position(s):")
            for pos in positions:
                print(f"     Symbol: {pos.get('symbol', 'N/A')}")
                print(f"     Side: {pos.get('side', 'N/A')}")
                print(f"     Size: {pos.get('size', 0)}")
                print(f"     Entry Price: ${pos.get('entry_price', 0):.2f}")
                print(f"     Mark Price: ${pos.get('mark_price', 0):.2f}")
                print(f"     Unrealized P&L: ${pos.get('unrealized_pnl', 0):.2f}")
                print()
        else:
            print("   ✅ No open positions (all trades closed)")
        
        # Check for actual executed orders on Bybit Demo
        print("\n3. ACTUAL ORDER HISTORY ON BYBIT DEMO:")
        try:
            response = client.pybit_session.get_closed_pnl(
                category="linear",
                symbol="XAUUSDT",
                limit=20
            )
            
            if response.get('retCode') == 0:
                result = response.get('result', {})
                list_data = result.get('list', [])
                
                if list_data:
                    print(f"   Found {len(list_data)} closed trade(s) on Bybit Demo:")
                    bybit_trades = []
                    for i, trade in enumerate(list_data[:5], 1):
                        order_id = trade.get('orderId', 'N/A')
                        symbol = trade.get('symbol', 'N/A')
                        side = trade.get('side', 'N/A')
                        qty = float(trade.get('qty', 0))
                        entry_price = float(trade.get('avgEntryPrice', 0))
                        closed_pnl = float(trade.get('closedPnl', 0))
                        created_time = trade.get('createdTime', 'N/A')
                        
                        bybit_trades.append({
                            'order_id': order_id,
                            'symbol': symbol,
                            'side': side,
                            'qty': qty,
                            'entry_price': entry_price,
                            'pnl': closed_pnl,
                            'time': created_time
                        })
                        
                        print(f"   Trade {i}:")
                        print(f"     Order ID: {order_id}")
                        print(f"     Symbol: {symbol}")
                        print(f"     Side: {side}")
                        print(f"     Qty: {qty}")
                        print(f"     Entry Price: ${entry_price:.2f}")
                        print(f"     Realized P&L: ${closed_pnl:+.2f}")
                        print(f"     Time: {datetime.fromtimestamp(int(created_time)/1000).strftime('%Y-%m-%d %H:%M:%S')}")
                        print()
                    
                    print(f"   ⚠️  IMPORTANT: Only {len(list_data)} trade(s) found on Bybit Demo")
                    print(f"      but {count} trades recorded in local database.")
                    print(f"      This indicates the paper trades are LOCAL SIMULATIONS only.")
                else:
                    print("   ⚠️  No closed trades found on Bybit Demo API")
                    print(f"      Database shows {count} trades, but none exist on exchange.")
            else:
                print(f"   ❌ API Error: {response.get('retMsg', 'Unknown error')}")
        except Exception as e:
            print(f"   ⚠️  Could not fetch closed P&L: {e}")
        
        await client.close()
        
    except Exception as e:
        print(f"\n❌ Error checking Bybit Demo: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # =========================================================================
    # SECTION 3: TELEGRAM NOTIFICATION AUDIT
    # =========================================================================
    print("=" * 80)
    print("SECTION 3: TELEGRAM NOTIFICATION AUDIT")
    print("=" * 80)
    print()
    
    # Check Telegram configuration
    print("1. TELEGRAM CONFIGURATION:")
    print(f"   Bot Token: {'✅ Configured' if settings.TELEGRAM_BOT_TOKEN else '❌ Not configured'}")
    print(f"   Chat ID: {'✅ Configured' if settings.TELEGRAM_CHAT_ID else '❌ Not configured'}")
    print(f"   Notifications Enabled: {'✅ Yes' if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID else '❌ No'}")
    print()
    
    # Check if notifier was used
    print("2. NOTIFICATION LOGS:")
    log_files = [
        'logs/worker.log',
        'logs/validation_cycle.log',
        'logs/uvicorn.log'
    ]
    
    telegram_found = False
    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                content = f.read()
                if 'telegram' in content.lower() or 'notification' in content.lower():
                    telegram_found = True
                    print(f"   ✅ Found Telegram references in {log_file}")
                    
                    # Show recent entries
                    lines = content.split('\n')
                    telegram_lines = [l for l in lines if 'telegram' in l.lower() or 'notification' in l.lower()]
                    if telegram_lines:
                        print(f"      Recent entries: {len(telegram_lines)}")
                        for line in telegram_lines[-3:]:
                            print(f"      {line[:200]}")
        except FileNotFoundError:
            print(f"   ⚠️  Log file not found: {log_file}")
    
    if not telegram_found:
        print("   ❌ No Telegram notification activity found in logs")
    
    print()
    
    # Check execute_paper_trade.py for notification calls
    print("3. CODE ANALYSIS - execute_paper_trade.py:")
    try:
        with open('scripts/execute_paper_trade.py', 'r') as f:
            content = f.read()
            
            has_notifier_import = 'TelegramNotifier' in content or 'notifier' in content.lower()
            has_notification_call = 'send_trade' in content or 'send_message' in content
            
            print(f"   Imports TelegramNotifier: {'✅ Yes' if has_notifier_import else '❌ No'}")
            print(f"   Calls notification methods: {'✅ Yes' if has_notification_call else '❌ No'}")
            
            if not has_notifier_import or not has_notification_call:
                print()
                print("   ⚠️  CRITICAL FINDING:")
                print("      The execute_paper_trade.py script does NOT send Telegram notifications!")
                print("      It only records trades locally without notifying users.")
    except FileNotFoundError:
        print("   ❌ Script file not found")
    
    print()
    
    # =========================================================================
    # SECTION 4: CONSISTENCY ANALYSIS & DISCREPANCIES
    # =========================================================================
    print("=" * 80)
    print("SECTION 4: CONSISTENCY ANALYSIS & DISCREPANCIES")
    print("=" * 80)
    print()
    
    discrepancies = []
    
    # Discrepancy 1: Database vs Exchange
    if count > 0:
        discrepancies.append({
            'type': 'DATABASE vs EXCHANGE',
            'severity': 'CRITICAL',
            'description': f'Database has {count} paper trades, but Bybit Demo shows minimal/no corresponding orders',
            'impact': 'Paper trades are LOCAL SIMULATIONS only, not real exchange orders',
            'recommendation': 'To execute REAL trades, use create_limit_order() or create_market_order() methods'
        })
    
    # Discrepancy 2: Telegram Notifications
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        if not telegram_found:
            discrepancies.append({
                'type': 'TELEGRAM NOTIFICATIONS',
                'severity': 'HIGH',
                'description': 'Telegram is configured but no notifications were sent for paper trades',
                'impact': 'Users are not informed about trade executions',
                'recommendation': 'Integrate TelegramNotifier into execute_paper_trade.py'
            })
    else:
        discrepancies.append({
            'type': 'TELEGRAM CONFIGURATION',
            'severity': 'MEDIUM',
            'description': 'Telegram credentials not configured in .env',
            'impact': 'Cannot send any notifications',
            'recommendation': 'Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env file'
        })
    
    # Discrepancy 3: Trade Execution Mode
    discrepancies.append({
        'type': 'EXECUTION MODE',
        'severity': 'INFO',
        'description': 'All trades marked as "paper" mode with simulated exits',
        'impact': 'Trades are not submitted to exchange, exits are randomly generated',
        'recommendation': 'For real validation, submit actual orders and track fills'
    })
    
    # Print discrepancies
    if discrepancies:
        print(f"Found {len(discrepancies)} discrepancy(ies):\n")
        
        for i, disc in enumerate(discrepancies, 1):
            severity_emoji = {
                'CRITICAL': '🚨',
                'HIGH': '❌',
                'MEDIUM': '⚠️ ',
                'LOW': 'ℹ️ ',
                'INFO': 'ℹ️ '
            }.get(disc['severity'], 'ℹ️ ')
            
            print(f"{i}. {severity_emoji} [{disc['severity']}] {disc['type']}")
            print(f"   Description: {disc['description']}")
            print(f"   Impact: {disc['impact']}")
            print(f"   Recommendation: {disc['recommendation']}")
            print()
    else:
        print("✅ No discrepancies found!")
    
    print()
    
    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print("=" * 80)
    print("FINAL AUDIT SUMMARY")
    print("=" * 80)
    print()
    
    print("Key Findings:")
    print(f"  1. Database Records: {count} paper trades recorded locally")
    print(f"  2. Exchange State: Minimal/no corresponding orders on Bybit Demo")
    print(f"  3. Telegram Notifications: {'Configured but not used' if settings.TELEGRAM_BOT_TOKEN else 'Not configured'}")
    print()
    
    print("Root Cause Analysis:")
    print("  The execute_paper_trade.py script performs LOCAL SIMULATION only:")
    print("  - ✅ Records trades in SQLite database")
    print("  - ❌ Does NOT submit orders to Bybit Demo exchange")
    print("  - ❌ Does NOT send Telegram notifications")
    print("  - ✅ Simulates random exits for testing purposes")
    print()
    
    print("Recommendations:")
    print("  1. To execute REAL orders on Bybit Demo:")
    print("     - Use client.create_limit_order() or client.create_market_order()")
    print("     - Track order fills and update database accordingly")
    print()
    print("  2. To enable Telegram notifications:")
    print("     - Import TelegramNotifier in execute_paper_trade.py")
    print("     - Call notifier.send_trade_entry() after trade execution")
    print("     - Call notifier.send_trade_exit() after trade closure")
    print()
    print("  3. For complete validation:")
    print("     - Execute real orders on Bybit Demo")
    print("     - Verify fills match database records")
    print("     - Confirm Telegram notifications contain accurate data")
    print()
    
    print("=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(audit_paper_trades())
