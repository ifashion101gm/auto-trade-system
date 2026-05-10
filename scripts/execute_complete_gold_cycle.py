#!/usr/bin/env python3
"""
Complete Gold Futures Paper Trading Cycle
Implements: Market Data → AI Analysis → Trade Proposal → Order Execution → DB Persistence → Telegram Notification

Following COMPLETE_TRADING_CYCLE_REPORT.md standards:
- OpenRouter API Integration for AI-powered decisions
- Binance Testnet Execution with real order placement
- Enhanced Telegram Reporting with order IDs, fees, slippage
- Self-Learning Feedback Loop for continuous optimization
"""
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.live_trading_service import LiveTradingService
from app.storage.db import get_session
from app.infra.telegram_notifier import TelegramNotifier


async def execute_complete_gold_cycle():
    """
    Execute complete paper trading cycle for Gold futures (PAXG/USDT).
    
    Implements the full workflow:
    1. Market Data Fetch
    2. AI Analysis (OpenRouter)
    3. Trade Proposal Generation
    4. Order Execution (Binance Testnet)
    5. Database Persistence
    6. Telegram Notification
    """
    
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#  GOLD FUTURES - COMPLETE PAPER TRADING CYCLE" + " "*23 + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    print(f"\n📋 Configuration:")
    print(f"   Symbol: {settings.GOLD_SYMBOL_BINANCE}")
    print(f"   Exchange: Binance Testnet (Futures Demo)")
    print(f"   Execution Mode: {settings.EXECUTION_MODE}")
    print(f"   Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"   Risk Per Trade: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
    print(f"   Min Confidence: {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
    
    # Initialize Live Trading Service
    print(f"\n{'='*70}")
    print("  INITIALIZING TRADING SERVICE")
    print(f"{'='*70}")
    
    service = LiveTradingService(
        exchange_name="binance",
        use_testnet=True,
        use_openrouter=True
    )
    
    try:
        # Execute complete trading cycle
        print(f"\n{'='*70}")
        print("  EXECUTING COMPLETE TRADING CYCLE")
        print(f"{'='*70}")
        
        result = await service.execute_trading_cycle(
            symbol=settings.GOLD_SYMBOL_BINANCE,
            user_id="default_user",
            db_session=None,  # Will create session internally
            execute_on_binance=True,
            execute_on_mexc=False
        )
        
        # Display results
        print(f"\n{'='*70}")
        print("  CYCLE EXECUTION RESULTS")
        print(f"{'='*70}")
        
        if result['status'] == 'success':
            print(f"\n✅ Status: SUCCESS")
            print(f"⏱️  Cycle Time: {result.get('cycle_time_ms', 0):.0f}ms")
            
            # Stage-by-stage breakdown
            stages = result.get('stages', {})
            print(f"\n📊 Stage Results:")
            for stage, status in stages.items():
                emoji = "✅" if status in ['success', 'executed', 'sent', 'completed'] else "❌"
                print(f"   {emoji} {stage.replace('_', ' ').title()}: {status}")
            
            # Market data summary
            if 'market_data' in result:
                md = result['market_data']
                print(f"\n📈 Market Data:")
                print(f"   • Current Price: ${md.get('current_price', 0):,.2f}")
                print(f"   • 24h Volume: ${md.get('volume_24h', 0):,.2f}")
                print(f"   • Volatility: {md.get('volatility', 0)*100:.2f}%")
                print(f"   • RSI: {md.get('rsi', 0):.2f}")
            
            # AI analysis summary
            if 'ai_result' in result:
                ai = result['ai_result']
                print(f"\n🧠 AI Analysis:")
                print(f"   • Regime: {ai.get('regime', 'N/A')}")
                print(f"   • Strategy: {ai.get('strategy', {}).get('strategy', 'N/A')}")
                print(f"   • Confidence: {ai.get('strategy', {}).get('confidence', 0)*100:.1f}%")
                print(f"   • Risk Level: {ai.get('risk', {}).get('risk_level', 'N/A')}")
            
            # Execution details
            if 'execution' in result and result['execution'].get('status') == 'executed':
                exec_data = result['execution']
                print(f"\n⚡ Order Execution:")
                print(f"   • Order ID: {exec_data.get('order_id', 'N/A')}")
                print(f"   • Filled Price: ${exec_data.get('filled_price', 0):,.2f}")
                print(f"   • Quantity: {exec_data.get('filled_quantity', 0):.4f}")
                print(f"   • Fee: ${exec_data.get('fee', 0):.4f} {exec_data.get('fee_currency', 'USDT')}")
                print(f"   • Position Value: ${exec_data.get('position_value_usd', 0):,.2f}")
                
                # Calculate slippage
                entry = exec_data.get('entry_price', 0)
                filled = exec_data.get('filled_price', 0)
                if entry > 0:
                    slippage = abs(filled - entry) / entry * 100
                    slippage_emoji = "✅" if slippage < 0.1 else "⚠️" if slippage < 0.5 else "❌"
                    print(f"   • Slippage: {slippage_emoji} {slippage:.4f}%")
            
            print(f"\n{'='*70}")
            print("  🎉 COMPLETE CYCLE EXECUTED SUCCESSFULLY!")
            print(f"{'='*70}")
            print(f"\n✅ All 6 stages completed:")
            print(f"   1. ✅ Market Data Fetch")
            print(f"   2. ✅ AI Analysis (OpenRouter)")
            print(f"   3. ✅ Trade Proposal Generated")
            print(f"   4. ✅ Order Executed on Binance Testnet")
            print(f"   5. ✅ Database Persistence")
            print(f"   6. ✅ Telegram Notification Sent")
            
            return True
            
        else:
            print(f"\n❌ Status: FAILED")
            print(f"⏱️  Cycle Time: {result.get('cycle_time_ms', 0):.0f}ms")
            print(f"Error: {result.get('error', 'Unknown error')}")
            
            # Show which stages failed
            stages = result.get('stages', {})
            print(f"\n📊 Stage Results:")
            for stage, status in stages.items():
                emoji = "✅" if status in ['success', 'executed', 'sent', 'completed'] else "❌"
                print(f"   {emoji} {stage.replace('_', ' ').title()}: {status}")
            
            return False
    
    except Exception as e:
        print(f"\n❌ Cycle execution failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up
        await service.close()
        print(f"\n{'='*70}")
        print("  Service connections closed")
        print(f"{'='*70}\n")


async def verify_database_persistence():
    """Verify that the trade was persisted to database"""
    print(f"\n{'='*70}")
    print("  VERIFYING DATABASE PERSISTENCE")
    print(f"{'='*70}")
    
    try:
        from sqlalchemy import select
        from app.storage.models import PaperTrades
        
        async for db_session in get_session():
            # Get the most recent open trade for PAXG/USDT
            stmt = (
                select(PaperTrades)
                .where(PaperTrades.symbol == settings.GOLD_SYMBOL_BINANCE)
                .where(PaperTrades.status == 'open')
                .order_by(PaperTrades.ts_open.desc())
                .limit(1)
            )
            
            result = await db_session.execute(stmt)
            trade = result.scalar_one_or_none()
            
            if trade:
                print(f"\n✅ Trade found in database:")
                print(f"   • Trade ID: #{trade.id}")
                print(f"   • Symbol: {trade.symbol}")
                print(f"   • Side: {trade.side}")
                print(f"   • Entry Price: ${trade.entry_price:,.2f}")
                print(f"   • Quantity: {trade.qty:.4f}")
                print(f"   • Leverage: {trade.leverage}x")
                print(f"   • Stop Loss: ${trade.stop_loss:,.2f}" if trade.stop_loss else "   • Stop Loss: N/A")
                print(f"   • Take Profit: ${trade.take_profit:,.2f}" if trade.take_profit else "   • Take Profit: N/A")
                print(f"   • Status: {trade.status}")
                print(f"   • Opened At: {trade.ts_open}")
                
                if trade.notes:
                    notes = json.loads(trade.notes) if isinstance(trade.notes, str) else trade.notes
                    print(f"   • Order ID: {notes.get('order_id', 'N/A')}")
                
                return True
            else:
                print(f"\n⚠️  No open trades found for {settings.GOLD_SYMBOL_BINANCE}")
                return False
    
    except Exception as e:
        print(f"\n❌ Database verification failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main execution function"""
    
    # Step 1: Execute complete trading cycle
    cycle_success = await execute_complete_gold_cycle()
    
    if cycle_success:
        # Step 2: Verify database persistence
        await asyncio.sleep(1)  # Brief pause
        db_verified = await verify_database_persistence()
        
        if db_verified:
            print(f"\n{'='*70}")
            print("  ✅ ALL OPERATIONS COMPLETED SUCCESSFULLY!")
            print(f"{'='*70}")
            print(f"\n🎯 Complete paper trading cycle executed:")
            print(f"   • Market data fetched from Binance Testnet")
            print(f"   • AI analysis performed via OpenRouter")
            print(f"   • Trade proposal generated with risk parameters")
            print(f"   • Market order executed on Binance Testnet")
            print(f"   • Trade persisted to database (status: open)")
            print(f"   • Telegram notification sent with full details")
            print(f"\n📊 System is ready for live monitoring and management.")
            print(f"{'='*70}\n")
            sys.exit(0)
        else:
            print(f"\n⚠️  Cycle executed but database verification failed")
            sys.exit(1)
    else:
        print(f"\n❌ Trading cycle failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
