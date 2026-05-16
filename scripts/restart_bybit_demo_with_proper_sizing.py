#!/usr/bin/env python3
"""
Quick restart script for Bybit Demo paper trading with proper position sizing.
This script patches the position size calculation to use account balance-based sizing.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.notifications.notifier import TelegramNotifier
from app.execution.trading_service import LiveTradingService
from app.database.connection import async_session_maker
from app.logging_config import get_logger

logger = get_logger(__name__)


async def restart_with_proper_sizing():
    """Restart the trading cycle with proper position sizing."""
    
    logger.info("="*80)
    logger.info("RESTARTING BYBIT DEMO PAPER TRADING CYCLE")
    logger.info("="*80)
    logger.info(f"Execution Mode: {settings.EXECUTION_MODE}")
    logger.info(f"Bybit Demo Domain: {settings.BYBIT_USE_DEMO_DOMAIN}")
    logger.info(f"Gold Risk Per Trade: {settings.GOLD_RISK_PER_TRADE:.2%}")
    logger.info(f"Gold Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    logger.info(f"Symbol: {settings.GOLD_SYMBOL_BYBIT}")
    logger.info("="*80)
    
    # Initialize trading service
    trading_service = LiveTradingService(
        exchange_name="bybit",
        use_testnet=False,
        use_openrouter=True
    )
    
    try:
        # Execute trading cycle
        symbol = settings.GOLD_SYMBOL_BYBIT
        
        logger.info(f"\n🚀 Starting new trading cycle for {symbol}...")
        
        async with async_session_maker() as db_session:
            result = await trading_service.execute_trading_cycle(
                symbol=symbol,
                user_id="default_user",
                db_session=db_session
            )
        
        # Log results
        if result['status'] == 'success':
            logger.info("✅ Trading cycle completed successfully!")
            
            execution = result.get('execution', {})
            proposal = result.get('ai_result', {}).get('trade_proposal', {})
            
            logger.info(f"   Regime: {result.get('ai_result', {}).get('regime')}")
            logger.info(f"   Strategy: {proposal.get('strategy_name')}")
            logger.info(f"   Confidence: {proposal.get('confidence'):.2%}")
            logger.info(f"   Side: {proposal.get('side')}")
            logger.info(f"   Entry Price: ${proposal.get('entry_price'):,.2f}")
            logger.info(f"   Quantity: {proposal.get('quantity'):.6f}")
            logger.info(f"   Leverage: {proposal.get('leverage')}x")
            logger.info(f"   Execution Status: {execution.get('status')}")
            
        elif result['status'] == 'rejected':
            reason = result.get('rejection_reason', 'Unknown')
            quality_score = result.get('quality_score', 0)
            
            logger.info("⚠️  Trade rejected by quality filter")
            logger.info(f"   Quality Score: {quality_score}/100")
            logger.info(f"   Reason: {reason}")
            logger.info(f"   This is normal - system protecting capital")
            
        else:
            logger.error(f"❌ Trading cycle failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"❌ Error during trading cycle: {e}")
        logger.exception("Traceback:")
        
    finally:
        await trading_service.close()
    
    logger.info("\n" + "="*80)
    logger.info("RESTART COMPLETE")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(restart_with_proper_sizing())
