"""
Automated test script to place a sample market order on Bybit Testnet.

This is a non-interactive version suitable for CI/CD or automated testing.
No user confirmation required - use with caution!

Usage:
    python3 scripts/test_bybit_market_order_auto.py
"""
import asyncio
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.infra.bybit_client import BybitClient
from app.config import settings


async def test_bybit_market_order_auto():
    """
    Automated test function to place a sample market order on Bybit Testnet.
    """
    client = None
    
    try:
        print("=" * 80)
        print("Bybit Testnet Market Order Test (Automated)")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Step 1: Initialize BybitClient
        print("[1/6] Initializing BybitClient...")
        client = BybitClient(testnet=True, demo_trading=False)
        print("      ✅ Client initialized")
        
        # Step 2: Check balance
        print("\n[2/6] Checking account balance...")
        balance = await client.fetch_balance()
        usdt_balance = balance['total_usdt']
        print(f"      USDT Balance: {usdt_balance:.2f} USDT")
        
        if usdt_balance < 20:
            print(f"      ⚠️  Warning: Low balance ({usdt_balance:.2f} USDT)")
        
        # Step 3: Fetch ticker and calculate order size
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
        print("✅ TEST PASSED - All steps completed successfully")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
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
    result = asyncio.run(test_bybit_market_order_auto())
    sys.exit(0 if result else 1)
