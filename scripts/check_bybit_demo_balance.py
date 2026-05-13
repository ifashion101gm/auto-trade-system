#!/usr/bin/env python3
"""
Check current Bybit Demo account balance and trading statistics.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.database.connection import async_session_maker
from app.database.models import PaperTrades
from sqlalchemy import select, func


async def check_bybit_demo_balance():
    """Check current Bybit Demo account status."""
    print("=" * 80)
    print("BYBIT DEMO ACCOUNT - CURRENT STATUS")
    print("=" * 80)
    
    async with async_session_maker() as db:
        # Check total trades
        result = await db.execute(
            select(func.count(PaperTrades.id))
            .where(PaperTrades.exchange == 'bybit')
        )
        total_trades = result.scalar() or 0
        
        # Check closed trades
        result = await db.execute(
            select(func.count(PaperTrades.id))
            .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
        )
        closed_trades = result.scalar() or 0
        
        # Check open trades
        result = await db.execute(
            select(func.count(PaperTrades.id))
            .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'open')
        )
        open_trades = result.scalar() or 0
        
        print(f"\n📊 Trade Statistics:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Closed Trades: {closed_trades}")
        print(f"   Open Trades: {open_trades}")
        
        # Calculate cumulative P&L
        if closed_trades > 0:
            result = await db.execute(
                select(PaperTrades)
                .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
                .order_by(PaperTrades.ts_close)
            )
            all_trades = result.scalars().all()
            
            # Starting balance (actual Bybit Demo account balance verified via API)
            initial_balance = 49997.72
            current_balance = initial_balance
            
            for trade in all_trades:
                if trade.profit:
                    current_balance += trade.profit
            
            cumulative_profit = current_balance - initial_balance
            
            print(f"\n💰 Account Balance:")
            print(f"   Starting Balance: ${initial_balance:.2f}")
            print(f"   Current Balance: ${current_balance:.2f}")
            print(f"   Cumulative Profit: ${cumulative_profit:.2f}")
            print(f"   Progress to $100 Profit Goal: {(cumulative_profit/100)*100:.1f}%")
            
            if cumulative_profit >= 100:
                print(f"\n   🎉 GOAL ACHIEVED! $100 profit reached from $49,997.72 starting balance")
            elif cumulative_profit >= 50:
                print(f"\n   ⚠️  Halfway there! ${cumulative_profit:.2f}/$100 profit achieved")
            else:
                remaining = 100 - cumulative_profit
                print(f"\n   📈 Need ${remaining:.2f} more profit to reach $100 goal (0.2% return target)")
            
            # Win rate
            wins = sum(1 for t in all_trades if t.profit and t.profit > 0)
            losses = len(all_trades) - wins
            win_rate = (wins / len(all_trades)) * 100 if all_trades else 0
            
            print(f"\n📈 Performance Metrics:")
            print(f"   Wins: {wins}")
            print(f"   Losses: {losses}")
            print(f"   Win Rate: {win_rate:.2f}%")
            
            # Profit factor
            gross_profit = sum(t.profit for t in all_trades if t.profit and t.profit > 0)
            gross_loss = abs(sum(t.profit for t in all_trades if t.profit and t.profit < 0))
            
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss
            else:
                profit_factor = float('inf') if gross_profit > 0 else 0
            
            print(f"   Gross Profit: ${gross_profit:.2f}")
            print(f"   Gross Loss: ${gross_loss:.2f}")
            print(f"   Profit Factor: {profit_factor:.2f}")
            
            # Drawdown
            balance = initial_balance
            peak_balance = initial_balance
            max_drawdown = 0.0
            
            for trade in all_trades:
                if trade.profit:
                    balance += trade.profit
                    if balance > peak_balance:
                        peak_balance = balance
                    
                    drawdown = (peak_balance - balance) / peak_balance * 100
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
            
            print(f"\n📉 Risk Metrics:")
            print(f"   Peak Balance: ${peak_balance:.2f}")
            print(f"   Max Drawdown: {max_drawdown:.2f}%")
            
        else:
            print(f"\n⚠️  No closed trades yet. Starting balance: $49,997.72 (actual demo balance)")
            print(f"   Target: $100 cumulative profit (0.2% return)")
            print(f"   Need to execute trades to track progress toward $100 goal")
        
        print(f"\n{'=' * 80}")
        print("CONFIGURATION CHECK")
        print("=" * 80)
        
        # Check current .env settings
        from app.config import settings
        
        print(f"\nCurrent Configuration:")
        print(f"   BYBIT_USE_DEMO_DOMAIN: {settings.BYBIT_USE_DEMO_DOMAIN}")
        print(f"   ACTIVE_EXCHANGE: {settings.ACTIVE_EXCHANGE}")
        print(f"   EXECUTION_MODE: {settings.EXECUTION_MODE}")
        print(f"   GOLD_RISK_PER_TRADE: {settings.GOLD_RISK_PER_TRADE}")
        print(f"   GOLD_MAX_LEVERAGE: {settings.GOLD_MAX_LEVERAGE}")
        
        # Validation checks
        print(f"\nConfiguration Status:")
        if settings.BYBIT_USE_DEMO_DOMAIN:
            print(f"   ✅ Using Demo Environment")
        else:
            print(f"   ❌ NOT using demo environment!")
        
        if settings.ACTIVE_EXCHANGE == 'bybit':
            print(f"   ✅ Active exchange is Bybit")
        else:
            print(f"   ❌ Active exchange is '{settings.ACTIVE_EXCHANGE}' (should be 'bybit')")
        
        if settings.GOLD_RISK_PER_TRADE <= 0.005:
            print(f"   ✅ Risk per trade is conservative ({settings.GOLD_RISK_PER_TRADE*100:.2f}%)")
        else:
            print(f"   ⚠️  Risk per trade is {settings.GOLD_RISK_PER_TRADE*100:.2f}% (elite target: 0.5%)")
        
        if settings.GOLD_MAX_LEVERAGE <= 3:
            print(f"   ✅ Leverage is conservative ({settings.GOLD_MAX_LEVERAGE}x)")
        else:
            print(f"   ⚠️  Leverage is {settings.GOLD_MAX_LEVERAGE}x (elite target: 3x)")


if __name__ == "__main__":
    asyncio.run(check_bybit_demo_balance())
