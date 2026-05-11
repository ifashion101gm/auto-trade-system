#!/usr/bin/env python3
"""Execute a single MEXC Gold futures validation cycle."""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.storage.db import async_session_maker
from app.services.live_trading_service import LiveTradingService
from app.logging_config import get_logger

logger = get_logger(__name__)

async def execute_cycle():
    """Execute a single trading cycle for MEXC Gold futures."""
    logger.info("\n" + "="*80)
    logger.info("MEXC GOLD FUTURES VALIDATION CYCLE")
    logger.info("="*80)
    logger.info(f"Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info(f"Symbol: {settings.GOLD_SYMBOL_MEXC}")
    logger.info(f"Exchange: MEXC Futures")
    
    trading_service = None
    try:
        # Initialize trading service
        trading_service = LiveTradingService(
            exchange_name="mexc",
            use_testnet=False,  # MEXC Demo Futures doesn't use testnet flag
            use_openrouter=True
        )
        
        symbol = settings.GOLD_SYMBOL_MEXC
        user_id = "default_user"
        
        logger.info(f"\n🚀 Starting validation cycle for {symbol}...")
        
        async with async_session_maker() as db_session:
            result = await trading_service.execute_trading_cycle(
                symbol=symbol,
                user_id=user_id,
                db_session=db_session
            )
        
        # Display results
        logger.info("\n" + "="*80)
        logger.info("CYCLE RESULTS")
        logger.info("="*80)
        
        if result['status'] == 'success':
            logger.info("✅ Cycle completed successfully!")
            
            execution = result.get('execution', {})
            proposal = result.get('ai_result', {}).get('trade_proposal', {})
            
            logger.info(f"\nRegime: {result.get('ai_result', {}).get('regime', 'N/A')}")
            logger.info(f"Strategy: {proposal.get('strategy_name', 'N/A')}")
            logger.info(f"Confidence: {proposal.get('confidence', 0):.2%}")
            logger.info(f"Side: {proposal.get('side', 'N/A')}")
            logger.info(f"Entry Price: ${proposal.get('entry_price', 0):,.2f}")
            logger.info(f"Leverage: {proposal.get('leverage', 1)}x")
            logger.info(f"\nExecution Status: {execution.get('status', 'unknown').upper()}")
            logger.info(f"Trade ID: {execution.get('trade_id', 'N/A')}")
            logger.info(f"Order ID: {execution.get('order_id', 'N/A')}")
            logger.info(f"Cycle Time: {result.get('cycle_time_ms', 0):.0f}ms")
            
            return True
            
        elif result['status'] == 'rejected':
            reason = result.get('rejection_reason', 'Unknown')
            quality_score = result.get('quality_score', 0)
            
            logger.info(f"⚠️  Trade rejected by quality filter")
            logger.info(f"   Quality Score: {quality_score}/100")
            logger.info(f"   Reason: {reason}")
            logger.info(f"   Cycle Time: {result.get('cycle_time_ms', 0):.0f}ms")
            logger.info(f"\nℹ️  This is normal - the system is protecting capital from low-quality trades")
            
            return True  # Rejection is not an error
            
        else:
            logger.error(f"❌ Cycle failed: {result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception during cycle: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if trading_service:
            await trading_service.close()
        logger.info(f"\nFinished: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    result = asyncio.run(execute_cycle())
    sys.exit(0 if result else 1)
