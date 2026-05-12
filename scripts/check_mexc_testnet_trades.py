#!/usr/bin/env python3
"""
Check current open paper trades on MEXC testnet.

This script performs two checks:
1. Database check: Queries local database for open MEXC paper trades
2. API check: Fetches actual open positions from MEXC testnet API

Usage:
    python scripts/check_mexc_testnet_trades.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from app.storage.models import PaperTrades
from app.storage.db import async_session_maker
from app.infra.mexc_client import MEXCClient
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def check_database_trades():
    """Check for open MEXC paper trades in local database."""
    logger.info("\n" + "="*80)
    logger.info("PART 1: Checking Local Database for Open MEXC Paper Trades")
    logger.info("="*80)
    
    async with async_session_maker() as db_session:
        # Query all open MEXC trades
        stmt = select(PaperTrades).where(
            PaperTrades.exchange == "mexc",
            PaperTrades.status == "open"
        ).order_by(PaperTrades.ts_open.desc())
        
        result = await db_session.execute(stmt)
        open_trades = result.scalars().all()
        
        logger.info(f"\n📊 Found {len(open_trades)} open MEXC paper trade(s) in database:\n")
        
        if not open_trades:
            logger.info("✅ No open trades found in database")
            return []
        
        trade_details = []
        for i, trade in enumerate(open_trades, 1):
            logger.info(f"--- Trade #{i} ---")
            logger.info(f"  Trade ID: {trade.id}")
            logger.info(f"  Symbol: {trade.symbol}")
            logger.info(f"  Side: {trade.side}")
            logger.info(f"  Entry Price: ${trade.entry_price:,.2f}")
            logger.info(f"  Exit Price: ${trade.exit_price:,.2f}" if trade.exit_price else "  Exit Price: N/A")
            logger.info(f"  Quantity: {trade.qty}")
            logger.info(f"  Leverage: {trade.leverage}x")
            logger.info(f"  Stop Loss: ${trade.stop_loss:,.2f}" if trade.stop_loss else "  Stop Loss: N/A")
            logger.info(f"  Take Profit: ${trade.take_profit:,.2f}" if trade.take_profit else "  Take Profit: N/A")
            logger.info(f"  Current P&L: ${trade.profit:+.2f}" if trade.profit is not None else "  Current P&L: N/A")
            logger.info(f"  P&L %: {trade.profit_pct:+.2f}%" if trade.profit_pct is not None else "  P&L %: N/A")
            logger.info(f"  Status: {trade.status}")
            logger.info(f"  Opened: {trade.ts_open}")
            logger.info(f"  User: {trade.user_id}")
            logger.info(f"  Execution Mode: {trade.execution_mode or 'N/A'}")
            logger.info("")
            
            trade_details.append({
                'id': trade.id,
                'symbol': trade.symbol,
                'side': trade.side,
                'entry_price': trade.entry_price,
                'qty': trade.qty,
                'leverage': trade.leverage,
                'ts_open': trade.ts_open
            })
        
        return trade_details


async def check_mexc_testnet_positions():
    """Fetch actual open positions from MEXC testnet API."""
    logger.info("\n" + "="*80)
    logger.info("PART 2: Checking MEXC Testnet API for Open Positions")
    logger.info("="*80)
    
    # Check if MEXC credentials are configured
    if not settings.MEXC_API_KEY or not settings.MEXC_API_SECRET:
        logger.warning("⚠️  MEXC API credentials not configured. Skipping API check.")
        logger.info("   Set MEXC_API_KEY and MEXC_API_SECRET in .env file to enable API check.")
        return []
    
    try:
        # Initialize MEXC client with testnet mode
        logger.info("\n🔌 Connecting to MEXC Futures Testnet...")
        mexc_client = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures',
            testnet=True  # Enable testnet mode
        )
        
        # Fetch account balance
        logger.info("\n💰 Fetching account balance...")
        balance = await mexc_client.fetch_balance()
        logger.info(f"   Total USDT: ${balance.get('total_usdt', 0):,.2f}")
        logger.info(f"   Free USDT: ${balance.get('free_usdt', 0):,.2f}")
        logger.info(f"   Used USDT: ${balance.get('used_usdt', 0):,.2f}")
        
        # Fetch open positions
        logger.info("\n📈 Fetching open positions...")
        positions = await mexc_client.fetch_open_positions()
        
        logger.info(f"\n📊 Found {len(positions)} open position(s) on MEXC testnet:\n")
        
        if not positions:
            logger.info("✅ No open positions found on MEXC testnet")
            await mexc_client.close()
            return []
        
        position_details = []
        for i, pos in enumerate(positions, 1):
            logger.info(f"--- Position #{i} ---")
            logger.info(f"  Symbol: {pos['symbol']}")
            logger.info(f"  Side: {pos['side'].upper()}")
            logger.info(f"  Size: {pos['size']}")
            logger.info(f"  Entry Price: ${pos['entry_price']:,.2f}" if pos.get('entry_price') else "  Entry Price: N/A")
            logger.info(f"  Mark Price: ${pos['mark_price']:,.2f}" if pos.get('mark_price') else "  Mark Price: N/A")
            logger.info(f"  Unrealized P&L: ${pos['unrealized_pnl']:+.2f}" if pos.get('unrealized_pnl') is not None else "  Unrealized P&L: N/A")
            logger.info(f"  Leverage: {pos['leverage']}x" if pos.get('leverage') else "  Leverage: N/A")
            logger.info(f"  Liquidation Price: ${pos['liquidation_price']:,.2f}" if pos.get('liquidation_price') else "  Liquidation Price: N/A")
            logger.info("")
            
            position_details.append(pos)
        
        await mexc_client.close()
        return position_details
        
    except Exception as e:
        logger.error(f"❌ Failed to connect to MEXC testnet: {e}")
        import traceback
        traceback.print_exc()
        return []


async def compare_results(db_trades, api_positions):
    """Compare database trades with API positions."""
    logger.info("\n" + "="*80)
    logger.info("PART 3: Comparison Analysis")
    logger.info("="*80)
    
    logger.info(f"\nDatabase open trades: {len(db_trades)}")
    logger.info(f"MEXC testnet positions: {len(api_positions)}")
    
    if len(db_trades) == 0 and len(api_positions) == 0:
        logger.info("\n✅ System is clean - no open trades or positions")
        return True
    
    if len(db_trades) > 0 and len(api_positions) == 0:
        logger.warning("\n⚠️  WARNING: Database has open trades but no positions on MEXC testnet")
        logger.warning("   This may indicate:")
        logger.warning("   - Trades were closed manually on MEXC but not updated in database")
        logger.warning("   - MEXC testnet was reset/cleared")
        logger.warning("   - Database synchronization issue")
        logger.warning("\n   Recommendation: Run cleanup script to sync database")
        return False
    
    if len(db_trades) == 0 and len(api_positions) > 0:
        logger.warning("\n⚠️  WARNING: MEXC testnet has open positions but no database records")
        logger.warning("   This may indicate:")
        logger.warning("   - Positions were opened outside the system")
        logger.warning("   - Database records were deleted/lost")
        logger.warning("   - Manual trading on MEXC testnet")
        logger.warning("\n   Recommendation: Sync positions to database using sync script")
        return False
    
    if len(db_trades) > 0 and len(api_positions) > 0:
        logger.info("\n✅ Both database and MEXC testnet have open positions")
        logger.info("   Note: Verify that database trades match actual positions")
        
        # Try to match by symbol
        db_symbols = set(t['symbol'] for t in db_trades)
        api_symbols = set(p['symbol'] for p in api_positions)
        
        logger.info(f"\n   Database symbols: {db_symbols}")
        logger.info(f"   API symbols: {api_symbols}")
        
        if db_symbols != api_symbols:
            logger.warning("\n   ⚠️  Symbol mismatch detected!")
            logger.warning(f"      In DB but not API: {db_symbols - api_symbols}")
            logger.warning(f"      In API but not DB: {api_symbols - db_symbols}")
            return False
        else:
            logger.info("\n   ✅ Symbols match between database and API")
            return True
    
    return True


async def main():
    """Main entry point."""
    print("\n" + "#"*80)
    print("# CHECKING OPEN PAPER TRADES ON MEXC TESTNET")
    print("#"*80)
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print(f"MEXC Testnet Mode: {'ENABLED' if settings.MEXC_API_KEY else 'DISABLED (no credentials)'}")
    
    try:
        # Step 1: Check database
        db_trades = await check_database_trades()
        
        # Step 2: Check MEXC testnet API
        api_positions = await check_mexc_testnet_positions()
        
        # Step 3: Compare results
        is_synced = await compare_results(db_trades, api_positions)
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        if is_synced:
            print("✅ Database and MEXC testnet are synchronized")
        else:
            print("⚠️  Synchronization issues detected - review warnings above")
        
        print(f"\nDatabase open trades: {len(db_trades)}")
        print(f"MEXC testnet positions: {len(api_positions)}")
        
        if len(db_trades) > 0:
            print("\nNext steps:")
            print("1. To close all open trades: python scripts/cleanup_and_restart_mexc_cycle.py")
            print("2. To view trade details: Check logs above")
        
        if len(api_positions) > 0 and len(db_trades) == 0:
            print("\nTo sync positions to database:")
            print("python scripts/sync_mexc_testnet_position.py")
        
        print("="*80 + "\n")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
