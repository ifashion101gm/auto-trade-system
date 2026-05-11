#!/usr/bin/env python3
"""Check database for open MEXC paper trades."""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from app.storage.models import PaperTrades
from app.storage.db import async_session_maker
from app.logging_config import get_logger

logger = get_logger(__name__)

async def check_open_trades():
    """Check for open MEXC paper trades in database."""
    logger.info("Checking database for open MEXC paper trades...")
    
    async with async_session_maker() as db_session:
        # Query all open MEXC trades
        stmt = select(PaperTrades).where(
            PaperTrades.exchange == "mexc",
            PaperTrades.status == "open"
        ).order_by(PaperTrades.ts_open.desc())
        
        result = await db_session.execute(stmt)
        open_trades = result.scalars().all()
        
        logger.info(f"\nFound {len(open_trades)} open MEXC trade(s):\n")
        
        if not open_trades:
            logger.info("✅ No open trades found - system is clean!")
            return True
        
        for trade in open_trades:
            logger.info(f"Trade ID: {trade.id}")
            logger.info(f"  Symbol: {trade.symbol}")
            logger.info(f"  Side: {trade.side}")
            logger.info(f"  Entry Price: ${trade.entry_price:,.2f}")
            logger.info(f"  Quantity: {trade.qty}")
            logger.info(f"  Leverage: {trade.leverage}x")
            logger.info(f"  Opened: {trade.ts_open}")
            logger.info(f"  User: {trade.user_id}")
            logger.info("")
        
        return len(open_trades) == 0

if __name__ == "__main__":
    result = asyncio.run(check_open_trades())
    sys.exit(0 if result else 1)
