#!/usr/bin/env python3
"""
Execute a single test trading cycle on Bybit Demo.
Temporarily enables MICRO_LIVE_ENABLED for testing purposes.
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# CRITICAL: Enable micro-live mode for this test
os.environ['MICRO_LIVE_ENABLED'] = 'true'

from app.config import settings
from app.database.connection import async_session_maker
from app.execution.trading_service import LiveTradingService
from app.logging_config import get_logger

logger = get_logger(__name__)


async def execute_test_cycle():
    """Execute a single test trading cycle for XAUUSDT on Bybit Demo."""
    
    print("\n" + "="*80)
    print("TEST TRADING CYCLE - BYBIT DEMO")
    print("="*80)
    print(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Symbol: XAUUSDT (Gold)")
    print(f"Exchange: Bybit Demo (api-demo.bybit.com)")
    print(f"Execution Mode: {settings.EXECUTION_MODE}")
    print(f"Micro-Live Enabled: {settings.MICRO_LIVE_ENABLED}")
    print("="*80)
    
    trading_service = None
    
    try:
        # Initialize trading service
        print("\n🔧 Initializing LiveTradingService...")
        trading_service = LiveTradingService(
            exchange_name="bybit",
            use_testnet=False,  # Bybit Demo uses demo domain, not testnet flag
            use_openrouter=True
        )
        
        symbol = "XAUUSDT"
        user_id = "test_user"
        
        print(f"\n🚀 Starting test trading cycle for {symbol}...")
        print(f"   This will execute through all stages:")
        print(f"   1. Pre-flight health check")
        print(f"   2. Market data fetching")
        print(f"   3. AI analysis (regime detection + strategy selection)")
        print(f"   4. Risk assessment")
        print(f"   5. Trade proposal generation")
        print(f"   6. Quality filter validation")
        print(f"   7. Order execution (if approved)")
        print(f"   8. Database persistence")
        print(f"   9. Telegram notification")
        
        # Execute trading cycle
        async with async_session_maker() as db_session:
            result = await trading_service.execute_trading_cycle(
                symbol=symbol,
                user_id=user_id,
                db_session=db_session
            )
        
        # Display comprehensive results
        print("\n" + "="*80)
        print("CYCLE EXECUTION RESULTS")
        print("="*80)
        
        status = result.get('status', 'unknown')
        print(f"\n📊 Overall Status: {status.upper()}")
        print(f"⏱️  Cycle Time: {result.get('cycle_time_ms', 0):.0f}ms")
        
        # Stage-by-stage breakdown
        stages = result.get('stages', {})
        if stages:
            print(f"\n📋 Stage Results:")
            for stage, stage_status in stages.items():
                emoji = "✅" if stage_status in ['success', 'executed', 'sent', 'completed'] else "❌"
                print(f"   {emoji} {stage.replace('_', ' ').title()}: {stage_status}")
        
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
            
            if 'strategy' in ai:
                strat = ai['strategy']
                print(f"   • Strategy: {strat.get('strategy', 'N/A')}")
                print(f"   • Confidence: {strat.get('confidence', 0):.2%}")
            
            if 'risk' in ai:
                risk = ai['risk']
                print(f"   • Risk Level: {risk.get('risk_level', 'N/A')}")
        
        # Trade proposal
        if 'trade_proposal' in result:
            proposal = result['trade_proposal']
            print(f"\n💼 Trade Proposal:")
            print(f"   • Side: {proposal.get('side', 'N/A')}")
            print(f"   • Entry Price: ${proposal.get('entry_price', 0):,.2f}")
            print(f"   • Stop Loss: ${proposal.get('stop_loss', 0):,.2f}")
            print(f"   • Take Profit: ${proposal.get('take_profit', 0):,.2f}")
            print(f"   • Quantity: {proposal.get('quantity', 0):.6f}")
            print(f"   • Leverage: {proposal.get('leverage', 1)}x")
            print(f"   • Position Value: ${proposal.get('position_value_usd', 0):,.2f}")
        
        # Execution details
        if 'execution' in result:
            exec_data = result['execution']
            print(f"\n⚡ Execution Details:")
            print(f"   • Status: {exec_data.get('status', 'N/A').upper()}")
            print(f"   • Order ID: {exec_data.get('order_id', 'N/A')}")
            print(f"   • Trade ID: {exec_data.get('trade_id', 'N/A')}")
            print(f"   • Filled Price: ${exec_data.get('filled_price', 0):,.2f}")
            print(f"   • Filled Quantity: {exec_data.get('filled_quantity', 0):.6f}")
        
        # Rejection details (if applicable)
        if status == 'rejected':
            reason = result.get('rejection_reason', 'Unknown')
            quality_score = result.get('quality_score', 0)
            print(f"\n⚠️  Trade Rejected by Quality Filter:")
            print(f"   • Quality Score: {quality_score}/100")
            print(f"   • Reason: {reason}")
            print(f"   ℹ️  This is NORMAL behavior - system protecting capital")
        
        # Self-healing info
        if 'self_healing' in result:
            sh = result['self_healing']
            print(f"\n🛡️  Self-Healing Status:")
            print(f"   • Can Continue: {sh.get('can_continue', False)}")
            if sh.get('issues'):
                print(f"   • Issues: {sh['issues']}")
        
        # Error details (if failed)
        if status == 'failed' or status == 'error':
            error = result.get('error', 'Unknown error')
            print(f"\n❌ Error Details:")
            print(f"   • {error}")
        
        # Final verdict
        print("\n" + "="*80)
        if status == 'success':
            print("✅ TEST CYCLE COMPLETED SUCCESSFULLY!")
            print("="*80)
            print("\nThe system successfully executed a complete trading cycle.")
            print("All components are functioning correctly.")
            return True
            
        elif status == 'rejected':
            print("⚠️  TRADE REJECTED (Quality Filter)")
            print("="*80)
            print("\nThe trade was rejected by the quality filter.")
            print("This is EXPECTED behavior when market conditions don't meet criteria.")
            print("The system is protecting capital from low-quality trades.")
            return True  # Rejection is not a failure
            
        elif status == 'micro_live_disabled':
            print("⏸️  MICRO-LIVE MODE DISABLED")
            print("="*80)
            print("\nTrading blocked because MICRO_LIVE_ENABLED=False")
            print("Set MICRO_LIVE_ENABLED=true in .env to enable trading")
            return False
            
        else:
            print("❌ TEST CYCLE FAILED")
            print("="*80)
            print(f"\nStatus: {status}")
            print("Check logs for detailed error information")
            return False
    
    except Exception as e:
        print(f"\n❌ EXCEPTION DURING TEST CYCLE")
        print("="*80)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if trading_service:
            await trading_service.close()
        
        print(f"\nFinished: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("="*80 + "\n")


def main():
    """Main entry point."""
    success = asyncio.run(execute_test_cycle())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
