"""
Quick test to verify Bybit API access with current .env credentials.
"""
import asyncio
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.infra.bybit_client import BybitClient
from app.config import settings


async def test_bybit_api_access():
    """Test Bybit API access with current credentials."""
    
    print("\n" + "="*80)
    print("  BYBIT API ACCESS TEST")
    print("="*80)
    
    print(f"\n📋 Configuration from .env:")
    print(f"   • API Key: {settings.BYBIT_API_KEY[:10]}...{settings.BYBIT_API_KEY[-4:] if settings.BYBIT_API_KEY else 'NOT SET'}")
    print(f"   • API Secret: {'***' + settings.BYBIT_API_SECRET[-4:] if settings.BYBIT_API_SECRET else 'NOT SET'}")
    print(f"   • BYBIT_TESTNET env var: Not used by application")
    print()
    
    # Test 1: Connect with testnet=False (mainnet/demo trading)
    print("[TEST 1] Connecting to Mainnet API (for Demo Trading)")
    print("-" * 80)
    try:
        client = BybitClient(testnet=False)
        print("✅ Client initialized successfully")
        
        # Fetch balance
        balance = await client.fetch_balance()
        print(f"✅ Balance query successful")
        print(f"   • USDT Total: ${balance['total_usdt']:,.2f}")
        print(f"   • USDT Free: ${balance['free_usdt']:,.2f}")
        print(f"   • USDT Used: ${balance['used_usdt']:,.2f}")
        
        # Fetch market data
        print("\n[TEST 2] Fetching Market Data")
        print("-" * 80)
        ticker = await client.fetch_ticker('XAG/USDT:USDT')
        print(f"✅ XAG/USDT:USDT (Silver Perpetual)")
        print(f"   • Price: ${ticker['last_price']:,.2f}")
        print(f"   • Bid: ${ticker['bid']:,.2f}")
        print(f"   • Ask: ${ticker['ask']:,.2f}")
        print(f"   • 24h Volume: ${ticker['volume_24h']:,.2f}")
        
        await client.close()
        
        print("\n" + "="*80)
        print("  RESULT SUMMARY")
        print("="*80)
        
        if balance['total_usdt'] == 0:
            print("\n⚠️  Balance is $0.00")
            print("\nThis indicates:")
            print("  • API keys are VALID (authentication works)")
            print("  • But account has NO FUNDS")
            print("  • Keys likely belong to empty/live account, not demo account")
            print("\nNext Steps:")
            print("  1. Log into https://www.bybit.com/en/trade/demo")
            print("  2. Verify 'DEMO' badge is visible")
            print("  3. Generate NEW API keys while in demo mode")
            print("  4. Update .env with new credentials")
        else:
            print(f"\n✅ SUCCESS! Account has ${balance['total_usdt']:,.2f}")
            print("   API keys are working correctly with funds available!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        print("\n" + "="*80)
        print("  TROUBLESHOOTING")
        print("="*80)
        print("\nPossible issues:")
        print("  1. Invalid API credentials")
        print("  2. API keys don't have proper permissions")
        print("  3. Network connectivity issues")
        print("  4. Bybit API rate limiting")


if __name__ == "__main__":
    asyncio.run(test_bybit_api_access())
