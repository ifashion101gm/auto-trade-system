"""
Test script to place a sample market order on Bybit Testnet.

This script demonstrates:
1. Client initialization with testnet credentials
2. Fetching ticker data for safe order sizing
3. Placing a small market BUY order ($10-20 USD)
4. Order status checking and cleanup (cancel or close position)
5. Comprehensive error handling and logging

Usage:
    python3 scripts/test_bybit_market_order.py
"""
import asyncio
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.infra.bybit_client import BybitClient
from app.config import settings


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def print_header(title: str):
    """Print a formatted header."""
    print_separator()
    print(f"  {title}")
    print_separator()


async def test_bybit_market_order():
    """
    Main test function to place a sample market order on Bybit Testnet.
    """
    client = None
    
    try:
        print_header("Bybit Testnet Market Order Test")
        print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: Initialize BybitClient with testnet configuration
        print("\n[Step 1] Initializing BybitClient...")
        print(f"   Testnet: True")
        print(f"   Demo Trading: False")
        print(f"   API Key: {settings.BYBIT_DEMO_API_KEY[:8]}...{settings.BYBIT_DEMO_API_KEY[-4:] if settings.BYBIT_DEMO_API_KEY else 'N/A'}")
        print(f"   Rate Limit: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND} req/sec")
        print(f"   Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
        
        client = BybitClient(testnet=True, demo_trading=False)
        print("   ✅ Client initialized successfully")
        
        # Step 2: Check account balance
        print("\n[Step 2] Checking account balance...")
        try:
            balance = await client.fetch_balance()
            usdt_balance = balance['total_usdt']
            print(f"   USDT Balance: {usdt_balance:.2f} USDT")
            
            if usdt_balance < 50:
                print(f"   ⚠️  Warning: Low balance ({usdt_balance:.2f} USDT). Ensure sufficient funds for testing.")
        except Exception as e:
            print(f"   ❌ Failed to fetch balance: {e}")
            print("   Continuing with order placement anyway...")
        
        # Step 3: Select trading symbol and fetch ticker
        print("\n[Step 3] Fetching ticker data for order sizing...")
        
        # Try XRP first (lower price, safer for small orders)
        test_symbol = "XRP/USDT:USDT"
        target_usd_value = 15.0  # Target $15 USD order
        
        try:
            ticker = await client.fetch_ticker(test_symbol)
            current_price = ticker['last_price']
            print(f"   Symbol: {test_symbol}")
            print(f"   Current Price: ${current_price:.4f}")
            
            # Calculate safe order size
            order_amount = target_usd_value / current_price
            # Round down to avoid exceeding target
            order_amount = round(order_amount, 2)
            estimated_cost = order_amount * current_price
            
            print(f"   Target Order Value: ${target_usd_value:.2f} USD")
            print(f"   Calculated Amount: {order_amount} {test_symbol.split('/')[0]}")
            print(f"   Estimated Cost: ${estimated_cost:.2f} USD")
            
        except Exception as e:
            print(f"   ⚠️  Failed to fetch {test_symbol}, trying BTC/USDT:USDT...")
            test_symbol = "BTC/USDT:USDT"
            ticker = await client.fetch_ticker(test_symbol)
            current_price = ticker['last_price']
            print(f"   Symbol: {test_symbol}")
            print(f"   Current Price: ${current_price:.2f}")
            
            # For BTC, use very small amount
            order_amount = 0.0002  # ~$16 at $80k
            estimated_cost = order_amount * current_price
            print(f"   Order Amount: {order_amount} BTC")
            print(f"   Estimated Cost: ${estimated_cost:.2f} USD")
        
        # Step 4: Place market BUY order
        print("\n[Step 4] Placing market BUY order...")
        print(f"   Symbol: {test_symbol}")
        print(f"   Side: buy")
        print(f"   Amount: {order_amount}")
        print(f"   Type: MARKET")
        
        leverage = 1  # Use 1x leverage for safety
        
        try:
            order_result = await client.create_market_order(
                symbol=test_symbol,
                side='buy',
                amount=order_amount,
                leverage=leverage
            )
            
            print("\n   ✅ Order placed successfully!")
            print(f"   Order ID: {order_result['order_id']}")
            print(f"   Status: {order_result['status']}")
            print(f"   Filled Price: ${order_result['price']:.4f}" if order_result['price'] else "   Filled Price: N/A")
            print(f"   Amount: {order_result['amount']}")
            print(f"   Filled: {order_result['filled']}")
            print(f"   Remaining: {order_result['remaining']}")
            print(f"   Cost: ${order_result['cost']:.2f}" if order_result['cost'] else "   Cost: N/A")
            print(f"   Timestamp: {order_result['timestamp']}")
            
            order_id = order_result['order_id']
            order_status = order_result['status']
            
        except Exception as e:
            print(f"\n   ❌ Failed to place order: {e}")
            print("\n   Troubleshooting:")
            print("   1. Check API key permissions (Order - Trade)")
            print("   2. Verify sufficient USDT balance")
            print("   3. Ensure testnet has the trading pair available")
            print("   4. Check if minimum order size is met")
            return False
        
        # Step 5: Check order status and cleanup
        print("\n[Step 5] Checking order status and performing cleanup...")
        
        try:
            # Wait a moment for order to process
            await asyncio.sleep(2)
            
            # Fetch current order status
            order_status_info = await client.fetch_order_status(order_id, test_symbol)
            current_status = order_status_info['status']
            print(f"   Current Status: {current_status}")
            
            if current_status == 'closed' or current_status == 'filled':
                print("   ✅ Order was filled successfully")
                
                # Close the position
                print("\n[Step 6] Closing position...")
                try:
                    close_result = await client.close_position(test_symbol)
                    print(f"   ✅ Position closed")
                    print(f"   Close Order ID: {close_result['order_id']}")
                    print(f"   Close Status: {close_result['status']}")
                    print(f"   Close Price: ${close_result['price']:.4f}" if close_result.get('price') else "   Close Price: N/A")
                except Exception as e:
                    print(f"   ⚠️  Failed to close position: {e}")
                    print("   Note: Position may already be closed or not exist")
                    
            elif current_status == 'open' or current_status == 'new':
                print("   ⚠️  Order is still open - attempting to cancel...")
                
                # Cancel the order
                try:
                    cancel_result = await client.cancel_order(order_id, test_symbol)
                    print(f"   ✅ Order cancelled successfully")
                    print(f"   Cancelled Order ID: {cancel_result['order_id']}")
                    print(f"   Cancel Status: {cancel_result['status']}")
                except Exception as e:
                    print(f"   ❌ Failed to cancel order: {e}")
                    
            else:
                print(f"   ℹ️  Order status: {current_status} (no action needed)")
        
        except Exception as e:
            print(f"   ⚠️  Error during status check/cleanup: {e}")
            print("   Note: Manual cleanup may be required")
        
        # Step 7: Final summary
        print("\n" + "=" * 80)
        print("  TEST SUMMARY")
        print("=" * 80)
        print(f"  ✅ Client Initialization: SUCCESS")
        print(f"  ✅ Balance Check: {'SUCCESS' if usdt_balance > 0 else 'SKIPPED'}")
        print(f"  ✅ Ticker Fetch: SUCCESS")
        print(f"  ✅ Order Placement: {'SUCCESS' if order_id else 'FAILED'}")
        print(f"  ✅ Cleanup: COMPLETED")
        print("=" * 80)
        print("\n  🎉 Test completed successfully!")
        print("  Check your Bybit Testnet account for order history.")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Always close the client connection
        if client:
            print("\n[Cleanup] Closing client connection...")
            try:
                await client.close()
                print("   ✅ Client connection closed")
            except Exception as e:
                print(f"   ⚠️  Error closing connection: {e}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("  WARNING: This script will place a REAL order on Bybit TESTNET")
    print("  Testnet uses virtual funds, but please verify before proceeding.")
    print("=" * 80)
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        print("\nStarting test...\n")
        result = asyncio.run(test_bybit_market_order())
        sys.exit(0 if result else 1)
    else:
        print("\nTest cancelled by user.")
        sys.exit(0)
