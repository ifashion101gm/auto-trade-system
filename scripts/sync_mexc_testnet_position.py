"""
Sync MEXC testnet position to local database.
Manually syncs the GOLD position visible on testnet web interface.
"""
import asyncio
import sys
import uuid
from datetime import datetime

sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.storage.db import get_session
from app.storage.models import Trades, Positions
from app.exchange.mexc_demo import MEXCDemoExchange
from sqlalchemy import select


async def sync_mexc_testnet_position():
    """Sync the GOLD position from MEXC testnet to local database."""
    print("="*70)
    print("MEXC Testnet Position Sync")
    print("="*70)
    
    # Position data from screenshot
    # GOLD(XAUT)USDT Perpetual | 25,943.9883 USDT | Entry: 4,601.6 | Current: 4,723.0
    # 10X Long | PnL: +666.47 USDT (+26.36%)
    
    position_data = {
        'symbol': 'GOLD(XAUT)/USDT',
        'side': 'LONG',
        'size_usdt': 25943.9883,
        'entry_price': 4601.6,
        'current_price': 4723.0,
        'leverage': 10,
        'unrealized_pnl': 666.47,
        'margin_ratio': 0.0002  # 0.02%
    }
    
    # Calculate quantity in contracts
    quantity = position_data['size_usdt'] / position_data['entry_price']
    
    print(f"\n📊 Position Details (from screenshot):")
    print(f"   Symbol: {position_data['symbol']}")
    print(f"   Side: {position_data['side']}")
    print(f"   Size: {position_data['size_usdt']:,.2f} USDT")
    print(f"   Entry Price: ${position_data['entry_price']:,.1f}")
    print(f"   Current Price: ${position_data['current_price']:,.1f}")
    print(f"   Leverage: {position_data['leverage']}X")
    print(f"   Unrealized PnL: +${position_data['unrealized_pnl']:,.2f}")
    print(f"   Quantity: {quantity:.4f} contracts")
    
    # Try to fetch from actual testnet first
    print("\n📡 Attempting to fetch from MEXC testnet API...")
    try:
        exchange = MEXCDemoExchange(testnet=True)
        testnet_positions = await exchange.get_positions()
        
        if testnet_positions:
            print(f"   ✅ Found {len(testnet_positions)} position(s) on testnet")
            for pos in testnet_positions:
                print(f"   - {pos['symbol']}: {pos['side']} {pos['size']}")
        else:
            print("   ⚠️  No positions found via API (may be credential mismatch)")
        
        await exchange.client.close()
    except Exception as e:
        print(f"   ️  Could not fetch from testnet API: {e}")
    
    # Sync to local database
    print("\n📝 Syncing position to local database...")
    
    async for db_session in get_session():
        try:
            # Check if position already exists
            stmt = select(Positions).where(
                (Positions.symbol == position_data['symbol']) & 
                (Positions.status == 'open')
            )
            result = await db_session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                print("   ⚠️  Position already exists, updating...")
                existing.current_price = position_data['current_price']
                existing.unrealized_pnl = position_data['unrealized_pnl']
                existing.last_sync = datetime.utcnow().isoformat()
                await db_session.commit()
                print("   ✅ Position updated")
            else:
                print("   Creating new position record...")
                
                # Create trade
                trade_id = str(uuid.uuid4())
                trade = Trades(
                    id=trade_id,
                    mode='DEMO',
                    exchange='mexc',
                    symbol=position_data['symbol'],
                    side=position_data['side'],
                    status='open',
                    entry_price=position_data['entry_price'],
                    current_price=position_data['current_price'],
                    exit_price=None,
                    stop_loss=None,
                    take_profit=None,
                    leverage=position_data['leverage'],
                    quantity=quantity,
                    pnl=position_data['unrealized_pnl'],
                    pnl_pct=26.36,
                    exchange_order_id='testnet_manual_sync',
                    strategy_name='MANUAL_SYNC',
                    regime='unknown',
                    confidence=None,
                    created_at=datetime.utcnow().isoformat(),
                    closed_at=None
                )
                db_session.add(trade)
                await db_session.flush()
                
                # Create position
                position = Positions(
                    id=str(uuid.uuid4()),
                    trade_id=trade_id,
                    symbol=position_data['symbol'],
                    size=quantity,
                    entry_price=position_data['entry_price'],
                    current_price=position_data['current_price'],
                    unrealized_pnl=position_data['unrealized_pnl'],
                    liquidation_price=0,
                    leverage=position_data['leverage'],
                    status='open',
                    last_sync=datetime.utcnow().isoformat()
                )
                db_session.add(position)
                await db_session.commit()
                
                print(f"   ✅ Position synced!")
                print(f"   Trade ID: {trade_id}")
            
            # Summary
            print("\n" + "="*70)
            print("✅ SYNC COMPLETE")
            print("="*70)
            print("\n📈 Position is now tracked locally!")
            print("   The system will monitor and reconcile it automatically.")
            print("\n Current PnL: +$666.47 USDT (+26.36%)")
            print("   Great trade! 🎉")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            await db_session.rollback()
        
        break


if __name__ == "__main__":
    asyncio.run(sync_mexc_testnet_position())
