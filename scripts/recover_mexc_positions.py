"""
Recovery script to sync open positions from MEXC testnet to local database.
Use this when positions exist on exchange but not in our database.
"""
import asyncio
import sys
import uuid
from datetime import datetime

sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.exchange.mexc_demo import MEXCDemoExchange
from app.storage.db import get_session
from app.storage.models import Trades, Positions
from sqlalchemy import select


async def sync_mexc_positions():
    """Sync open positions from MEXC testnet to local database."""
    print("="*70)
    print("MEXC Testnet Position Recovery & Sync")
    print("="*70)
    
    # Initialize exchange
    exchange = MEXCDemoExchange()
    
    try:
        # Fetch positions from MEXC
        print("\n📡 Fetching positions from MEXC testnet...")
        exchange_positions = await exchange.get_positions()
        
        if not exchange_positions:
            print("✅ No open positions found on MEXC testnet")
            return
        
        print(f"\n📊 Found {len(exchange_positions)} open position(s) on exchange\n")
        
        # Sync each position
        async for db_session in get_session():
            for ex_pos in exchange_positions:
                symbol = ex_pos['symbol']
                print(f"\n{'='*70}")
                print(f"Processing: {symbol}")
                print(f"{'='*70}")
                
                # Check if position already exists in DB
                stmt = select(Positions).where(
                    (Positions.symbol == symbol) & (Positions.status == 'open')
                )
                result = await db_session.execute(stmt)
                existing_position = result.scalar_one_or_none()
                
                if existing_position:
                    print(f"️  Position already exists in database, updating...")
                    existing_position.current_price = ex_pos['current_price']
                    existing_position.unrealized_pnl = ex_pos['unrealized_pnl']
                    existing_position.last_sync = datetime.utcnow().isoformat()
                    await db_session.commit()
                    print(f"✅ Position updated")
                else:
                    print(f"📝 Creating new position record in database...")
                    
                    # Create trade record
                    trade_id = str(uuid.uuid4())
                    
                    # Calculate quantity from position size
                    # For futures: size = quantity * entry_price
                    entry_price = ex_pos['entry_price']
                    current_price = ex_pos['current_price']
                    size_usdt = ex_pos['size']  # This might be in USDT or contracts
                    leverage = ex_pos['leverage']
                    
                    # Try to get quantity (might need adjustment based on MEXC API response)
                    quantity = size_usdt / entry_price if entry_price > 0 else 0
                    
                    trade_record = Trades(
                        id=trade_id,
                        mode='DEMO',
                        exchange='mexc',
                        symbol=symbol,
                        side='LONG' if ex_pos.get('side', '').upper() in ['BUY', 'LONG'] else 'SHORT',
                        status='open',
                        entry_price=entry_price,
                        current_price=current_price,
                        exit_price=None,
                        stop_loss=None,
                        take_profit=None,
                        leverage=leverage,
                        quantity=quantity,
                        pnl=ex_pos.get('unrealized_pnl', 0),
                        pnl_pct=0,
                        exchange_order_id=ex_pos.get('order_id', 'synced_from_exchange'),
                        strategy_name='MANUAL_RECOVERY',
                        regime='unknown',
                        confidence=None,
                        created_at=datetime.utcnow().isoformat(),
                        closed_at=None
                    )
                    db_session.add(trade_record)
                    await db_session.flush()
                    
                    # Create position record
                    position_record = Positions(
                        id=str(uuid.uuid4()),
                        trade_id=trade_id,
                        symbol=symbol,
                        size=quantity,
                        entry_price=entry_price,
                        current_price=current_price,
                        unrealized_pnl=ex_pos.get('unrealized_pnl', 0),
                        liquidation_price=ex_pos.get('liquidation_price'),
                        leverage=leverage,
                        status='open',
                        last_sync=datetime.utcnow().isoformat()
                    )
                    db_session.add(position_record)
                    await db_session.commit()
                    
                    print(f"✅ Position synced to database")
                    print(f"   Trade ID: {trade_id}")
                
                # Display position details
                print(f"\n📈 Position Details:")
                print(f"   Symbol: {symbol}")
                print(f"   Side: {ex_pos.get('side', 'LONG')}")
                print(f"   Entry Price: ${entry_price:,.2f}")
                print(f"   Current Price: ${current_price:,.2f}")
                print(f"   Unrealized PnL: ${ex_pos.get('unrealized_pnl', 0):,.2f}")
                print(f"   Leverage: {leverage}x")
                print(f"   Margin Ratio: {ex_pos.get('margin_ratio', 0):.2%}")
            
            break
        
        print(f"\n{'='*70}")
        print("✅ Sync completed successfully!")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await exchange.client.close()


async def main():
    """Main entry point."""
    await sync_mexc_positions()


if __name__ == "__main__":
    asyncio.run(main())
