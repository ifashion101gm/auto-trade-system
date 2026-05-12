"""
Test Bybit API configuration for both LIVE and DEMO accounts.
Validates .env settings, credentials format, and connectivity.
"""
import asyncio
import sys
from app.config import settings
from app.infra.bybit_client import BybitClient


def check_env_configuration():
    """Check if all required environment variables are set."""
    print("=" * 80)
    print("Bybit API Configuration Check")
    print("=" * 80)
    
    print("\n1. Environment Variables Status:")
    
    # Live account credentials
    print("\n   LIVE Account:")
    if settings.BYBIT_API_KEY:
        masked_key = settings.BYBIT_API_KEY[:4] + "..." + settings.BYBIT_API_KEY[-4:]
        print(f"   ✓ BYBIT_API_KEY: {masked_key}")
    else:
        print(f"   ✗ BYBIT_API_KEY: NOT SET")
    
    if settings.BYBIT_API_SECRET:
        masked_secret = settings.BYBIT_API_SECRET[:4] + "..." + settings.BYBIT_API_SECRET[-4:]
        print(f"   ✓ BYBIT_API_SECRET: {masked_secret}")
    else:
        print(f"   ✗ BYBIT_API_SECRET: NOT SET")
    
    # Demo account credentials
    print("\n   DEMO Account:")
    if settings.BYBIT_DEMO_API_KEY:
        masked_key = settings.BYBIT_DEMO_API_KEY[:4] + "..." + settings.BYBIT_DEMO_API_KEY[-4:]
        print(f"   ✓ BYBIT_DEMO_API_KEY: {masked_key}")
    else:
        print(f"   ✗ BYBIT_DEMO_API_KEY: NOT SET")
    
    if settings.BYBIT_DEMO_API_SECRET:
        masked_secret = settings.BYBIT_DEMO_API_SECRET[:4] + "..." + settings.BYBIT_DEMO_API_SECRET[-4:]
        print(f"   ✓ BYBIT_DEMO_API_SECRET: {masked_secret}")
    else:
        print(f"   ✗ BYBIT_DEMO_API_SECRET: NOT SET")
    
    # Domain configuration
    print("\n   Domain Configuration:")
    print(f"   BYBIT_USE_DEMO_DOMAIN: {settings.BYBIT_USE_DEMO_DOMAIN}")
    if settings.BYBIT_USE_DEMO_DOMAIN:
        print(f"   → Currently configured for: DEMO (api-demo.bybit.com)")
    else:
        print(f"   → Currently configured for: LIVE (api.bybit.com)")
    
    return True


async def test_demo_account():
    """Test connection to Bybit DEMO account."""
    print("\n" + "=" * 80)
    print("Testing DEMO Account Connection")
    print("=" * 80)
    
    if not settings.BYBIT_DEMO_API_KEY or not settings.BYBIT_DEMO_API_SECRET:
        print("\n⚠️  Skipping DEMO test: Credentials not configured")
        return False
    
    try:
        print("\n1. Initializing BybitClient (DEMO mode)...")
        client = BybitClient(
            api_key=settings.BYBIT_DEMO_API_KEY,
            api_secret=settings.BYBIT_DEMO_API_SECRET,
            demo_trading=True
        )
        print("   ✅ Client initialized")
        print(f"   → Domain: https://api-demo.bybit.com")
        
        print("\n2. Testing balance fetch...")
        balance = await client.fetch_balance()
        total_usdt = balance.get('total_usdt', 0)
        print(f"   ✅ Balance fetched: ${total_usdt:.2f}")
        
        print("\n3. Testing ticker fetch...")
        ticker = await client.fetch_ticker('BTC/USDT:USDT')
        last_price = ticker.get('last_price', 0)
        print(f"   ✅ Ticker fetched: BTC/USDT = ${last_price:.2f}")
        
        print("\n4. Testing position fetch...")
        positions = await client.fetch_open_positions()
        print(f"   ✅ Positions fetched: {len(positions)} open")
        
        print("\n5. Testing order history...")
        try:
            orders = await client.fetch_order_history('BTC/USDT:USDT', limit=5)
            print(f"   ✅ Order history fetched: {len(orders)} orders")
        except Exception as e:
            print(f"   ⚠️  Order history: {e}")
        
        await client.close()
        
        print("\n✅ DEMO Account Test: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ DEMO Account Test: FAILED")
        print(f"   Error: {e}")
        print("\n   Common issues:")
        print("   - API keys must be generated FROM demo mode interface")
        print("   - Visit: https://www.bybit.com/en/trade/demo")
        print("   - Generate keys while in demo mode")
        return False


async def test_live_account():
    """Test connection to Bybit LIVE account."""
    print("\n" + "=" * 80)
    print("Testing LIVE Account Connection")
    print("=" * 80)
    
    if not settings.BYBIT_API_KEY or not settings.BYBIT_API_SECRET:
        print("\n⚠️  Skipping LIVE test: Credentials not configured")
        return False
    
    confirm = input("\n⚠️  WARNING: This will connect to LIVE trading environment!\n   Type 'YES' to continue: ")
    
    if confirm != 'YES':
        print("\n   LIVE test cancelled by user")
        return False
    
    try:
        print("\n1. Initializing BybitClient (LIVE mode)...")
        client = BybitClient(
            api_key=settings.BYBIT_API_KEY,
            api_secret=settings.BYBIT_API_SECRET,
            demo_trading=False
        )
        print("   ✅ Client initialized")
        print(f"   → Domain: https://api.bybit.com")
        print(f"   ⚠️  This is REAL MONEY environment!")
        
        print("\n2. Testing balance fetch...")
        balance = await client.fetch_balance()
        total_usdt = balance.get('total_usdt', 0)
        print(f"   ✅ Balance fetched: ${total_usdt:.2f}")
        
        print("\n3. Testing ticker fetch...")
        ticker = await client.fetch_ticker('BTC/USDT:USDT')
        last_price = ticker.get('last_price', 0)
        print(f"   ✅ Ticker fetched: BTC/USDT = ${last_price:.2f}")
        
        print("\n4. Testing position fetch...")
        positions = await client.fetch_open_positions()
        print(f"   ✅ Positions fetched: {len(positions)} open")
        
        await client.close()
        
        print("\n✅ LIVE Account Test: PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ LIVE Account Test: FAILED")
        print(f"   Error: {e}")
        return False


async def test_connector_integration():
    """Test BybitConnector with current .env settings."""
    print("\n" + "=" * 80)
    print("Testing BybitConnector Integration")
    print("=" * 80)
    
    try:
        from app.exchange.bybit_connector import BybitConnector
        
        print(f"\n1. Current configuration: {'DEMO' if settings.BYBIT_USE_DEMO_DOMAIN else 'LIVE'}")
        
        print("\n2. Initializing BybitConnector...")
        connector = BybitConnector(demo_trading=settings.BYBIT_USE_DEMO_DOMAIN)
        print(f"   ✅ Connector initialized")
        print(f"   Mode: {connector.mode}")
        print(f"   Demo Trading: {connector.demo_trading}")
        
        print("\n3. Testing connection...")
        connected = await connector.connect()
        
        if connected:
            print("   ✅ Connected successfully")
            
            print("\n4. Testing sync_state...")
            state = await connector.sync_state()
            print(f"   ✅ State synced")
            print(f"      Positions: {len(state['positions'])}")
            print(f"      Open Orders: {len(state['open_orders'])}")
            
            print("\n5. Checking WebSocket status...")
            print(f"   WS Connected: {connector.ws_manager.is_connected()}")
            print(f"   Active Streams: {len(connector.ws_manager.active_streams)}")
        else:
            print("   ⚠️  Connection failed (check credentials)")
        
        await connector.close()
        
        print("\n✅ Connector Integration Test: COMPLETED")
        return True
        
    except Exception as e:
        print(f"\n❌ Connector Integration Test: FAILED")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all configuration tests."""
    print("\n")
    
    # Check environment configuration
    check_env_configuration()
    
    # Test based on current configuration
    if settings.BYBIT_USE_DEMO_DOMAIN:
        print("\n→ Current mode is DEMO, testing demo account...")
        await test_demo_account()
    else:
        print("\n→ Current mode is LIVE, testing live account...")
        await test_live_account()
    
    # Test connector integration
    await test_connector_integration()
    
    print("\n" + "=" * 80)
    print("Configuration Summary")
    print("=" * 80)
    
    print("\nRequired .env variables:")
    print("  For DEMO trading:")
    print("    - BYBIT_DEMO_API_KEY (required)")
    print("    - BYBIT_DEMO_API_SECRET (required)")
    print("    - BYBIT_USE_DEMO_DOMAIN=true (required)")
    print("\n  For LIVE trading:")
    print("    - BYBIT_API_KEY (required)")
    print("    - BYBIT_API_SECRET (required)")
    print("    - BYBIT_USE_DEMO_DOMAIN=false (or omit)")
    
    print("\nImportant Notes:")
    print("  • DEMO keys MUST be generated from https://www.bybit.com/en/trade/demo")
    print("  • DEMO and LIVE keys are SEPARATE and NOT interchangeable")
    print("  • Symbol format for perpetual swaps: BTC/USDT:USDT (with :USDT suffix)")
    print("  • The system uses BYBIT_USE_DEMO_DOMAIN flag, NOT BYBIT_TESTNET")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
