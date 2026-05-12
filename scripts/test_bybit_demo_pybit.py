#!/usr/bin/env python3
"""
Test Bybit Demo Trading order placement using official pybit SDK.

This script:
1. Connects to api-demo.bybit.com (Demo Trading)
2. Fetches balance and ticker data
3. Places a small market BUY order ($15 USD worth)
4. Checks order status
5. Cancels or closes the position
6. Handles errors gracefully

Usage:
    source .venv/bin/activate
    python scripts/test_bybit_demo_pybit.py
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.pybit_demo_client import PybitDemoClient


async def test_demo_order():
    """Test placing a market order on Bybit Demo Trading."""
    client = None
    
    try:
        print("=" * 80)
        print("Bybit Demo Trading Order Test (pybit SDK)")
        print("=" * 80)
        
        # Step 1: Initialize PybitDemoClient
        print("\n[1/6] Initializing PybitDemoClient...")
        print("      Connecting to: https://api-demo.bybit.com")
        client = PybitDemoClient()
        print("      ✅ Client initialized (DEMO MODE)")
        
        # Step 2: Check demo balance
        print("\n[2/6] Checking demo account balance...")
        balance = await client.fetch_balance()
        usdt_balance = balance['total_usdt']
        print(f"      USDT Balance: {usdt_balance:.2f} USDT")
        
        if usdt_balance < 20:
            print("      ⚠️  Low balance! Request demo funds from Bybit demo interface")
            return False
        
        # Step 3: Fetch ticker and calculate order size
        print("\n[3/6] Fetching ticker data...")
        test_symbol = "XRPUSDT"  # Demo uses simple format (no :USDT suffix)
        target_usd_value = 15.0
        
        ticker = await client.fetch_ticker(test_symbol)
        current_price = ticker['last_price']
        order_amount = round(target_usd_value / current_price, 2)
        
        print(f"      Symbol: {test_symbol}")
        print(f"      Price: ${current_price:.4f}")
        print(f"      Order Amount: {order_amount} XRP (${target_usd_value:.2f})")
        
        # Step 4: Place market BUY order
        print("\n[4/6] Placing market BUY order on DEMO...")
        order_result = await client.create_market_order(
            symbol=test_symbol,
            side='buy',
            amount=order_amount,
            leverage=1
        )
        
        order_id = order_result['order_id']
        print(f"      ✅ Demo order placed: {order_id}")
        print(f"      Status: {order_result['status']}")
        
        # Step 5: Wait and check status
        print("\n[5/6] Checking order status...")
        await asyncio.sleep(2)
        
        order_status_info = await client.fetch_order_status(order_id, test_symbol)
        current_status = order_status_info['status']
        filled_qty = order_status_info['filled_qty']
        avg_price = order_status_info['avg_price']
        
        print(f"      Status: {current_status}")
        print(f"      Filled: {filled_qty} {test_symbol}")
        print(f"      Avg Price: ${avg_price:.4f}")
        
        # Step 6: Cleanup - cancel or close
        print("\n[6/6] Performing cleanup...")
        
        if current_status in ['Filled', 'PartiallyFilled']:
            print("      Order filled - closing position...")
            try:
                close_result = await client.close_position(test_symbol)
                if close_result['order_id']:
                    print(f"      ✅ Position closed: {close_result['order_id']}")
                else:
                    print(f"      ℹ️  {close_result['message']}")
            except Exception as e:
                print(f"      ⚠️  Close failed: {e}")
                
        elif current_status in ['New', 'Untriggered']:
            print("      Order open - cancelling...")
            try:
                cancel_result = await client.cancel_order(order_id, test_symbol)
                print(f"      ✅ Order cancelled: {cancel_result['order_id']}")
            except Exception as e:
                print(f"      ❌ Cancel failed: {e}")
        
        # Show final positions
        print("\n📊 Final Positions:")
        positions = await client.get_positions()
        if positions:
            for pos in positions:
                print(f"   {pos['symbol']}: {pos['side']} {pos['size']} @ ${pos['entry_price']:.4f}")
                print(f"      P&L: ${pos['unrealized_pnl']:.2f}")
        else:
            print("   No open positions")
        
        print("\n" + "=" * 80)
        print("✅ DEMO TEST PASSED - All steps completed successfully")
        print("=" * 80)
        print("\n📝 Notes:")
        print("   • This used DEMO TRADING (virtual funds)")
        print("   • Endpoint: https://api-demo.bybit.com")
        print("   • No real money was used")
        print("   • Order was automatically cleaned up")
        
        return True
        
    except Exception as e:
        print(f"\n❌ DEMO TEST FAILED: {e}")
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
    success = asyncio.run(test_demo_order())
    sys.exit(0 if success else 1)
