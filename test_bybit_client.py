#!/usr/bin/env python3
"""Test BybitClient with Pybit SDK directly"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.infra.bybit_client import BybitClient

async def test_bybit_client():
    print("=" * 70)
    print("Testing BybitClient with Pybit SDK")
    print("=" * 70)
    
    try:
        # Initialize BybitClient with demo mode
        client = BybitClient(
            demo_trading=True
        )
        
        print("\n✅ BybitClient initialized successfully")
        print(f"   Using Pybit: {client.use_pybit}")
        print(f"   Demo Trading: {client.demo_trading}")
        print()
        
        # Test fetch_balance
        print("Testing fetch_balance()...")
        balance = await client.fetch_balance()
        print(f"   Total USDT: ${balance['total_usdt']:,.2f}")
        print(f"   Free USDT: ${balance['free_usdt']:,.2f}")
        print()
        
        # Test fetch_positions
        print("Testing fetch_positions()...")
        positions = await client.fetch_positions()
        print(f"   Open positions: {len(positions)}")
        if positions:
            for pos in positions:
                print(f"   - {pos['symbol']}: {pos['side']} {pos['size']}")
        print()
        
        # Test get_open_positions (alias)
        print("Testing get_open_positions()...")
        open_positions = await client.get_open_positions()
        print(f"   Open positions: {len(open_positions)}")
        print()
        
        print("=" * 70)
        print("✅ All BybitClient tests passed!")
        print("=" * 70)
        
        await client.close()
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bybit_client())
