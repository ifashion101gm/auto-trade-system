#!/usr/bin/env python3
"""
Quick Bybit API Validation - Demo & Live (Pybit SDK)

Fast read-only validation of both Demo and Live configurations.
SAFETY: No write operations - authentication and connectivity only.
"""
import asyncio
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def mask_key(key):
    """Mask API key for display."""
    if not key or len(key) < 9:
        return "***"
    return f"{key[:5]}...{key[-4:]}"


async def test_demo():
    """Test Demo Trading with PybitDemoClient."""
    print("\n" + "="*80)
    print("DEMO TRADING VALIDATION (Pybit SDK)")
    print("="*80)
    
    try:
        from app.infra.pybit_demo_client import PybitDemoClient
        
        # Check credentials
        demo_key = settings.BYBIT_DEMO_API_KEY
        demo_secret = settings.BYBIT_DEMO_API_SECRET
        
        if not demo_key or not demo_secret:
            print("❌ FAIL: Demo credentials missing")
            return False
        
        print(f"\n✅ Credentials: {mask_key(demo_key)}")
        print(f"✅ Endpoint: https://api-demo.bybit.com")
        
        # Initialize client
        print("\n🔧 Initializing PybitDemoClient...")
        client = PybitDemoClient(api_key=demo_key, api_secret=demo_secret)
        print("✅ Client initialized (testnet=False, demo=True)")
        
        # Fetch balance
        print("\n💰 Fetching balance...")
        balance = await client.fetch_balance()
        usdt = balance.get('total_usdt', 0)
        print(f"✅ Balance: ${usdt:.2f} USDT")
        
        # Fetch ticker
        print("\n📊 Fetching market data...")
        ticker = await client.fetch_ticker("XRPUSDT")
        print(f"✅ XRP/USDT: ${ticker['last_price']:.4f}")
        
        await client.close()
        
        print("\n✅ DEMO VALIDATION: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ DEMO VALIDATION FAILED: {e}")
        return False


async def test_live():
    """Test Live Mode with BybitClient."""
    print("\n" + "="*80)
    print("LIVE MODE VALIDATION (CCXT)")
    print("="*80)
    
    try:
        from app.infra.bybit_client import BybitClient
        
        # Check credentials
        live_key = settings.BYBIT_API_KEY
        live_secret = settings.BYBIT_API_SECRET
        
        if not live_key or not live_secret:
            print("❌ FAIL: Live credentials missing")
            return False
        
        print(f"\n✅ Credentials: {mask_key(live_key)}")
        print(f"✅ Endpoint: https://api.bybit.com")
        
        # Initialize client
        print("\n🔧 Initializing BybitClient (live mode)...")
        client = BybitClient(
            api_key=live_key,
            api_secret=live_secret,
            testnet=False,
            demo_trading=False
        )
        print("✅ Client initialized (testnet=False, demo_trading=False)")
        
        # Fetch server time
        print("\n⏰ Fetching server time...")
        start = time.time()
        server_time = await client.fetch_server_time()
        local_time = int(time.time() * 1000)
        elapsed = time.time() - start
        
        diff_seconds = abs(server_time - local_time) / 1000
        print(f"✅ Server time: {elapsed*1000:.0f}ms latency")
        print(f"   Clock difference: {diff_seconds:.2f}s")
        
        if diff_seconds > 5:
            print("   ⚠️  Warning: Clock skew detected")
        else:
            print("   ✅ Clock synchronized")
        
        # Test public endpoint (fast)
        print("\n📊 Testing public API...")
        ticker = await client.exchange.fetch_ticker('BTC/USDT:USDT')
        print(f"✅ BTC/USDT: ${ticker['last']:.2f}")
        
        await client.close()
        
        print("\n✅ LIVE MODE VALIDATION: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ LIVE MODE VALIDATION FAILED: {e}")
        return False


async def main():
    """Run both validations."""
    print("\n" + "="*80)
    print("BYBIT API VALIDATION - QUICK CHECK")
    print("SAFETY: Read-only tests only")
    print("="*80)
    
    # Test Demo
    demo_ok = await test_demo()
    
    # Test Live
    live_ok = await test_live()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Demo Trading: {'✅ PASSED' if demo_ok else '❌ FAILED'}")
    print(f"Live Mode:    {'✅ PASSED' if live_ok else '❌ FAILED'}")
    
    if demo_ok and live_ok:
        print("\n✅ ALL VALIDATIONS PASSED")
        print("Both Demo and Live configurations are operational.")
    else:
        print("\n⚠️  Some validations failed - check errors above")
    
    print("="*80 + "\n")
    
    return demo_ok and live_ok


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(130)
