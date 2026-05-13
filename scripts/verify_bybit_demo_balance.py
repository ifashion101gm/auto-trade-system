#!/usr/bin/env python3
"""
Verify Bybit Demo Account Balance via API
Compares actual API balance with database records
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from pybit.unified_trading import HTTP
from app.config import settings


async def verify_bybit_demo_balance():
    """Check actual Bybit Demo balance via API and compare with database."""
    print("=" * 80)
    print("BYBIT DEMO ACCOUNT - API BALANCE VERIFICATION")
    print("=" * 80)
    
    try:
        # Initialize Bybit Demo client
        print("\n🔌 Connecting to Bybit Demo API...")
        client = HTTP(
            testnet=False,  # Bybit Demo doesn't use testnet
            demo=True,      # Enable demo trading mode
            api_key=settings.BYBIT_DEMO_API_KEY,
            api_secret=settings.BYBIT_DEMO_API_SECRET,
        )
        
        # Get wallet balance
        print("📊 Fetching wallet balance...")
        balance_response = client.get_wallet_balance(accountType="UNIFIED")
        
        if balance_response.get('retCode') == 0:
            result = balance_response.get('result', {})
            list_data = result.get('list', [])
            
            if list_data:
                account = list_data[0]
                coin_list = account.get('coin', [])
                
                # Find USDT balance
                usdt_balance = None
                for coin in coin_list:
                    if coin.get('coin') == 'USDT':
                        # Helper function to safely convert to float
                        def safe_float(value, default=0.0):
                            if value is None or value == '':
                                return default
                            try:
                                return float(value)
                            except (ValueError, TypeError):
                                return default
                        
                        usdt_balance = {
                            'equity': safe_float(coin.get('equity')),
                            'wallet_balance': safe_float(coin.get('walletBalance')),
                            'available_to_withdraw': safe_float(coin.get('availableToWithdraw')),
                            'available_to_borrow': safe_float(coin.get('availableToBorrow')),
                            'borrow_amount': safe_float(coin.get('borrowAmount')),
                            'unrealised_pnl': safe_float(coin.get('unrealisedPnl')),
                            'cum_realised_pnl': safe_float(coin.get('cumRealisedPnl')),
                        }
                        break
                
                if usdt_balance:
                    print("\n" + "=" * 80)
                    print("ACTUAL BYBIT DEMO ACCOUNT BALANCE (via API)")
                    print("=" * 80)
                    print(f"\n USDT Balance Details:")
                    print(f"   Equity: ${usdt_balance['equity']:,.2f} USDT")
                    print(f"   Wallet Balance: ${usdt_balance['wallet_balance']:,.2f} USDT")
                    print(f"   Available to Withdraw: ${usdt_balance['available_to_withdraw']:,.2f} USDT")
                    print(f"   Available to Borrow: ${usdt_balance['available_to_borrow']:,.2f} USDT")
                    print(f"   Borrow Amount: ${usdt_balance['borrow_amount']:,.2f} USDT")
                    print(f"   Unrealized P&L: ${usdt_balance['unrealised_pnl']:,.2f} USDT")
                    print(f"   Cumulative Realized P&L: ${usdt_balance['cum_realised_pnl']:,.2f} USDT")
                    
                    print(f"\n{'=' * 80}")
                    print("COMPARISON WITH DATABASE RECORDS")
                    print("=" * 80)
                    
                    # Now check database records
                    from app.database.connection import async_session_maker
                    from app.database.models import PaperTrades
                    from sqlalchemy import select, func
                    
                    async with async_session_maker() as db:
                        # Count trades
                        result = await db.execute(
                            select(func.count(PaperTrades.id))
                            .where(PaperTrades.exchange == 'bybit')
                        )
                        total_trades = result.scalar() or 0
                        
                        result = await db.execute(
                            select(func.count(PaperTrades.id))
                            .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
                        )
                        closed_trades = result.scalar() or 0
                        
                        # Calculate database balance
                        db_starting_balance = 100.0
                        db_current_balance = db_starting_balance
                        
                        if closed_trades > 0:
                            result = await db.execute(
                                select(PaperTrades)
                                .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
                                .order_by(PaperTrades.ts_close)
                            )
                            all_trades = result.scalars().all()
                            
                            for trade in all_trades:
                                if trade.profit:
                                    db_current_balance += trade.profit
                        
                        db_cumulative_profit = db_current_balance - db_starting_balance
                        
                        print(f"\n Database Records:")
                        print(f"   Starting Balance (configured): ${db_starting_balance:.2f}")
                        print(f"   Current Balance (calculated): ${db_current_balance:.2f}")
                        print(f"   Cumulative Profit: ${db_cumulative_profit:.2f}")
                        print(f"   Total Trades: {total_trades}")
                        print(f"   Closed Trades: {closed_trades}")
                        
                        print(f"\n{'=' * 80}")
                        print("DISCREPANCY ANALYSIS")
                        print("=" * 80)
                        
                        api_equity = usdt_balance['equity']
                        db_balance = db_current_balance
                        discrepancy = api_equity - db_balance
                        
                        print(f"\n⚠️  BALANCE DISCREPANCY DETECTED:")
                        print(f"   API Actual Balance: ${api_equity:,.2f} USDT")
                        print(f"   Database Balance: ${db_balance:.2f}")
                        print(f"   Difference: ${discrepancy:,.2f}")
                        
                        print(f"\n🔍 Possible Explanations:")
                        if api_equity > 100000 and db_balance == 100.0:
                            print(f"   1. Bybit Demo account was reset/topped up to ~100K USDT (standard demo balance)")
                            print(f"   2. Database is tracking a separate $100 paper trading simulation")
                            print(f"   3. The $100 goal is for PAPER TRADING TRACKING, not actual demo balance")
                            print(f"   4. System uses $100 as virtual starting point for performance measurement")
                        
                        print(f"\n✅ RECOMMENDATION:")
                        print(f"   The Bybit Demo account has ~100K USDT (standard demo allocation)")
                        print(f"   Your $100 profit goal is a PAPER TRADING target")
                        print(f"   Continue tracking progress via PaperTrades table")
                        print(f"   Actual demo balance doesn't affect the $100 validation goal")
                        
                    print(f"\n{'=' * 80}")
                    print("VERIFICATION COMPLETE")
                    print("=" * 80)
                    
                else:
                    print("❌ USDT not found in account balance")
            else:
                print("❌ No account data returned")
        else:
            print(f"❌ API Error: {balance_response.get('retMsg', 'Unknown error')}")
            print(f"   RetCode: {balance_response.get('retCode')}")
            
    except Exception as e:
        print(f"❌ Error connecting to Bybit Demo API: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify_bybit_demo_balance())
