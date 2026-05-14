#!/usr/bin/env python3
"""
Sample Trade on Bybit Demo Account

This script executes a small test trade on the demo account to verify:
- API authentication works correctly
- Order placement and execution flow
- Position management
- Trade lifecycle tracking

SAFETY: Uses DEMO credentials only - no real funds at risk.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.bybit_client import BybitClient
from app.config import settings


async def execute_sample_trade():
    """Execute a sample trade on Bybit demo account."""
    
    print("=" * 80)
    print("BYBIT DEMO ACCOUNT - SAMPLE TRADE EXECUTION")
    print("=" * 80)
    print()
    
    # Verify we're using demo mode
    if not settings.BYBIT_USE_DEMO_DOMAIN:
        print("❌ ERROR: Not configured for demo trading!")
        print(f"   BYBIT_USE_DEMO_DOMAIN = {settings.BYBIT_USE_DEMO_DOMAIN}")
        print("\nPlease ensure .env has:")
        print("   BYBIT_USE_DEMO_DOMAIN=true")
        print("   BYBIT_DEMO_API_KEY=<your_demo_key>")
        print("   BYBIT_DEMO_API_SECRET=<your_demo_secret>")
        return False
    
    print("✅ Configuration verified for demo trading")
    print()
    
    client = None
    try:
        # Step 1: Initialize demo client
        print("📋 Step 1: Initializing Bybit Demo Client...")
        client = BybitClient(testnet=False, demo_trading=True)
        print("   ✅ Client initialized successfully")
        print()
        
        # Step 2: Check balance
        print("💰 Step 2: Checking account balance...")
        balance = await client.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('total', 0)
        print(f"   USDT Balance: ${usdt_balance:.2f}")
        
        if usdt_balance < 10:
            print("   ⚠️  Warning: Low balance for trading")
        print()
        
        # Step 3: Get market data
        print("📊 Step 3: Fetching market data...")
        symbol = "XAU/USDT:USDT"  # Gold futures
        ticker = await client.exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"   Symbol: {symbol}")
        print(f"   Current Price: ${current_price:.2f}")
        print(f"   Bid: ${ticker['bid']:.2f} | Ask: ${ticker['ask']:.2f}")
        print()
        
        # Step 4: Calculate order size (small test position)
        quantity = 0.01  # 0.01 contracts (very small for safety)
        order_value = quantity * current_price
        print("📐 Step 4: Order parameters...")
        print(f"   Quantity: {quantity} contracts")
        print(f"   Estimated Value: ${order_value:.2f}")
        print(f"   Side: BUY (Long)")
        print()
        
        # Step 5: Place order
        print("🚀 Step 5: Placing MARKET BUY order...")
        try:
            # Use CCXT directly through the client's exchange
            order = await client.exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=quantity
            )
            
            print("   ✅ Order placed successfully!")
            print(f"   Order ID: {order.get('id', 'N/A')}")
            print(f"   Status: {order.get('status', 'N/A')}")
            print(f"   Filled: {order.get('filled', 0)}")
            print(f"   Average Price: ${order.get('average', 0):.2f}")
            print()
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Order placement failed: {error_msg}")
            
            if "insufficient" in error_msg.lower() or "balance" in error_msg.lower():
                print("\n   ⚠️  Demo account has insufficient balance.")
                print("   Please fund your demo account at:")
                print("   https://www.bybit.com/en/demo-trading")
            elif "permission" in error_msg.lower():
                print("\n   ⚠️  API keys may not have trading permissions.")
                print("   Check API key settings in Bybit dashboard.")
            else:
                print("\n   This is expected if:")
                print("   - Demo account needs funding")
                print("   - API keys don't have trading permissions")
                print("   - Market is closed or unavailable")
            return False
        
        # Step 6: Check positions
        print("📍 Step 6: Checking open positions...")
        positions = await client.fetch_open_positions()
        
        gold_positions = [p for p in positions if 'XAU' in p.get('symbol', '')]
        if gold_positions:
            for pos in gold_positions:
                print(f"   ✅ Position found:")
                print(f"      Symbol: {pos['symbol']}")
                print(f"      Side: {pos['side']}")
                print(f"      Size: {pos['contracts']}")
                print(f"      Entry Price: ${pos['entryPrice']:.2f}")
                print(f"      Unrealized PnL: ${pos['unrealizedPnl']:.2f}")
        else:
            print("   ℹ️  No open positions (order may still be processing)")
        print()
        
        # Step 7: Summary
        print("=" * 80)
        print("TRADE EXECUTION SUMMARY")
        print("=" * 80)
        print(f"✅ Demo trade executed successfully")
        print(f"   Symbol: {symbol}")
        print(f"   Side: BUY")
        print(f"   Quantity: {quantity} contracts")
        print(f"   Type: MARKET ORDER")
        print(f"   Account: DEMO (No real funds)")
        print()
        print("Next steps:")
        print("   1. Monitor position in Bybit demo dashboard")
        print("   2. Close position manually or via API when ready")
        print("   3. Review trade in transaction history")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during trade execution: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if client:
            await client.close()
            print("\n🔒 Client connection closed")


if __name__ == "__main__":
    print()
    success = asyncio.run(execute_sample_trade())
    print()
    
    if success:
        print("✅ Sample trade completed successfully!")
        sys.exit(0)
    else:
        print("⚠️  Sample trade did not complete (check output above)")
        sys.exit(1)
