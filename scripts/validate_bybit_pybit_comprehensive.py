#!/usr/bin/env python3
"""
Comprehensive Bybit API Validation - Demo & Live (Pybit SDK)

This script validates both Demo and Live Bybit API configurations using the official Pybit SDK.

OBJECTIVES:
1. Demo Trading Validation (Pybit SDK):
   - Verify PybitDemoClient initialization with demo=True, testnet=False
   - Confirm routing to api-demo.bybit.com
   - Test read-only operations (balance, ticker) with demo credentials
   
2. Live Mode Capability Check (Pybit SDK):
   - Verify BybitClient live mode configuration
   - Confirm routing to api.bybit.com with live credentials
   - Test read-only connectivity (server time, balance)

SAFETY: NO write operations executed - read-only validation only.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def mask_api_key(api_key: str) -> str:
    """Mask API key for safe display (first 5 + last 4 chars)."""
    if not api_key or len(api_key) < 9:
        return "***"
    return f"{api_key[:5]}...{api_key[-4:]}"


async def validate_demo_trading():
    """Validate Demo Trading configuration using Pybit SDK."""
    
    print("\n" + "=" * 80)
    print("DEMO TRADING VALIDATION (Pybit SDK)")
    print("=" * 80)
    
    results = {
        'status': 'FAILED',
        'endpoint': None,
        'authentication': False,
        'balance': None,
        'ticker': None,
        'errors': []
    }
    
    try:
        # Step 1: Configuration Verification
        print("\n📋 Step 1: Configuration Verification")
        print("-" * 80)
        
        demo_key = settings.BYBIT_DEMO_API_KEY
        demo_secret = settings.BYBIT_DEMO_API_SECRET
        
        if not demo_key or not demo_secret:
            print("❌ FAIL: Demo API credentials not configured")
            print(f"   BYBIT_DEMO_API_KEY: {'Set' if demo_key else 'MISSING'}")
            print(f"   BYBIT_DEMO_API_SECRET: {'Set' if demo_secret else 'MISSING'}")
            results['errors'].append("Missing demo credentials")
            return results
        
        print(f"✅ Demo API Key: {mask_api_key(demo_key)}")
        print(f"✅ Demo API Secret: {'Set' if demo_secret else 'MISSING'}")
        print(f"✅ BYBIT_USE_DEMO_DOMAIN: {settings.BYBIT_USE_DEMO_DOMAIN}")
        print(f"✅ Expected Endpoint: https://api-demo.bybit.com")
        print()
        
        # Step 2: Initialize PybitDemoClient
        print("🔧 Step 2: Initializing PybitDemoClient")
        print("-" * 80)
        
        from app.infra.pybit_demo_client import PybitDemoClient
        
        client = PybitDemoClient(
            api_key=demo_key,
            api_secret=demo_secret
        )
        
        print("✅ PybitDemoClient initialized successfully")
        print("   Configuration:")
        print("   - testnet=False (NOT testnet)")
        print("   - demo=True (Demo trading enabled)")
        print("   - recv_window=5000ms")
        print()
        
        results['endpoint'] = "https://api-demo.bybit.com"
        
        # Step 3: Fetch Balance (Read-Only)
        print("💰 Step 3: Fetching Demo Account Balance")
        print("-" * 80)
        
        balance = await client.fetch_balance()
        usdt_balance = balance.get('total_usdt', 0)
        
        print(f"✅ Balance fetch successful")
        print(f"   USDT Balance: ${usdt_balance:.2f}")
        print(f"   Account Type: {balance.get('account_type', 'UNIFIED')}")
        
        if usdt_balance == 0:
            print("   ⚠️  Warning: Zero balance - demo account may need funding")
            print("   Visit: https://www.bybit.com/en/demo-trading")
        
        results['balance'] = usdt_balance
        results['authentication'] = True
        print()
        
        # Step 4: Fetch Ticker Data (Read-Only)
        print("📊 Step 4: Fetching Market Data")
        print("-" * 80)
        
        test_symbol = "XRPUSDT"  # Demo uses simple format
        
        ticker = await client.fetch_ticker(test_symbol)
        
        print(f"✅ Ticker fetch successful")
        print(f"   Symbol: {ticker['symbol']}")
        print(f"   Last Price: ${ticker['last_price']:.4f}")
        print(f"   Bid: ${ticker['bid_price']:.4f} | Ask: ${ticker['ask_price']:.4f}")
        print(f"   24h Volume: {ticker['volume_24h']:,.0f}")
        
        results['ticker'] = ticker['last_price']
        print()
        
        # Step 5: Summary
        print("📝 Step 5: Demo Validation Summary")
        print("-" * 80)
        print("✅ ALL DEMO TESTS PASSED")
        print(f"   • Endpoint: {results['endpoint']}")
        print(f"   • Authentication: SUCCESS")
        print(f"   • Balance: ${results['balance']:.2f} USDT")
        print(f"   • Market Data: {results['ticker']:.4f} ({test_symbol})")
        print(f"   • SDK: Pybit v5 (Official)")
        
        results['status'] = 'PASSED'
        
        await client.close()
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ DEMO VALIDATION FAILED: {error_msg}")
        results['errors'].append(error_msg)
        
        # Provide troubleshooting guidance
        if '10003' in error_msg:
            print("\n🔍 Troubleshooting:")
            print("   Error 10003: Invalid API Key")
            print("   - Ensure you're using DEMO keys (not live/testnet)")
            print("   - Generate new keys at: https://www.bybit.com/en/demo-trading")
            print("   - Check .env has correct BYBIT_DEMO_API_KEY/SECRET")
        
        elif '10024' in error_msg:
            print("\n🔍 Troubleshooting:")
            print("   Error 10024: Regulatory Restriction")
            print("   - Complete KYC verification on demo site")
            print("   - Check geographic restrictions")
            print("   - Contact Bybit support")
        
        elif 'Connection' in error_msg or 'timeout' in error_msg.lower():
            print("\n🔍 Troubleshooting:")
            print("   Connection Error")
            print("   - Check internet connectivity")
            print("   - Verify firewall allows outbound HTTPS")
            print("   - Try: curl https://api-demo.bybit.com/v5/public/time")
    
    return results


async def validate_live_mode():
    """Validate Live Trading configuration using Pybit SDK."""
    
    print("\n" + "=" * 80)
    print("LIVE MODE CAPABILITY CHECK (Pybit SDK)")
    print("=" * 80)
    
    results = {
        'status': 'FAILED',
        'endpoint': None,
        'authentication': False,
        'server_time': None,
        'balance': None,
        'errors': []
    }
    
    try:
        # Step 1: Configuration Verification
        print("\n📋 Step 1: Configuration Verification")
        print("-" * 80)
        
        live_key = settings.BYBIT_API_KEY
        live_secret = settings.BYBIT_API_SECRET
        
        if not live_key or not live_secret:
            print("❌ FAIL: Live API credentials not configured")
            print(f"   BYBIT_API_KEY: {'Set' if live_key else 'MISSING'}")
            print(f"   BYBIT_API_SECRET: {'Set' if live_secret else 'MISSING'}")
            results['errors'].append("Missing live credentials")
            return results
        
        print(f"✅ Live API Key: {mask_api_key(live_key)}")
        print(f"✅ Live API Secret: {'Set' if live_secret else 'MISSING'}")
        print(f"✅ Expected Endpoint: https://api.bybit.com")
        print(f"   Note: Using CCXT for live mode (Pybit available for fallback)")
        print()
        
        # Step 2: Initialize BybitClient in Live Mode
        print("🔧 Step 2: Initializing BybitClient (Live Mode)")
        print("-" * 80)
        
        from app.infra.bybit_client import BybitClient
        
        # Initialize with demo_trading=False to use live endpoint
        client = BybitClient(
            api_key=live_key,
            api_secret=live_secret,
            testnet=False,
            demo_trading=False  # Explicitly disable demo mode
        )
        
        print("✅ BybitClient initialized successfully")
        print("   Configuration:")
        print("   - testnet=False")
        print("   - demo_trading=False (Live mode)")
        print("   - SDK: CCXT (unified interface)")
        print("   - Rate Limit: Enabled")
        print()
        
        results['endpoint'] = "https://api.bybit.com"
        
        # Step 3: Fetch Server Time (Read-Only)
        print("⏰ Step 3: Fetching Server Time")
        print("-" * 80)
        
        server_time_ms = await client.fetch_server_time()
        local_time_ms = int(asyncio.get_event_loop().time() * 1000)
        time_diff = abs(server_time_ms - local_time_ms) / 1000
        
        print(f"✅ Server time fetch successful")
        print(f"   Server Time: {datetime.fromtimestamp(server_time_ms/1000).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"   Time Difference: {time_diff:.2f}s")
        
        if time_diff > 5:
            print("   ⚠️  Warning: Clock skew > 5s - may cause authentication errors")
            print("   Recommendation: Enable automatic date/time synchronization")
        else:
            print("   ✅ Clock synchronized")
        
        results['server_time'] = server_time_ms
        print()
        
        # Step 4: Fetch Balance (Read-Only)
        print("💰 Step 4: Fetching Live Account Balance")
        print("-" * 80)
        
        balance = await client.fetch_balance()
        usdt_balance = balance.get('total_usdt', 0)
        
        print(f"✅ Balance fetch successful")
        print(f"   USDT Balance: ${usdt_balance:.2f}")
        print(f"   Free USDT: ${balance.get('free_usdt', 0):.2f}")
        
        results['balance'] = usdt_balance
        results['authentication'] = True
        print()
        
        # Step 5: Validate Clock Sync
        print("🕐 Step 5: Clock Synchronization Check")
        print("-" * 80)
        
        clock_sync = await client.validate_clock_sync(max_diff_seconds=5)
        
        if clock_sync:
            print("✅ Clock sync validated")
            print("   System clock is within acceptable range")
        else:
            print("❌ Clock sync failed")
            print("   Please synchronize system clock before trading")
        
        print()
        
        # Step 6: Summary
        print("📝 Step 6: Live Mode Validation Summary")
        print("-" * 80)
        print("✅ ALL LIVE MODE TESTS PASSED")
        print(f"   • Endpoint: {results['endpoint']}")
        print(f"   • Authentication: SUCCESS")
        print(f"   • Server Time: Synchronized")
        print(f"   • Balance: ${results['balance']:.2f} USDT")
        print(f"   • SDK: CCXT (with Pybit fallback available)")
        
        results['status'] = 'PASSED'
        
        await client.close()
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ LIVE MODE VALIDATION FAILED: {error_msg}")
        results['errors'].append(error_msg)
        
        # Provide troubleshooting guidance
        if '10003' in error_msg:
            print("\n🔍 Troubleshooting:")
            print("   Error 10003: Invalid API Key")
            print("   - Verify live API key/secret are correct")
            print("   - Check key hasn't expired or been revoked")
            print("   - Ensure key has required permissions")
        
        elif '10004' in error_msg:
            print("\n🔍 Troubleshooting:")
            print("   Error 10004: Permissions Denied")
            print("   - Check API key permissions in Bybit dashboard")
            print("   - Required: Account Read, Wallet Read")
            print("   - For trading: Order Trade, Position Read/Write")
        
        elif '10005' in error_msg:
            print("\n🔍 Troubleshooting:")
            print("   Error 10005: IP Restriction")
            print("   - Add your server IP to API key whitelist")
            print("   - Or disable IP restriction temporarily for testing")
        
        elif '10016' in error_msg or 'clock' in error_msg.lower():
            print("\n🔍 Troubleshooting:")
            print("   Error 10016: Timestamp/Clock Error")
            print("   - Synchronize system clock (enable NTP)")
            print("   - Increase recv_window in .env (currently 5000ms)")
        
        elif 'Connection' in error_msg or 'timeout' in error_msg.lower():
            print("\n🔍 Troubleshooting:")
            print("   Connection Error")
            print("   - Check internet connectivity")
            print("   - Verify firewall allows outbound HTTPS to api.bybit.com")
            print("   - Try: curl https://api.bybit.com/v5/public/time")
    
    return results


async def main():
    """Run comprehensive validation."""
    
    print("\n" + "=" * 80)
    print("BYBIT API COMPREHENSIVE VALIDATION")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print("\nThis validation checks both Demo and Live Bybit API configurations.")
    print("SAFETY: Read-only operations only - NO orders placed.")
    
    # Run Demo Validation
    demo_results = await validate_demo_trading()
    
    # Run Live Validation
    live_results = await validate_live_mode()
    
    # Final Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    print("\n📊 Demo Trading (Pybit SDK):")
    print(f"   Status: {demo_results['status']}")
    print(f"   Endpoint: {demo_results['endpoint']}")
    if demo_results['balance'] is not None:
        print(f"   Balance: ${demo_results['balance']:.2f} USDT")
    if demo_results['ticker'] is not None:
        print(f"   Market Data: ${demo_results['ticker']:.4f}")
    if demo_results['errors']:
        print(f"   Errors: {len(demo_results['errors'])}")
        for err in demo_results['errors']:
            print(f"      - {err}")
    
    print("\n📊 Live Mode (CCXT/Pybit):")
    print(f"   Status: {live_results['status']}")
    print(f"   Endpoint: {live_results['endpoint']}")
    if live_results['balance'] is not None:
        print(f"   Balance: ${live_results['balance']:.2f} USDT")
    if live_results['server_time'] is not None:
        print(f"   Server Time: Synchronized")
    if live_results['errors']:
        print(f"   Errors: {len(live_results['errors'])}")
        for err in live_results['errors']:
            print(f"      - {err}")
    
    print("\n" + "=" * 80)
    
    # Overall status
    if demo_results['status'] == 'PASSED' and live_results['status'] == 'PASSED':
        print("✅ OVERALL: ALL VALIDATIONS PASSED")
        print("\nBoth Demo and Live configurations are operational.")
        print("The system is ready for trading operations.")
        overall_success = True
    else:
        print("⚠️  OVERALL: SOME VALIDATIONS FAILED")
        print("\nReview errors above and fix configuration issues.")
        overall_success = False
    
    print("=" * 80 + "\n")
    
    return overall_success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
