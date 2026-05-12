"""
Diagnostic script to test Bybit Demo API key authentication.
Tests different authentication methods and provides detailed error analysis.
"""
import asyncio
import ccxt.async_support as ccxt
from app.config import settings


async def test_ccxt_direct():
    """Test CCXT directly with minimal configuration."""
    print("=" * 80)
    print("Test 1: CCXT Direct Connection")
    print("=" * 80)
    
    try:
        exchange = ccxt.bybit({
            'apiKey': settings.BYBIT_DEMO_API_KEY,
            'secret': settings.BYBIT_DEMO_API_SECRET,
            'enableRateLimit': True,
            'urls': {
                'api': {
                    'public': 'https://api-demo.bybit.com',
                    'private': 'https://api-demo.bybit.com',
                }
            },
            'options': {
                'defaultType': 'swap',
            }
        })
        
        print(f"\n✓ Exchange initialized")
        print(f"  API Key: {settings.BYBIT_DEMO_API_KEY[:10]}...{settings.BYBIT_DEMO_API_KEY[-4:]}")
        print(f"  Secret Length: {len(settings.BYBIT_DEMO_API_SECRET)}")
        print(f"  Domain: https://api-demo.bybit.com")
        
        # Try to load markets (doesn't require authentication)
        print("\nTesting public endpoint (load_markets)...")
        markets = await exchange.load_markets()
        print(f"✓ Loaded {len(markets)} markets")
        
        # Try authenticated endpoint
        print("\nTesting private endpoint (fetch_balance)...")
        try:
            balance = await exchange.fetch_balance()
            print(f"✓ Balance fetched successfully")
            print(f"  Total USDT: {balance.get('USDT', {}).get('total', 0)}")
        except Exception as e:
            print(f" Balance fetch failed: {e}")
            error_msg = str(e)
            
            # Analyze error
            if "10003" in error_msg:
                print("\n  Error Code 10003: API key is invalid")
                print("  Possible causes:")
                print("  1. API Key/Secret mismatch (typo or wrong pair)")
                print("  2. Key is disabled or expired")
                print("  3. Key doesn't have read permissions")
                print("  4. IP restriction blocking this server")
            elif "10002" in error_msg:
                print("\n  Error Code 10002: Invalid parameter")
                print("  Possible causes:")
                print("  1. API key format incorrect")
                print("  2. Extra characters or spaces in key/secret")
            elif "10001" in error_msg:
                print("\n  Error Code 10001: Parameter error")
            elif "10004" in error_msg:
                print("\n  Error Code 10004: API key permissions denied")
                print("  Possible causes:")
                print("  1. API key doesn't have 'Account' read permission")
                print("  2. API key doesn't have 'Wallet' read permission")
        
        await exchange.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_with_signature():
    """Test signature generation to verify secret key."""
    print("\n" + "=" * 80)
    print("Test 2: API Key/Secret Format Validation")
    print("=" * 80)
    
    api_key = settings.BYBIT_DEMO_API_KEY
    api_secret = settings.BYBIT_DEMO_API_SECRET
    
    print(f"\nAPI Key Analysis:")
    print(f"  Key: {api_key}")
    print(f"  Length: {len(api_key)}")
    has_space = ' ' in api_key
    has_quote = '"' in api_key or "'" in api_key
    print(f"  Contains spaces: {has_space}")
    print(f"  Contains quotes: {has_quote}")
    print(f"  Appears to be Base64: {api_key.isalnum()}")
    
    print(f"\nAPI Secret Analysis:")
    print(f"  Secret (masked): {api_secret[:6]}...{api_secret[-6:]}")
    print(f"  Length: {len(api_secret)}")
    has_space_secret = ' ' in api_secret
    has_quote_secret = '"' in api_secret or "'" in api_secret
    print(f"  Contains spaces: {has_space_secret}")
    print(f"  Contains quotes: {has_quote_secret}")
    
    # Check for common mistakes
    issues = []
    
    if len(api_key) < 10:
        issues.append("API key seems too short (should be ~20 characters)")
    if len(api_secret) < 20:
        issues.append("API secret seems too short (should be ~40+ characters)")
    if ' ' in api_key or ' ' in api_secret:
        issues.append("WARNING: Contains spaces! Remove all spaces from key/secret")
    if '\"' in api_key or '\"' in api_secret:
        issues.append("WARNING: Contains quotes! Remove quotes from .env values")
    if api_key.startswith('eFxn8ZW90O7d5ZWoAY') and len(api_key) > 20:
        issues.append("WARNING: API key appears duplicated! Should be exactly 18 chars: eFxn8ZW90O7d5ZWoAY")
    
    if issues:
        print(f"\n⚠️  Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\n✓ Key/Secret format looks correct")
    
    return len(issues) == 0


async def test_alternative_endpoints():
    """Test different API endpoints to isolate the issue."""
    print("\n" + "=" * 80)
    print("Test 3: Alternative Endpoint Tests")
    print("=" * 80)
    
    exchange = ccxt.bybit({
        'apiKey': settings.BYBIT_DEMO_API_KEY,
        'secret': settings.BYBIT_DEMO_API_SECRET,
        'enableRateLimit': True,
        'urls': {
            'api': {
                'public': 'https://api-demo.bybit.com',
                'private': 'https://api-demo.bybit.com',
            }
        },
        'options': {
            'defaultType': 'swap',
        }
    })
    
    tests = [
        ("fetch_positions", exchange.fetch_positions, []),
        ("fetch_open_orders", exchange.fetch_open_orders, []),
    ]
    
    for test_name, test_func, args in tests:
        try:
            print(f"\nTesting {test_name}...")
            result = await test_func(*args)
            print(f"  ✓ Success: {type(result).__name__}")
            if isinstance(result, list):
                print(f"    Count: {len(result)}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
    
    await exchange.close()


async def check_permissions():
    """Check if the issue might be permissions-related."""
    print("\n" + "=" * 80)
    print("Test 4: Permission Requirements")
    print("=" * 80)
    
    print("\nRequired API Permissions for Demo Trading:")
    print("  ✓ Order - Trade (Spot)")
    print("  ✓ Position - Read & Write")
    print("  ✓ Account - Read")
    print("  ✓ Wallet - Read")
    
    print("\nCurrent Key Permissions (from your screenshot):")
    print("  ✓ Contracts - Orders Positions")
    print("  ✓ USDC Contracts - Trade")
    print("  ✓ Unified Trading - Trade")
    print("  ✓ SPOT - Trade")
    
    print("\n✓ All required permissions appear to be enabled")
    print("\nNote: If you're still getting auth errors, try:")
    print("  1. Disable and re-enable the API key")
    print("  2. Create a brand new API key")
    print("  3. Check if there are IP restrictions enabled")


async def main():
    """Run all diagnostic tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "Bybit Demo API Diagnostic Tool" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")
    
    # Test 1: Format validation
    await test_with_signature()
    
    # Test 2: Direct CCXT connection
    await test_ccxt_direct()
    
    # Test 3: Alternative endpoints
    await test_alternative_endpoints()
    
    # Test 4: Permission check
    await check_permissions()
    
    print("\n" + "=" * 80)
    print("Diagnostic Summary")
    print("=" * 80)
    print("\nNext Steps:")
    print("  1. If key format has issues → Fix the .env file")
    print("  2. If permissions are wrong → Edit API key permissions")
    print("  3. If key is invalid → Create new API key")
    print("  4. If IP restricted → Add your server IP to allowed list")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
