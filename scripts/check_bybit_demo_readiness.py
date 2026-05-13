#!/usr/bin/env python3
"""
Quick diagnostic script to check current paper trading status for Bybit.
Runs all key validation checks from the Gold Bot V2 Elite plan.
"""
import asyncio
from app.storage.db import async_session_maker
from app.storage.models import PaperTrades
from sqlalchemy import select, func


async def check_bybit_demo_status():
    """Check current Bybit Demo paper trading statistics."""
    print("=" * 80)
    print("GOLD BOT V2 ELITE - BYBIT DEMO STATUS CHECK")
    print("=" * 80)
    
    async with async_session_maker() as db:
        # Total trades
        result = await db.execute(
            select(func.count(PaperTrades.id))
            .where(PaperTrades.exchange == 'bybit')
        )
        total_trades = result.scalar() or 0
        
        # Closed trades
        result = await db.execute(
            select(func.count(PaperTrades.id))
            .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
        )
        closed_trades = result.scalar() or 0
        
        # Open trades
        result = await db.execute(
            select(func.count(PaperTrades.id))
            .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'open')
        )
        open_trades = result.scalar() or 0
        
        print(f"\n📊 Trade Volume:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Closed Trades: {closed_trades}")
        print(f"   Open Trades: {open_trades}")
        
        if closed_trades >= 50:
            print(f"   ✅ PASS: Minimum 50 trades achieved")
        else:
            remaining = 50 - closed_trades
            print(f"   ❌ NEED {remaining} more trades to reach minimum")
        
        # Win rate (last 50 closed trades)
        if closed_trades > 0:
            result = await db.execute(
                select(PaperTrades)
                .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
                .order_by(PaperTrades.ts_close.desc())
                .limit(min(50, closed_trades))
            )
            recent_trades = result.scalars().all()
            
            wins = sum(1 for t in recent_trades if t.profit and t.profit > 0)
            losses = len(recent_trades) - wins
            win_rate = (wins / len(recent_trades)) * 100 if recent_trades else 0
            
            print(f"\n📈 Performance (Last {len(recent_trades)} Trades):")
            print(f"   Wins: {wins}")
            print(f"   Losses: {losses}")
            print(f"   Win Rate: {win_rate:.2f}%")
            
            if win_rate >= 60:
                print(f"   ✅ ELITE: Win rate ≥ 60%")
            elif win_rate >= 55:
                print(f"   ⚠️  ACCEPTABLE: Win rate 55-60%")
            else:
                print(f"   ❌ BELOW MINIMUM: Win rate < 55%")
            
            # Profit factor
            gross_profit = sum(t.profit for t in recent_trades if t.profit and t.profit > 0)
            gross_loss = abs(sum(t.profit for t in recent_trades if t.profit and t.profit < 0))
            
            if gross_loss > 0:
                profit_factor = gross_profit / gross_loss
            else:
                profit_factor = float('inf') if gross_profit > 0 else 0
            
            net_pnl = gross_profit - gross_loss
            
            print(f"\n💰 Profitability:")
            print(f"   Gross Profit: ${gross_profit:.2f}")
            print(f"   Gross Loss: ${gross_loss:.2f}")
            print(f"   Net P&L: ${net_pnl:.2f}")
            print(f"   Profit Factor: {profit_factor:.2f}")
            
            if profit_factor >= 2.0:
                print(f"   ✅ ELITE: PF ≥ 2.0")
            elif profit_factor >= 1.5:
                print(f"   ⚠️  ACCEPTABLE: PF 1.5-2.0")
            else:
                print(f"   ❌ BELOW MINIMUM: PF < 1.5")
            
            # Drawdown analysis
            initial_balance = 100.0
            balance = initial_balance
            peak_balance = initial_balance
            max_drawdown = 0.0
            
            # Get trades in chronological order
            result = await db.execute(
                select(PaperTrades)
                .where(PaperTrades.exchange == 'bybit', PaperTrades.status == 'closed')
                .order_by(PaperTrades.ts_close)
            )
            all_trades = result.scalars().all()
            
            for trade in all_trades:
                if trade.profit:
                    balance += trade.profit
                    if balance > peak_balance:
                        peak_balance = balance
                    
                    drawdown = (peak_balance - balance) / peak_balance * 100
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
            
            print(f"\n📉 Risk Management:")
            print(f"   Starting Balance: ${initial_balance:.2f}")
            print(f"   Current Balance: ${balance:.2f}")
            print(f"   Peak Balance: ${peak_balance:.2f}")
            print(f"   Max Drawdown: {max_drawdown:.2f}%")
            
            if max_drawdown <= 2.0:
                print(f"   ✅ ELITE: DD ≤ 2%")
            elif max_drawdown <= 5.0:
                print(f"   ⚠️  ACCEPTABLE: DD 2-5%")
            else:
                print(f"   ❌ EXCEEDS LIMIT: DD > 5%")
            
            # Risk-Reward ratio
            total_risk = 0
            total_reward = 0
            rr_count = 0
            
            for trade in recent_trades:
                if trade.entry_price and trade.stop_loss and trade.profit and trade.qty:
                    risk = abs(trade.entry_price - trade.stop_loss)
                    if trade.side == 'LONG':
                        reward = trade.profit / trade.qty
                    else:
                        reward = abs(trade.profit / trade.qty)
                    
                    if risk > 0:
                        total_risk += risk
                        total_reward += reward
                        rr_count += 1
            
            if rr_count > 0:
                avg_rr = total_reward / total_risk
                print(f"\n⚖️  Risk-Reward:")
                print(f"   Average R:R Ratio: {avg_rr:.2f}:1")
                
                if avg_rr >= 2.0:
                    print(f"   ✅ ELITE: R:R ≥ 2:1")
                elif avg_rr >= 1.5:
                    print(f"   ⚠️  ACCEPTABLE: R:R 1.5-2:1")
                else:
                    print(f"   ❌ BELOW MINIMUM: R:R < 1.5:1")
        
        # Overall readiness assessment
        print(f"\n{'=' * 80}")
        print("OVERALL READINESS ASSESSMENT")
        print("=" * 80)
        
        checks_passed = 0
        checks_total = 5
        
        if closed_trades >= 50:
            checks_passed += 1
            print("✅ [1/5] Trade Volume: PASSED")
        else:
            print(f"❌ [1/5] Trade Volume: FAILED ({closed_trades}/50)")
        
        if closed_trades > 0 and win_rate >= 55:
            checks_passed += 1
            print(f"✅ [2/5] Win Rate: PASSED ({win_rate:.2f}%)")
        elif closed_trades > 0:
            print(f"❌ [2/5] Win Rate: FAILED ({win_rate:.2f}% < 55%)")
        
        if closed_trades > 0 and profit_factor >= 1.5:
            checks_passed += 1
            print(f"✅ [3/5] Profit Factor: PASSED ({profit_factor:.2f})")
        elif closed_trades > 0:
            print(f"❌ [3/5] Profit Factor: FAILED ({profit_factor:.2f} < 1.5)")
        
        if max_drawdown <= 5.0:
            checks_passed += 1
            print(f"✅ [4/5] Max Drawdown: PASSED ({max_drawdown:.2f}%)")
        else:
            print(f"❌ [4/5] Max Drawdown: FAILED ({max_drawdown:.2f}% > 5%)")
        
        if rr_count > 0 and avg_rr >= 1.5:
            checks_passed += 1
            print(f"✅ [5/5] Risk-Reward: PASSED ({avg_rr:.2f}:1)")
        elif rr_count > 0:
            print(f"❌ [5/5] Risk-Reward: FAILED ({avg_rr:.2f}:1 < 1.5:1)")
        
        print(f"\nScore: {checks_passed}/{checks_total} checks passed")
        
        if checks_passed == checks_total:
            print("\n🎉 READY FOR LIVE TRADING VALIDATION!")
            print("   Next step: Verify Bybit Live API connectivity")
        elif checks_passed >= 3:
            print("\n⚠️  PARTIALLY READY - Continue paper trading")
            print(f"   Need {checks_total - checks_passed} more criteria to pass")
        else:
            print("\n❌ NOT READY - More paper trading needed")
            print("   Focus on improving strategy performance")


if __name__ == "__main__":
    asyncio.run(check_bybit_demo_status())
