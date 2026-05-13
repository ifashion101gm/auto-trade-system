"""
Diagnostic script to check Bybit Demo API permissions and connectivity.
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def check_bybit_demo_api():
    """Test Bybit Demo API connectivity and permissions."""
    from app.infra.bybit_client import BybitClient
    
    print("=" * 70)
    print("BYBIT DEMO API PERMISSION CHECK")
    print("=" * 70)
    
    # Check configuration
    print("\n📋 Configuration:")
    print(f"  BYBIT_USE_DEMO_DOMAIN: {os.getenv('BYBIT_USE_DEMO_DOMAIN', 'NOT SET')}")
    print(f"  BYBIT_DEMO_API_KEY: {os.getenv('BYBIT_DEMO_API_KEY', 'NOT SET')[:20]}...")
    print(f"  BYBIT_DEMO_API_SECRET: {'***' + os.getenv('BYBIT_DEMO_API_SECRET', 'NOT SET')[-8:]}")
    
    client = BybitClient(demo_trading=True)
    
    try:
        print("\n🔄 Attempting to connect to Bybit Demo API...")
        print(f"   Base URL: {client.exchange.urls['api']['private']}")
        
        # Test 1: Check server time (no auth required)
        print("\n✅ Test 1: Server Connectivity")
        try:
            time_data = await client.fetch_server_time()
            print(f"   Server Time: {time_data}")
            print("   ✅ Server connection successful")
        except Exception as e:
            print(f"   ❌ Server connection failed: {e}")
            return
        
        # Test 2: Fetch balance (requires authentication)
        print("\n✅ Test 2: Balance Check (Authentication Test)")
        try:
            balance = await client.fetch_balance()
            total_usdt = float(balance.get('total_usdt', 0))
            free_usdt = float(balance.get('free_usdt', 0))
            used_usdt = float(balance.get('used_usdt', 0))
            print(f"   Total Balance: ${total_usdt:,.2f}")
            print(f"   Available Balance: ${free_usdt:,.2f}")
            print(f"   Used Balance: ${used_usdt:,.2f}")
            print("   ✅ Authentication successful")
        except Exception as e:
            print(f"   ❌ Balance check failed: {e}")
            print("\n🔧 Troubleshooting:")
            print("   1. Verify API keys are from demo mode (not live or testnet)")
            print("   2. Go to: https://www.bybit.com/en/trade/demo")
            print("   3. Navigate to Profile → API Management (while in demo mode)")
            print("   4. Generate new API keys with Read-Write + Contract permissions")
            print("   5. Update .env with new BYBIT_DEMO_API_KEY and BYBIT_DEMO_API_SECRET")
            return
        
        # Test 3: Check positions
        print("\n✅ Test 3: Position Check (Read Permissions)")
        try:
            positions = await client.fetch_open_positions()
            print(f"   Active Positions: {len(positions)}")
            for pos in positions:
                print(f"   - {pos.get('symbol', 'UNKNOWN')}: {pos.get('side', 'N/A')} {pos.get('size', 0)}")
            print("   ✅ Position read permission granted")
        except Exception as e:
            print(f"   ❌ Position check failed: {e}")
            print("   ⚠️  Read permissions may be restricted")
        
        # Test 4: Check orders
        print("\n✅ Test 4: Order Check (Read Permissions)")
        try:
            orders = await client.fetch_open_orders(symbol="XAU/USDT:USDT")
            print(f"   Open Orders: {len(orders)}")
            print("   ✅ Order read permission granted")
        except Exception as e:
            print(f"   ❌ Order check failed: {e}")
            print("   ⚠️  Order read permissions may be restricted")
        
        # Test 5: Place test order (requires write permissions)
        print("\n✅ Test 5: Test Order (Write Permissions)")
        try:
            # Place a very small test order (will be rejected if permissions insufficient)
            order = await client.create_market_order(
                symbol="XAU/USDT:USDT",
                side="buy",
                amount=0.01,
                leverage=1
            )
            print(f"   Order ID: {order.get('order_id', 'N/A')}")
            print(f"   Status: {order.get('status', 'N/A')}")
            print("   ✅ Write permissions granted")
                    
            # Cancel the test order immediately
            try:
                await client.cancel_order(
                    symbol="XAU/USDT:USDT",
                    order_id=order.get('order_id')
                )
                print("   ✅ Test order cancelled successfully")
            except Exception as e:
                print(f"   ⚠️  Could not cancel test order: {e}")
        except Exception as e:
            print(f"   ❌ Test order failed: {e}")
            print("   ⚠️  Write permissions may be restricted or insufficient balance")
        
        print("\n" + "=" * 70)
        print("✅ BYBIT DEMO API CHECK COMPLETE")
        print("=" * 70)
        print("\n Summary:")
        print("   • Server Connectivity: ✅ Working")
        print("   • Authentication: ✅ Working")
        print("   • API Permissions: See test results above")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(check_bybit_demo_api())
