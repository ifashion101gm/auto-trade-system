"""Quick test for Bybit Testnet API with new credentials"""
import asyncio
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.infra.bybit_client import BybitClient
from app.config import settings

print("=" * 80)
print("Testing BybitClient with new API credentials")
print("=" * 80)
print(f"API Key: {settings.BYBIT_DEMO_API_KEY}")
print(f"Secret Length: {len(settings.BYBIT_DEMO_API_SECRET)}")
print(f"BYBIT_USE_DEMO_DOMAIN: {settings.BYBIT_USE_DEMO_DOMAIN}")
print()

async def test():
    client = BybitClient(testnet=True, demo_trading=False)
    
    try:
        print("1. Testing fetch_balance...")
        balance = await client.fetch_balance()
        usdt = balance['total_usdt']
        print(f"   SUCCESS! USDT Balance: {usdt}")
        
        print("\n2. Testing fetch_ticker...")
        ticker = await client.fetch_ticker("BTC/USDT:USDT")
        print(f"   SUCCESS! BTC Price: {ticker['last_price']}")
        
        print("\n3. Testing positions...")
        positions = await client.fetch_open_positions()
        print(f"   SUCCESS! Open positions: {len(positions)}")
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED! Bybit Testnet is working!")
        print("=" * 80)
        return True
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()

result = asyncio.run(test())
sys.exit(0 if result else 1)
