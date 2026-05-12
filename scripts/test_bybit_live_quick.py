#!/usr/bin/env python3
"""
Quick Bybit Live API Connection Test.
Simple connectivity and authentication check.
"""
import asyncio
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.bybit_client import BybitClient


async def quick_test():
    """Quick test of live API connection."""
    client = None
    
    try:
        print("Testing Bybit LIVE API connection...")
        print(f"Endpoint: https://api.bybit.com")
        print(f"API Key: {settings.BYBIT_API_KEY[:8]}...{settings.BYBIT_API_KEY[-4:]}" if hasattr(settings, 'BYBIT_API_KEY') else "N/A")
        
        # Initialize client
        start_time = time.time()
        client = BybitClient(testnet=False, demo_trading=False)
        init_time = time.time() - start_time
        print(f"✅ Client initialized in {init_time:.2f}s")
        
        # Test 1: Fetch ticker (public endpoint - no auth required)
        print("\nTest 1: Public market data...")
        start_time = time.time()
        try:
            ticker = await client.fetch_ticker("BTCUSDT")
            elapsed = time.time() - start_time
            print(f"✅ BTC/USDT: ${ticker['last_price']:.2f} ({elapsed:.2f}s)")
        except Exception as e:
            print(f"❌ Failed: {e}")
            return False
        
        # Test 2: Fetch balance (private endpoint - requires auth)
        print("\nTest 2: Private balance query...")
        start_time = time.time()
        try:
            balance = await client.fetch_balance()
            elapsed = time.time() - start_time
            usdt = balance.get('total_usdt', 0)
            
            if usdt == 0:
                print(f"✅ Balance: {usdt:.2f} USDT ({elapsed:.2f}s) - Account empty (OK for testing)")
            else:
                print(f"✅ Balance: {usdt:.2f} USDT ({elapsed:.2f}s)")
        except Exception as e:
            print(f"❌ Failed: {e}")
            error_msg = str(e)
            
            if 'retCode' in error_msg:
                import re
                match = re.search(r'retCode["\s]*:\s*(\d+)', error_msg)
                if match:
                    ret_code = match.group(1)
                    desc = BybitClient.get_bybit_error_description(int(ret_code))
                    print(f"   Error Code: {ret_code}")
                    print(f"   Description: {desc}")
            return False
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - Live API connection working!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if client:
            await client.close()


if __name__ == "__main__":
    from app.config import settings
    success = asyncio.run(quick_test())
    sys.exit(0 if success else 1)
