"""
Test market order on Bybit Demo Trading environment.

Demo Trading uses api-demo.bybit.com with virtual funds.
This is different from Testnet (api-testnet.bybit.com).

Usage:
    python3 scripts/test_bybit_demo_order.py
"""
import asyncio
import sys
from datetime import datetime

sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.infra.bybit_client import BybitClient
from app.config import settings


async def test_demo_market_order():
    """Place a test market order on Bybit Demo Trading."""
    client = None
    
    try:
        print("=" * 80)
        print("Bybit Demo Trading Market Order Test")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Step 1: Initialize with demo trading mode
        print("[1/6] Initializing BybitClient (Demo Trading Mode)...")
        print(f"      Domain: api-demo.bybit.com")
        print(f"      API Key: {settings.BYBIT_DEMO_API_KEY[:8]}...{settings.BYBIT_DEMO_API_KEY[-4:]}")
        
        # Force demo_trading=True to use demo domain
        client = BybitClient(testnet=False, demo_trading=True)
        print("      ✅ Client initialized")
        
        # Step 2: Check balance
        print("\n[2/6] Checking demo account balance...")
        balance = await client.fetch_balance()
        usdt_balance = balance['total_usdt']
        print(f"      USDT Balance: {usdt_balance:,.2f} USDT")
        
        if usdt_balance < 50:
            print(f"      ⚠️  Warning: Low balance ({usdt_balance:.2f} USDT)")
            print(f"      Visit https://www.bybit.com/en/trade/demo to add virtual funds")
        
        # Step 3: Fetch ticker
        print("\n[3/6] Fetching ticker data...")
        test_symbol = "XRP/USDT:USDT"
        target_usd_value = 15.0
        
        ticker = await client.fetch_ticker(test_symbol)
        current_price = ticker['last_price']
        order_amount = round(target_usd_value / current_price, 2)
        
        print(f"      Symbol: {test_symbol}")
        print(f"      Price: ${current_price:.4f}")
        print(f"      Order Amount: {order_amount} XRP (${target_usd_value:.2f})")
        
        # Step 4: Place market BUY order
        print("\n[4/6] Placing market BUY order...")
        order_result = await client.create_market_order(
            symbol=test_symbol,
            side='buy',
            amount=order_amount,
            leverage=1
        )
        
        order_id = order_result['order_id']
        print(f"      ✅ Order placed: {order_id}")
        print(f"      Status: {order_result['status']}")
        print(f"      Filled: {order_result['filled']}")
        if order_result.get('price'):
            print(f"      Price: ${order_result['price']:.4f}")
        
        # Step 5: Wait and check status
        print("\n[5/6] Checking order status...")
        await asyncio.sleep(2)
        
        order_status_info = await client.fetch_order_status(order_id, test_symbol)
        current_status = order_status_info['status']
        print(f"      Status: {current_status}")
        
        # Step 6: Cleanup
        print("\n[6/6] Performing cleanup...")
        
        if current_status in ['closed', 'filled']:
            print("      Order filled - closing position...")
            try:
                close_result = await client.close_position(test_symbol)
                print(f"      ✅ Position closed: {close_result['order_id']}")
            except Exception as e:
                print(f"      ⚠️  Close failed: {e}")
                
        elif current_status in ['open', 'new']:
            print("      Order open - cancelling...")
            try:
                cancel_result = await client.cancel_order(order_id, test_symbol)
                print(f"      ✅ Order cancelled: {cancel_result['order_id']}")
            except Exception as e:
                print(f"      ❌ Cancel failed: {e}")
        else:
            print(f"      ℹ️  Status: {current_status} (no action)")
        
        # Summary
        print("\n" + "=" * 80)
        print("✅ DEMO TRADING TEST PASSED")
        print("=" * 80)
        print(f"Order ID: {order_id}")
        print(f"Status: {current_status}")
        print(f"Symbol: {test_symbol}")
        print(f"Amount: {order_amount} XRP")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        
        # Provide specific guidance for common errors
        error_msg = str(e)
        if '10024' in error_msg:
            print("\n   💡 This error suggests regulatory restrictions on Demo Trading.")
            print("   Try these solutions:")
            print("   1. Verify your main Bybit account has completed KYC")
            print("   2. Check if derivatives trading is enabled on your account")
            print("   3. Contact Bybit support if restrictions persist")
            print("   4. Consider using a different region's demo account")
        elif '10003' in error_msg:
            print("\n   💡 API key invalid. Verify credentials in .env file.")
        elif '10004' in error_msg:
            print("\n   💡 Permissions denied. Enable Order-Trade permission on API key.")
        
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if client:
            try:
                await client.close()
            except:
                pass


if __name__ == "__main__":
    print("\n⚠️  This will place an order on Bybit DEMO TRADING (virtual funds)")
    print("    Demo Trading may have different restrictions than Testnet.\n")
    
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        print("\nStarting demo trading test...\n")
        result = asyncio.run(test_demo_market_order())
        sys.exit(0 if result else 1)
    else:
        print("\nTest cancelled.")
        sys.exit(0)
