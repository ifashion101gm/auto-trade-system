#!/usr/bin/env python3
"""
Reconciliation Script - Sync Bybit Demo Orders with Database

This script compares executed orders on Bybit Demo with local database records
and creates missing trade entries to ensure data consistency.

Usage:
    python scripts/reconcile_bybit_orders.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infra.bybit_client import BybitClient
from app.config import settings
from app.database.connection import get_session
from app.database.models import PaperTrades
from sqlalchemy import select


async def reconcile_orders():
    """Reconcile Bybit Demo orders with database."""
    print("="*80)
    print("BYBIT DEMO ORDER RECONCILIATION")
    print("="*80)
    
    # Initialize Bybit client
    client = BybitClient(
        api_key=settings.BYBIT_DEMO_API_KEY,
        api_secret=settings.BYBIT_DEMO_API_SECRET,
        testnet=False,
        demo_trading=True
    )
    
    try:
        # Fetch order history from Bybit
        print("\n📊 Fetching order history from Bybit Demo...")
        bybit_symbol = 'XAUUSDT'
        
        response = client.pybit_session.get_order_history(
            category='linear',
            symbol=bybit_symbol,
            limit=50  # Get more to be safe
        )
        
        result = response.get('result', {}).get('list', [])
        print(f"   Found {len(result)} orders in Bybit history")
        
        if not result:
            print("   ⚠️  No orders found - nothing to reconcile")
            return
        
        # Get existing trades from database
        async with get_session() as session:
            stmt = select(PaperTrades).order_by(PaperTrades.ts_open.desc())
            db_result = await session.execute(stmt)
            db_trades = db_result.scalars().all()
            
            print(f"   Found {len(db_trades)} trades in database")
            
            # Create set of existing order IDs for quick lookup
            existing_order_ids = {t.order_id for t in db_trades if t.order_id}
            print(f"   Existing order IDs: {len(existing_order_ids)}")
            
            # Identify missing orders
            missing_orders = []
            for order in result:
                order_id = order.get('orderId')
                status = order.get('orderStatus')
                
                # Only process filled orders
                if status == 'Filled' and order_id not in existing_order_ids:
                    missing_orders.append(order)
            
            print(f"\n🔍 Reconciliation Results:")
            print(f"   • Total Bybit orders: {len(result)}")
            print(f"   • Database trades: {len(db_trades)}")
            print(f"   • Missing trades: {len(missing_orders)}")
            
            if not missing_orders:
                print("\n✅ Database is in sync - no reconciliation needed")
                return
            
            # Create missing trade records
            print(f"\n📝 Creating {len(missing_orders)} missing trade records...")
            
            created_count = 0
            for order in missing_orders:
                try:
                    side = order.get('side', '').lower()  # 'Buy' or 'Sell'
                    qty = float(order.get('qty', 0))
                    avg_price = float(order.get('avgPrice', 0))
                    created_time = int(order.get('createdTime', 0))
                    order_id = order.get('orderId')
                    
                    # Convert timestamp
                    ts_open = datetime.fromtimestamp(created_time / 1000, tz=timezone.utc).isoformat()
                    
                    # Determine if this is part of a round trip (buy then sell or vice versa)
                    # For simplicity, we'll create individual trade records
                    # P&L calculation would require matching buy/sell pairs
                    
                    trade = PaperTrades(
                        ts_open=ts_open,
                        ts_close=ts_open,  # Assume closed immediately for market orders
                        user_id='reconciled',
                        exchange='bybit_demo',
                        symbol='XAU/USDT:USDT',
                        side=side.upper(),
                        leverage=1,  # Default leverage
                        qty=qty,
                        entry_price=avg_price,
                        exit_price=avg_price,  # Same as entry for now
                        stop_loss=None,
                        take_profit=None,
                        profit=0.0,  # Would need pair matching to calculate
                        profit_pct=0.0,
                        status='closed',
                        trade_status='POSITION_CLOSED',
                        notes=f'Reconciled from Bybit order history. Order ID: {order_id}',
                        execution_mode='demo',
                        order_id=order_id
                    )
                    
                    session.add(trade)
                    await session.flush()
                    created_count += 1
                    
                    print(f"   ✅ Created trade #{trade.id}: {side} {qty} @ ${avg_price:.2f}")
                    
                except Exception as e:
                    print(f"   ❌ Failed to create trade for order {order.get('orderId')}: {e}")
            
            # Commit all changes
            await session.commit()
            print(f"\n✅ Successfully reconciled {created_count} trades")
            
            # Show summary
            stmt = select(PaperTrades).where(PaperTrades.user_id == 'reconciled')
            result = await session.execute(stmt)
            reconciled_trades = result.scalars().all()
            
            print(f"\n📊 Reconciliation Summary:")
            print(f"   • Reconciled trades: {len(reconciled_trades)}")
            print(f"   • All marked as 'closed' (market orders)")
            print(f"   • P&L set to $0 (requires pair matching for accurate calculation)")
            print(f"   • User ID: 'reconciled' (for easy identification)")
            
    except Exception as e:
        print(f"\n❌ Reconciliation failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()
    
    print("\n" + "="*80)
    print("RECONCILIATION COMPLETE")
    print("="*80)


if __name__ == "__main__":
    print("\n⚠️  WARNING: This will modify the database to add missing trade records.")
    print("   Make sure you have a backup before proceeding.\n")
    
    response = input("Continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        asyncio.run(reconcile_orders())
    else:
        print("Reconciliation cancelled.")
        sys.exit(0)
