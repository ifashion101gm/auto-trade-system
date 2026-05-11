#!/usr/bin/env python3
"""Check all recent MEXC trades including rejected ones."""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, func
from app.storage.models import PaperTrades
from app.storage.db import async_session_maker
from app.logging_config import get_logger

logger = get_logger(__name__)

async def check_recent_trades():
    """Check for recent MEXC trades in database."""
    logger.info("Checking database for recent MEXC trades...")
    
    async with async_session_maker() as db_session:
        # Get total count
        stmt_total = select(func.count(PaperTrades.id)).where(
            PaperTrades.exchange == "mexc"
        )
        result_total = await db_session.execute(stmt_total)
        total_count = result_total.scalar() or 0
        
        logger.info(f"\nTotal MEXC trades in database: {total_count}\n")
        
        if total_count == 0:
            logger.info("✅ No trades found - this is a fresh start!")
            return
        
        # Query recent trades (last 10)
        stmt = select(PaperTrades).where(
            PaperTrades.exchange == "mexc"
        ).order_by(PaperTrades.ts_open.desc()).limit(10)
        
        result = await db_session.execute(stmt)
        trades = result.scalars().all()
        
        logger.info(f"Recent trades:\n")
        
        for trade in trades:
            status_emoji = {
                'open': '🟢',
                'closed': '✅',
                'rejected': '❌',
                'cancelled': '⚠️'
            }.get(trade.status, '❓')
            
            logger.info(f"{status_emoji} Trade ID: {trade.id}")
            logger.info(f"   Symbol: {trade.symbol}")
            logger.info(f"   Side: {trade.side}")
            logger.info(f"   Status: {trade.status.upper()}")
            if trade.entry_price:
                logger.info(f"   Entry Price: ${trade.entry_price:,.2f}")
            if trade.qty:
                logger.info(f"   Quantity: {trade.qty}")
            if trade.leverage:
                logger.info(f"   Leverage: {trade.leverage}x")
            if trade.profit is not None:
                logger.info(f"   P&L: ${trade.profit:+.2f}")
            logger.info(f"   Opened: {trade.ts_open}")
            if trade.ts_close:
                logger.info(f"   Closed: {trade.ts_close}")
            if trade.notes:
                # Truncate long notes
                notes_preview = trade.notes[:100] + "..." if len(trade.notes) > 100 else trade.notes
                logger.info(f"   Notes: {notes_preview}")
            logger.info("")

if __name__ == "__main__":
    asyncio.run(check_recent_trades())
