#!/usr/bin/env python3
"""
Bybit Exchange API Validation - Automated (Non-Interactive)
Tests complete trading cycle without user prompts.
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.infra.bybit_client import BybitClient


async def test_bybit_configuration():
    """Test 1: Verify Bybit API configuration"""
    print("\n" + "="*70)
    print("  TEST 1: BYBIT API CONFIGURATION")
    print("="*70)
    
    api_key = settings.BYBIT_API_KEY
    api_secret = settings.BYBIT_API_SECRET
    
    if not api_key or not api_secret:
        print("   ❌ API credentials not configured")
        return False
    
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    print(f"   ✅ BYBIT_API_KEY: {masked_key}")
    print(f"   ✅ Configuration valid")
    
    return True


async def test_testnet_connection():
    """Test 2: Connect to Bybit Demo Trading"""
    print("\n" + "="*70)
    print("  TEST 2: BYBIT DEMO TRADING CONNECTION")
    print("="*70)
    
    print("\n  ℹ️  Bybit Demo Trading Configuration:")
    print(f"  • Domain: api-demo.bybit.com")
    print(f"  • API Key: {settings.BYBIT_DEMO_API_KEY[:8]}..." if settings.BYBIT_DEMO_API_KEY else "  • API Key: NOT SET")
    print(f"  • Demo Domain Enabled: {settings.BYBIT_USE_DEMO_DOMAIN}")
    print()
    
    try:
        # Use demo trading mode with demo domain
        client = BybitClient(demo_trading=True)
        balance = await client.fetch_balance()
        
        print(f"   ✅ Connected to Bybit Demo Trading")
        print(f"   ✅ Domain: https://api-demo.bybit.com")
        print()
        print(f"   📊 Demo Account Balance:")
        print(f"   • Total USDT: ${balance['total_usdt']:,.2f}")
        print(f"   • Available: ${balance['free_usdt']:,.2f}")
        
        if balance['total_usdt'] > 0:
            print(f"   ✅ Demo account has virtual funds!")
        else:
            print(f"   ⚠️  Demo account shows $0 - may need to activate demo mode")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Connection failed: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False


async def test_mainnet_connection():
    """Test 3: Connect to Bybit Mainnet"""
    print("\n" + "="*70)
    print("  TEST 3: BYBIT MAINNET CONNECTION")
    print("="*70)
    
    try:
        client = BybitClient(testnet=False)
        balance = await client.fetch_balance()
        
        print(f"   ✅ Connected to Mainnet")
        print(f"   ✅ Balance: ${balance['total_usdt']:,.2f}")
        
        if balance['total_usdt'] >= settings.LIVE_TRADING_MIN_BALANCE_USD:
            print(f"   ✅ Sufficient balance for live trading")
        else:
            print(f"   ⚠️  Balance below minimum (${settings.LIVE_TRADING_MIN_BALANCE_USD:.2f})")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Mainnet connection failed: {str(e)[:100]}")
        return False


async def test_market_data():
    """Test 4: Fetch market data for Gold perpetual"""
    print("\n" + "="*70)
    print("  TEST 4: MARKET DATA FETCHING (Gold Perpetual)")
    print("="*70)
    
    try:
        # Use demo trading mode
        client = BybitClient(demo_trading=True)
        
        # Test both XAU (Gold) and XAG (Silver) perpetuals
        symbols_to_test = ['XAU/USDT:USDT', 'XAG/USDT:USDT']
        
        for symbol in symbols_to_test:
            ticker = await client.fetch_ticker(symbol)
            metal_name = "Gold" if "XAU" in symbol else "Silver"
            print(f"   ✅ {symbol} ({metal_name} Perpetual)")
            print(f"      • Price: ${ticker['last_price']:,.2f}")
            print(f"      • Bid/Ask: ${ticker['bid']:,.2f} / ${ticker['ask']:,.2f}")
            print(f"      • 24h Volume: ${ticker['volume_24h']:,.2f}")
            print()
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Market data fetch failed: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False


async def test_order_placement():
    """Test 5: Place and track order on Demo Trading with Gold perpetual"""
    print("\n" + "="*70)
    print("  TEST 5: ORDER PLACEMENT & STATUS (Demo Trading - Gold)")
    print("="*70)
    
    print("\n  ℹ️  This will place a REAL order on Demo Trading")
    print("  • Uses virtual funds from demo account")
    print("  • Symbol: XAU/USDT:USDT (Gold Perpetual)")
    print("  • All trades are risk-free (virtual money)")
    print()
    
    try:
        # Use demo trading mode
        client = BybitClient(demo_trading=True)
        
        # Get current price for XAU/USDT:USDT (Gold Perpetual)
        ticker = await client.fetch_ticker('XAU/USDT:USDT')
        current_price = ticker['last_price']
        
        # Place small test order (Gold is ~$3,300/oz, use 0.01 oz = ~$33)
        test_amount = 0.01  # 0.01 oz of gold (very conservative)
        estimated_cost = test_amount * current_price
        
        print(f"   📋 Order Details:")
        print(f"   • Symbol: XAU/USDT:USDT (Gold Perpetual)")
        print(f"   • Side: BUY")
        print(f"   • Amount: {test_amount} XAU (~{test_amount} oz)")
        print(f"   • Current Price: ${current_price:,.2f}")
        print(f"   • Estimated Cost: ${estimated_cost:,.2f}")
        print(f"   • Leverage: 1x")
        print()
        
        # Place market order
        print("   🚀 Placing market order...")
        order = await client.create_market_order(
            symbol='XAU/USDT:USDT',
            side='buy',
            amount=test_amount,
            leverage=1
        )
        
        print(f"   ✅ Order Placed Successfully!")
        print(f"   • Order ID: {order.get('order_id', 'N/A')}")
        print(f"   • Status: {order.get('status', 'N/A')}")
        print(f"   • Filled Price: ${order.get('price', 0):,.2f}")
        print(f"   • Amount: {order.get('amount', 0):,.4f} XAU")
        print(f"   • Cost: ${order.get('cost', 0):,.2f}")
        print(f"   • Fee: {order.get('fee', {})}")
        print()
        
        # Fetch order status
        print("   📊 Fetching order status...")
        order_status = await client.fetch_order_status(
            order_id=order['order_id'],
            symbol='XAU/USDT:USDT'
        )
        
        print(f"   ✅ Order Status Retrieved")
        print(f"   • Order ID: {order_status['order_id']}")
        print(f"   • Status: {order_status['status']}")
        print(f"   • Filled: {order_status['filled']} XAU")
        print(f"   • Remaining: {order_status['remaining']} XAU")
        print(f"   • Average Price: ${order_status.get('average', 0):,.2f}")
        print()
        
        # Check open positions
        print("   🔍 Checking open positions...")
        positions = await client.fetch_open_positions()
        
        if positions:
            print(f"   ✅ Found {len(positions)} open position(s):")
            for pos in positions:
                print(f"   • Symbol: {pos['symbol']}")
                print(f"     Side: {pos['side']}")
                print(f"     Size: {pos['size']}")
                print(f"     Entry Price: ${pos['entry_price']:,.2f}")
                print(f"     Mark Price: ${pos['mark_price']:,.2f}")
                print(f"     Unrealized PnL: ${pos['unrealized_pnl']:,.2f}")
                print()
        else:
            print(f"   ℹ️  No open positions (order may have been auto-closed)")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Order placement failed: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return False


async def test_risk_calculations():
    """Test 6: Risk management calculations"""
    print("\n" + "="*70)
    print("  TEST 6: RISK MANAGEMENT CALCULATIONS")
    print("="*70)
    
    try:
        client = BybitClient(testnet=True)
        
        # Example calculation
        entry_price = 50000.0
        stop_loss = 49000.0
        leverage = 5
        balance = 1000.0
        
        risk_amount = balance * settings.GOLD_RISK_PER_TRADE
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit
        
        fee_rate = client.get_trading_fee_rate()
        total_cost = client.calculate_total_cost(entry_price, quantity, leverage)
        
        print(f"   ✅ Risk Amount: ${risk_amount:.2f}")
        print(f"   ✅ Quantity: {quantity:.6f} BTC")
        print(f"   ✅ Fee Rate: {fee_rate*100:.3f}%")
        print(f"   ✅ Total Cost: ${total_cost:.2f}")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Risk calculation failed: {str(e)[:100]}")
        return False


async def main():
    print("\n" + "#"*70)
    print("#  BYBIT EXCHANGE API - AUTOMATED VALIDATION" + " "*29 + "#")
    print("#"*70)
    
    results = {}
    
    try:
        # Run all tests
        results['config'] = await test_bybit_configuration()
        await asyncio.sleep(0.5)
        
        results['testnet'] = await test_testnet_connection()
        await asyncio.sleep(0.5)
        
        results['mainnet'] = await test_mainnet_connection()
        await asyncio.sleep(0.5)
        
        results['market_data'] = await test_market_data()
        await asyncio.sleep(0.5)
        
        results['orders'] = await test_order_placement()
        await asyncio.sleep(0.5)
        
        results['risk'] = await test_risk_calculations()
        
    except Exception as e:
        print(f"\n❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("  VALIDATION SUMMARY")
    print("="*70)
    
    tests = [
        ("API Configuration", results.get('config', False)),
        ("Testnet Connection", results.get('testnet', False)),
        ("Mainnet Connection", results.get('mainnet', False)),
        ("Market Data", results.get('market_data', False)),
        ("Order Placement", results.get('orders', False)),
        ("Risk Calculations", results.get('risk', False)),
    ]
    
    passed = sum(1 for _, p in tests if p)
    total = len(tests)
    
    for name, result in tests:
        icon = "✅" if result else "❌"
        print(f"   {icon} {name}")
    
    print(f"\n   Results: {passed}/{total} passed")
    
    if passed == total:
        print("\n   🎉 ALL TESTS PASSED!")
    elif passed >= 4:
        print(f"\n   ⚠️  {passed}/{total} passed - Mostly operational")
    else:
        print(f"\n   ❌ Only {passed}/{total} passed - Needs attention")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
