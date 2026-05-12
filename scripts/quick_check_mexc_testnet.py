#!/usr/bin/env python3
"""
Quick check of MEXC testnet for open positions.
This is a lightweight version that just checks the API.
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infra.mexc_client import MEXCClient
from app.config import settings


async def main():
    """Check MEXC testnet for open positions."""
    print("\n" + "="*80)
    print("QUICK MEXC TESTNET POSITION CHECK")
    print("="*80)
    
    if not settings.MEXC_API_KEY or not settings.MEXC_API_SECRET:
        print("❌ MEXC API credentials not configured")
        return False
    
    try:
        print("\n🔌 Connecting to MEXC Futures Testnet...")
        mexc = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures',
            testnet=True
        )
        
        print("💰 Fetching balance...")
        balance = await mexc.fetch_balance()
        print(f"   Total: ${balance.get('total_usdt', 0):,.2f}")
        print(f"   Free: ${balance.get('free_usdt', 0):,.2f}")
        
        print("\n📈 Fetching open positions...")
        positions = await mexc.fetch_open_positions()
        
        print(f"\n✅ Found {len(positions)} open position(s):\n")
        
        if not positions:
            print("   No open positions on MEXC testnet")
        else:
            for i, pos in enumerate(positions, 1):
                print(f"   Position #{i}:")
                print(f"      Symbol: {pos['symbol']}")
                print(f"      Side: {pos['side'].upper()}")
                print(f"      Size: {pos['size']}")
                if pos.get('entry_price'):
                    print(f"      Entry: ${pos['entry_price']:,.2f}")
                if pos.get('mark_price'):
                    print(f"      Mark: ${pos['mark_price']:,.2f}")
                if pos.get('unrealized_pnl') is not None:
                    print(f"      P&L: ${pos['unrealized_pnl']:+.2f}")
                if pos.get('leverage'):
                    print(f"      Leverage: {pos['leverage']}x")
                print("")
        
        await mexc.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
