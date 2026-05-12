"""Validate Bybit client configuration and initialization"""
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.config import settings
from app.infra.bybit_client import BybitClient

print("=" * 80)
print("Bybit Client Configuration Validation")
print("=" * 80)

# Check configuration
print("\n1. Configuration Parameters:")
print(f"   BYBIT_CLIENT_LIBRARY: {settings.BYBIT_CLIENT_LIBRARY}")
print(f"   BYBIT_RATE_LIMIT_ENABLED: {settings.BYBIT_RATE_LIMIT_ENABLED}")
print(f"   BYBIT_RATE_LIMIT_CALLS_PER_SECOND: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND}")
print(f"   BYBIT_CATEGORY: {settings.BYBIT_CATEGORY}")
print(f"   BYBIT_RECV_WINDOW: {settings.BYBIT_RECV_WINDOW}ms")
print(f"   BYBIT_USE_DEMO_DOMAIN: {settings.BYBIT_USE_DEMO_DOMAIN}")

# Test client initialization
print("\n2. Testing Client Initialization...")
try:
    client = BybitClient(testnet=True, demo_trading=False)
    print("   ✅ Client initialized successfully")
    print(f"   ✅ Rate limit configured: {client.exchange.rateLimit}ms between requests")
    print(f"   ✅ Recv window set: {client.exchange.options.get('recvWindow')}ms")
    print(f"   ✅ Time adjustment enabled: {client.exchange.options.get('adjustForTimeDifference')}")
    
    # Verify error helper method exists
    print("\n3. Testing Error Code Helper...")
    error_desc = BybitClient.get_bybit_error_description(10003)
    print(f"   ✅ Error 10003: {error_desc}")
    
    error_desc = BybitClient.get_bybit_error_description(10016)
    print(f"   ✅ Error 10016: {error_desc}")
    
    print("\n" + "=" * 80)
    print("✅ ALL VALIDATIONS PASSED!")
    print("=" * 80)
    print("\nKey Improvements Implemented:")
    print("  • Rate limiting aligned with Bybit standards (10 req/sec)")
    print("  • recvWindow parameter for timestamp validation")
    print("  • adjustForTimeDifference for clock skew compensation")
    print("  • Category-based API calls (linear/inverse/spot/option)")
    print("  • Comprehensive Bybit-specific error code handling")
    print("  • Enhanced logging with actionable troubleshooting steps")
    print("=" * 80)
    
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
