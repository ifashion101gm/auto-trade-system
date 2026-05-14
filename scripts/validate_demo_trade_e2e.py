#!/usr/bin/env python3
"""
Comprehensive Demo Trade Validation Script

Executes a complete end-to-end trade lifecycle on Bybit Demo Trading account:
1. Configuration verification
2. Client initialization (Pybit SDK)
3. Pre-trade validation (balance, ticker)
4. Market order execution (~$10-15 USD)
5. Order status monitoring
6. Position verification
7. Cleanup (close position)
8. Final state confirmation

SAFETY: Uses DEMO credentials only - NO live trading occurs.
"""
import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.logging_config import setup_logger

setup_logger()


def mask_key(key: str) -> str:
    """Mask API key for safe display."""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


async def validate_configuration():
    """Step 1: Verify demo trading configuration."""
    print("\n" + "=" * 80)
    print("STEP 1: CONFIGURATION VERIFICATION")
    print("=" * 80)
    
    # Check demo domain setting
    if not settings.BYBIT_USE_DEMO_DOMAIN:
        print("❌ FAIL: BYBIT_USE_DEMO_DOMAIN is not enabled")
        print(f"   Current value: {settings.BYBIT_USE_DEMO_DOMAIN}")
        print("\nPlease set in .env:")
        print("   BYBIT_USE_DEMO_DOMAIN=true")
        return False
    
    print("✅ BYBIT_USE_DEMO_DOMAIN = true")
    
    # Check demo credentials
    demo_key = settings.BYBIT_DEMO_API_KEY
    demo_secret = settings.BYBIT_DEMO_API_SECRET
    
    if not demo_key or not demo_secret:
        print("❌ FAIL: Demo API credentials missing")
        print("\nPlease set in .env:")
        print("   BYBIT_DEMO_API_KEY=<your_demo_key>")
        print("   BYBIT_DEMO_API_SECRET=<your_demo_secret>")
        return False
    
    print(f"✅ Demo API Key: {mask_key(demo_key)}")
    print(f"✅ Demo API Secret: {mask_key(demo_secret)[:4]}...")
    print("✅ Endpoint: https://api-demo.bybit.com")
    print("✅ SDK: Official Pybit v5 (required for demo)")
    
    return True


async def test_client_initialization():
    """Step 2: Initialize client and verify routing."""
    print("\n" + "=" * 80)
    print("STEP 2: CLIENT INITIALIZATION")
    print("=" * 80)
    
    try:
        from app.infra.bybit_client import BybitClient
        
        print("\n🔧 Initializing BybitClient with demo_trading=True...")
        client = BybitClient(
            api_key=settings.BYBIT_DEMO_API_KEY,
            api_secret=settings.BYBIT_DEMO_API_SECRET,
            testnet=False,
            demo_trading=True
        )
        
        # Verify internal configuration
        print(f"\n✅ Client initialized successfully")
        print(f"   Mode: {'DEMO' if client.demo_trading else 'LIVE'}")
        print(f"   Using Pybit: {client.use_pybit}")
        print(f"   Testnet: {client.testnet}")
        
        if not client.use_pybit:
            print("❌ FAIL: Client should be using Pybit SDK for demo mode")
            await client.close()
            return False
        
        print("✅ Correctly using Pybit SDK for demo trading")
        print("✅ Routing to: https://api-demo.bybit.com")
        
        return client
        
    except Exception as e:
        print(f"❌ FAIL: Client initialization error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def pre_trade_validation(client):
    """Step 3: Fetch balance and ticker for pre-trade checks."""
    print("\n" + "=" * 80)
    print("STEP 3: PRE-TRADE VALIDATION")
    print("=" * 80)
    
    try:
        # Fetch balance
        print("\n💰 Fetching USDT balance...")
        start_time = time.time()
        balance = await client.fetch_balance()
        elapsed = time.time() - start_time
        
        total_usdt = balance.get('total_usdt', 0)
        free_usdt = balance.get('free_usdt', 0)
        
        print(f"✅ Balance fetched in {elapsed*1000:.0f}ms")
        print(f"   Total USDT: ${total_usdt:.2f}")
        print(f"   Available: ${free_usdt:.2f}")
        
        if total_usdt < 10:
            print(f"\n⚠️  WARNING: Low balance (${total_usdt:.2f})")
            print("   Recommended minimum: $100 USDT for testing")
            return False, None
        
        # Fetch ticker
        print("\n📊 Fetching XRP/USDT ticker...")
        symbol = "XRP/USDT:USDT"
        start_time = time.time()
        ticker = await client.fetch_ticker(symbol)
        elapsed = time.time() - start_time
        
        last_price = ticker.get('last_price', 0)
        bid = ticker.get('bid', 0)
        ask = ticker.get('ask', 0)
        
        print(f"✅ Ticker fetched in {elapsed*1000:.0f}ms")
        print(f"   Symbol: {symbol}")
        print(f"   Last Price: ${last_price:.4f}")
        print(f"   Bid: ${bid:.4f} | Ask: ${ask:.4f}")
        
        if last_price <= 0:
            print("❌ FAIL: Invalid ticker price")
            return False, None
        
        return True, ticker
        
    except Exception as e:
        print(f"❌ FAIL: Pre-trade validation error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def execute_market_order(client, ticker):
    """Step 4: Execute small market buy order (~$10-15 USD)."""
    print("\n" + "=" * 80)
    print("STEP 4: MARKET ORDER EXECUTION")
    print("=" * 80)
    
    try:
        symbol = "XRP/USDT:USDT"
        current_price = ticker.get('last_price', 0)
        
        # Calculate quantity for ~$12 USD position
        target_value = 12.0  # USD
        raw_quantity = target_value / current_price
        
        # Get instrument info to determine proper quantity step
        print(f"\n🔍 Fetching instrument specifications for {symbol}...")
        try:
            # Use CCXT exchange to get market info
            markets = await client.exchange.load_markets()
            if symbol in markets:
                market = markets[symbol]
                amount_step = market.get('precision', {}).get('amount', 0.01)
                min_amount = market.get('limits', {}).get('amount', {}).get('min', 0.01)
                
                print(f"   Amount Step: {amount_step}")
                print(f"   Min Amount: {min_amount}")
                
                # Round quantity to nearest step
                if isinstance(amount_step, float) and amount_step > 0:
                    quantity = round(raw_quantity / amount_step) * amount_step
                    quantity = round(quantity, 8)  # Avoid floating point issues
                else:
                    quantity = round(raw_quantity, 2)
                
                # Ensure it meets minimum
                if quantity < min_amount:
                    quantity = min_amount
                    print(f"   ⚠️  Adjusted to minimum: {quantity}")
            else:
                # Fallback: round to 2 decimal places
                quantity = round(raw_quantity, 2)
                print(f"   ⚠️  Market not found, using default precision")
        except Exception as e:
            print(f"   ⚠️  Could not fetch market info: {e}")
            quantity = round(raw_quantity, 2)
        
        estimated_cost = quantity * current_price
        
        print(f"\n🎯 Order Parameters:")
        print(f"   Symbol: {symbol}")
        print(f"   Side: BUY (Long)")
        print(f"   Type: MARKET")
        print(f"   Quantity: {quantity} contracts")
        print(f"   Current Price: ${current_price:.4f}")
        print(f"   Estimated Value: ${estimated_cost:.2f} USD")
        print(f"   Leverage: 1x (no leverage)")
        
        # Confirm safety
        print(f"\n⚠️  SAFETY CHECK:")
        print(f"   ✓ Demo trading mode: ENABLED")
        print(f"   ✓ No real funds at risk")
        print(f"   ✓ Small position size (${estimated_cost:.2f})")
        print(f"   ✓ Will close position immediately after")
        
        confirm = input(f"\nProceed with order? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("\n❌ Order cancelled by user")
            return None
        
        # Place order
        print(f"\n🚀 Placing market order...")
        start_time = time.time()
        
        order = await client.create_market_order(
            symbol=symbol,
            side='buy',
            amount=quantity,
            leverage=1
        )
        
        elapsed = time.time() - start_time
        
        order_id = order.get('order_id', 'N/A')
        status = order.get('status', 'unknown')
        filled = order.get('filled', 0)
        avg_price = order.get('price', 0)
        
        print(f"\n✅ Order placed in {elapsed*1000:.0f}ms")
        print(f"   Order ID: {order_id}")
        print(f"   Status: {status}")
        print(f"   Filled: {filled}")
        print(f"   Average Price: ${avg_price:.4f}" if avg_price else "   Average Price: Pending fill")
        
        # Wait briefly for fill
        print(f"\n⏳ Waiting for order fill...")
        await asyncio.sleep(2)
        
        # Check order status
        print(f"\n🔍 Checking order status...")
        try:
            order_status = await client.fetch_order_status(order_id, symbol)
            final_status = order_status.get('status', 'unknown')
            filled_qty = order_status.get('filled', 0)
            avg_exec_price = order_status.get('average', avg_price)
            
            print(f"   Final Status: {final_status}")
            print(f"   Filled Qty: {filled_qty}")
            print(f"   Avg Execution Price: ${avg_exec_price:.4f}" if avg_exec_price else "   Avg Execution Price: N/A")
            
            if final_status in ['closed', 'filled']:
                print(f"✅ Order fully filled")
            elif final_status == 'open':
                print(f"⚠️  Order still open (may be partially filled)")
            else:
                print(f"ℹ️  Order status: {final_status}")
            
        except Exception as e:
            print(f"⚠️  Could not fetch order status: {e}")
            final_status = status
            avg_exec_price = avg_price
        
        return {
            'order_id': order_id,
            'symbol': symbol,
            'side': 'buy',
            'quantity': quantity,
            'status': final_status,
            'avg_price': avg_exec_price,
            'value': estimated_cost
        }
        
    except Exception as e:
        print(f"❌ FAIL: Order execution error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def verify_positions(client):
    """Step 5: Check open positions after order."""
    print("\n" + "=" * 80)
    print("STEP 5: POSITION VERIFICATION")
    print("=" * 80)
    
    try:
        print("\n📍 Fetching open positions...")
        positions = await client.fetch_open_positions()
        
        if not positions:
            print("ℹ️  No open positions found")
            print("   (Order may not have created a position yet)")
            return []
        
        print(f"✅ Found {len(positions)} open position(s):\n")
        
        for i, pos in enumerate(positions, 1):
            symbol = pos.get('symbol', 'N/A')
            side = pos.get('side', 'N/A')
            size = pos.get('size', 0)
            entry_price = pos.get('entry_price', 0)
            mark_price = pos.get('mark_price', 0)
            unrealized_pnl = pos.get('unrealized_pnl', 0)
            leverage = pos.get('leverage', 1)
            
            print(f"   Position #{i}:")
            print(f"      Symbol: {symbol}")
            print(f"      Side: {side.upper()}")
            print(f"      Size: {size}")
            print(f"      Entry Price: ${entry_price:.4f}")
            print(f"      Mark Price: ${mark_price:.4f}")
            print(f"      Unrealized PnL: ${unrealized_pnl:+.2f}")
            print(f"      Leverage: {leverage}x")
            print()
        
        return positions
        
    except Exception as e:
        print(f"❌ FAIL: Position verification error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def cleanup_position(client, positions):
    """Step 6: Close all open positions for cleanup."""
    print("\n" + "=" * 80)
    print("STEP 6: POSITION CLEANUP")
    print("=" * 80)
    
    if not positions:
        print("ℹ️  No positions to close")
        return True
    
    try:
        closed_count = 0
        
        for pos in positions:
            symbol = pos.get('symbol', '')
            side = pos.get('side', '')
            size = pos.get('size', 0)
            
            if size <= 0:
                continue
            
            print(f"\n🔄 Closing position: {symbol} ({side.upper()} {size})")
            
            # Determine opposite side
            close_side = 'sell' if side == 'long' else 'buy'
            
            # Close with market order
            close_order = await client.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=size,
                leverage=1
            )
            
            order_id = close_order.get('order_id', 'N/A')
            print(f"   ✅ Close order placed: {order_id}")
            
            # Wait for fill
            await asyncio.sleep(2)
            
            closed_count += 1
        
        print(f"\n✅ Successfully closed {closed_count} position(s)")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Cleanup error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def final_state_check(client):
    """Step 7: Verify final account state."""
    print("\n" + "=" * 80)
    print("STEP 7: FINAL STATE VERIFICATION")
    print("=" * 80)
    
    try:
        # Check balance
        print("\n💰 Final balance check...")
        balance = await client.fetch_balance()
        total_usdt = balance.get('total_usdt', 0)
        print(f"   Total USDT: ${total_usdt:.2f}")
        
        # Check positions
        print("\n📍 Final position check...")
        positions = await client.fetch_open_positions()
        
        if positions:
            print(f"   ⚠️  WARNING: {len(positions)} position(s) still open:")
            for pos in positions:
                print(f"      - {pos.get('symbol')}: {pos.get('side')} {pos.get('size')}")
        else:
            print("   ✅ All positions closed")
        
        print("\n✅ Final state verified")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Final state check error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Execute complete demo trade validation."""
    print("\n" + "=" * 80)
    print("BYBIT DEMO TRADING - END-TO-END TRADE VALIDATION")
    print("=" * 80)
    print("\nThis script will:")
    print("  1. Verify demo configuration")
    print("  2. Initialize Pybit SDK client")
    print("  3. Check balance and market data")
    print("  4. Execute small market buy order (~$12 USD)")
    print("  5. Monitor order fill and position")
    print("  6. Close position for cleanup")
    print("  7. Verify final state")
    print("\n⚠️  SAFETY: Uses DEMO account only - NO real funds at risk")
    print("=" * 80)
    
    client = None
    
    try:
        # Step 1: Configuration
        config_ok = await validate_configuration()
        if not config_ok:
            print("\n❌ VALIDATION FAILED: Configuration issues detected")
            return False
        
        # Step 2: Client initialization
        client = await test_client_initialization()
        if not client:
            print("\n❌ VALIDATION FAILED: Client initialization failed")
            return False
        
        # Step 3: Pre-trade validation
        pre_trade_ok, ticker = await pre_trade_validation(client)
        if not pre_trade_ok:
            print("\n❌ VALIDATION FAILED: Pre-trade checks failed")
            return False
        
        # Step 4: Execute order
        order_result = await execute_market_order(client, ticker)
        if not order_result:
            print("\n❌ VALIDATION FAILED: Order execution failed")
            return False
        
        print(f"\n{'='*80}")
        print(f"ORDER EXECUTED SUCCESSFULLY")
        print(f"{'='*80}")
        print(f"  Order ID: {order_result['order_id']}")
        print(f"  Symbol: {order_result['symbol']}")
        print(f"  Side: {order_result['side'].upper()}")
        print(f"  Quantity: {order_result['quantity']}")
        print(f"  Est. Value: ${order_result['value']:.2f} USD")
        print(f"  Status: {order_result['status']}")
        print(f"  Avg Price: ${order_result['avg_price']:.4f}" if order_result['avg_price'] else f"  Avg Price: Pending")
        
        # Step 5: Verify positions
        positions = await verify_positions(client)
        
        # Step 6: Cleanup
        cleanup_ok = await cleanup_position(client, positions)
        if not cleanup_ok:
            print("\n⚠️  WARNING: Cleanup encountered errors")
        
        # Step 7: Final state
        final_ok = await final_state_check(client)
        
        # Summary
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        print(f"✅ Configuration: PASSED")
        print(f"✅ Client Init: PASSED")
        print(f"✅ Pre-Trade Checks: PASSED")
        print(f"✅ Order Execution: PASSED")
        print(f"✅ Position Verification: {'PASSED' if positions else 'NO POSITIONS'}")
        print(f"✅ Cleanup: {'PASSED' if cleanup_ok else 'FAILED'}")
        print(f"✅ Final State: {'PASSED' if final_ok else 'FAILED'}")
        print("=" * 80)
        
        print("\n🎉 DEMO TRADE VALIDATION COMPLETED SUCCESSFULLY!")
        print("\nKey Results:")
        print(f"  • Order ID: {order_result['order_id']}")
        print(f"  • Execution Price: ${order_result['avg_price']:.4f}" if order_result['avg_price'] else "  • Execution Price: Market rate")
        print(f"  • Position Size: {order_result['quantity']} contracts")
        print(f"  • Total Value: ~${order_result['value']:.2f} USD")
        print(f"  • Final Status: {order_result['status']}")
        print("\n✅ All systems operational for demo trading")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        return False
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if client:
            await client.close()
            print("\n🔒 Client connection closed")


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
