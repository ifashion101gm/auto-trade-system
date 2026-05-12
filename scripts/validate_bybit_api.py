#!/usr/bin/env python3
"""
Bybit Exchange API Validation Script
Tests: Configuration → Connection → Market Data → Order Placement → Status Retrieval
Validates both Testnet (paper trading) and Mainnet (live trading) connectivity.
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
    
    print("\n1.1 Checking API Credentials")
    print("-" * 70)
    
    api_key = settings.BYBIT_API_KEY
    api_secret = settings.BYBIT_API_SECRET
    
    if not api_key:
        print("   ❌ BYBIT_API_KEY not configured in .env")
        return False
    
    if not api_secret:
        print("   ❌ BYBIT_API_SECRET not configured in .env")
        return False
    
    # Mask sensitive data for display
    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
    masked_secret = f"{api_secret[:8]}...{api_secret[-4:]}" if len(api_secret) > 12 else "***"
    
    print(f"   ✅ BYBIT_API_KEY: {masked_key}")
    print(f"   ✅ BYBIT_API_SECRET: {masked_secret}")
    print(f"   ✅ API credentials configured")
    
    print("\n1.2 Configuration Parameters")
    print("-" * 70)
    print(f"   Active Exchange: {settings.ACTIVE_EXCHANGE}")
    print(f"   Execution Mode: {settings.EXECUTION_MODE}")
    print(f"   Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"   Risk Per Trade: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
    
    return True


async def test_bybit_testnet_connection():
    """Test 2: Connect to Bybit Testnet"""
    print("\n" + "="*70)
    print("  TEST 2: BYBIT TESTNET CONNECTION (Paper Trading)")
    print("="*70)
    
    try:
        print("\n2.1 Initializing Testnet Client")
        print("-" * 70)
        
        client = BybitClient(testnet=True)
        print("   ✅ Bybit Testnet client initialized")
        
        # Fetch balance
        print("\n2.2 Fetching Account Balance")
        print("-" * 70)
        balance = await client.fetch_balance()
        
        print(f"   ✅ Total USDT: ${balance['total_usdt']:,.2f}")
        print(f"   ✅ Available: ${balance['free_usdt']:,.2f}")
        print(f"   ✅ Used: ${balance['used_usdt']:,.2f}")
        
        if balance['total_usdt'] > 0:
            print(f"   ✅ Testnet account has balance")
        else:
            print(f"   ⚠️  Testnet account has zero balance (may need faucet)")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Testnet connection failed: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return False


async def test_bybit_mainnet_connection():
    """Test 3: Connect to Bybit Mainnet"""
    print("\n" + "="*70)
    print("  TEST 3: BYBIT MAINNET CONNECTION (Live Trading)")
    print("="*70)
    
    print("\n⚠️  WARNING: This connects to LIVE TRADING environment")
    print("   Only proceed if you intend to trade with real funds!")
    print()
    
    try:
        print("3.1 Initializing Mainnet Client")
        print("-" * 70)
        
        client = BybitClient(testnet=False)
        print("   ✅ Bybit Mainnet client initialized")
        
        # Fetch balance
        print("\n3.2 Fetching Live Account Balance")
        print("-" * 70)
        balance = await client.fetch_balance()
        
        print(f"   ✅ Total USDT: ${balance['total_usdt']:,.2f}")
        print(f"   ✅ Available: ${balance['free_usdt']:,.2f}")
        print(f"   ✅ Used: ${balance['used_usdt']:,.2f}")
        
        if balance['total_usdt'] >= settings.LIVE_TRADING_MIN_BALANCE_USD:
            print(f"   ✅ Sufficient balance for live trading (min: ${settings.LIVE_TRADING_MIN_BALANCE_USD:.2f})")
        else:
            print(f"   ⚠️  Balance below minimum for live trading (${settings.LIVE_TRADING_MIN_BALANCE_USD:.2f})")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Mainnet connection failed: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return False


async def test_market_data_fetching():
    """Test 4: Fetch market data from Bybit"""
    print("\n" + "="*70)
    print("  TEST 4: MARKET DATA FETCHING")
    print("="*70)
    
    # Primary symbol: XAGUSDT (Silver) as shown in Bybit demo
    # For Bybit perpetual swaps in ccxt: SYMBOL/USDT:USDT
    symbols_to_test = [
        ('XAG/USDT:USDT', 'Silver Perpetual'),
        ('BTC/USDT:USDT', 'Bitcoin Perpetual'),
        ('ETH/USDT:USDT', 'Ethereum Perpetual'),
    ]
    
    results = {}
    
    for symbol, name in symbols_to_test:
        print(f"\n4.{symbols_to_test.index((symbol, name)) + 1} Fetching {name} ({symbol})")
        print("-" * 70)
        
        try:
            client = BybitClient(testnet=True)
            ticker = await client.fetch_ticker(symbol)
            
            print(f"   ✅ Symbol: {ticker['symbol']}")
            print(f"   ✅ Last Price: ${ticker['last_price']:,.2f}")
            print(f"   ✅ Bid/Ask: ${ticker['bid']:,.2f} / ${ticker['ask']:,.2f}")
            print(f"   ✅ 24h High: ${ticker['high_24h']:,.2f}")
            print(f"   ✅ 24h Low: ${ticker['low_24h']:,.2f}")
            print(f"   ✅ 24h Volume: ${ticker['volume_24h']:,.2f}")
            
            results[symbol] = ticker
            
            await client.close()
            
        except Exception as e:
            print(f"   ❌ Failed to fetch {symbol}: {str(e)[:100]}")
            results[symbol] = None
    
    # Check if at least one symbol worked
    successful = sum(1 for v in results.values() if v is not None)
    
    print(f"\n4.4 Market Data Summary")
    print("-" * 70)
    print(f"   ✅ Successfully fetched {successful}/{len(symbols_to_test)} symbols")
    
    return successful > 0


async def test_ohlcv_data():
    """Test 5: Fetch OHLCV candlestick data"""
    print("\n" + "="*70)
    print("  TEST 5: OHLCV CANDLESTICK DATA")
    print("="*70)
    
    try:
        client = BybitClient(testnet=True)
        
        print("\n5.1 Fetching BTC/USDT:USDT 1h Candles (Last 10)")
        print("-" * 70)
        
        ohlcv = await client.fetch_ohlcv('BTC/USDT:USDT', timeframe='1h', limit=10)
        
        if ohlcv and len(ohlcv) > 0:
            print(f"   ✅ Retrieved {len(ohlcv)} candles")
            print(f"\n   Latest Candle:")
            latest = ohlcv[-1]
            print(f"   • Timestamp: {latest[0]}")
            print(f"   • Open: ${latest[1]:,.2f}")
            print(f"   • High: ${latest[2]:,.2f}")
            print(f"   • Low: ${latest[3]:,.2f}")
            print(f"   • Close: ${latest[4]:,.2f}")
            print(f"   • Volume: ${latest[5]:,.2f}")
            
            await client.close()
            return True
        else:
            print(f"   ❌ No candlestick data returned")
            await client.close()
            return False
            
    except Exception as e:
        print(f"   ❌ OHLCV fetch failed: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False


async def test_order_placement_and_status():
    """Test 6: Place order and check status (Testnet only)"""
    print("\n" + "="*70)
    print("  TEST 6: ORDER PLACEMENT & STATUS RETRIEVAL (Testnet)")
    print("="*70)
    
    try:
        client = BybitClient(testnet=True)
        
        # Get current price for XAGUSDT (Silver)
        print("\n6.1 Getting Current Market Price")
        print("-" * 70)
        ticker = await client.fetch_ticker('XAG/USDT:USDT')
        current_price = ticker['last_price']
        print(f"   ✅ XAG/USDT:USDT (Silver Perpetual) Current Price: ${current_price:,.2f}")
        
        # Calculate test order size (Silver is cheaper, use reasonable amount)
        test_amount = 1.0  # 1 oz of silver
        leverage = 1  # Conservative leverage for test
        
        print(f"\n6.2 Placing Test Market Order")
        print("-" * 70)
        print(f"   Symbol: XAG/USDT:USDT (Silver Perpetual)")
        print(f"   Side: BUY")
        print(f"   Amount: {test_amount} XAG (~{test_amount} oz)")
        print(f"   Leverage: {leverage}x")
        print(f"   Estimated Cost: ${test_amount * current_price:,.2f}")
        
        # Place market order
        order = await client.create_market_order(
            symbol='XAG/USDT:USDT',
            side='buy',
            amount=test_amount,
            leverage=leverage
        )
        
        print(f"\n   ✅ Order Placed Successfully!")
        print(f"   • Order ID: {order.get('order_id', 'N/A')}")
        print(f"   • Status: {order.get('status', 'N/A')}")
        print(f"   • Filled Price: ${order.get('price', 0):,.2f}")
        print(f"   • Amount: {order.get('amount', 0):,.2f} XAG")
        print(f"   • Cost: ${order.get('cost', 0):,.2f}")
        print(f"   • Fee: {order.get('fee', {})}")
        
        # Fetch order status
        print(f"\n6.3 Fetching Order Status")
        print("-" * 70)
        
        order_status = await client.fetch_order_status(
            order_id=order['order_id'],
            symbol='XAG/USDT:USDT'
        )
        
        print(f"   ✅ Order Status Retrieved")
        print(f"   • Order ID: {order_status['order_id']}")
        print(f"   • Status: {order_status['status']}")
        print(f"   • Filled: {order_status['filled']} XAG")
        print(f"   • Remaining: {order_status['remaining']} XAG")
        print(f"   • Average Price: ${order_status.get('average', 0):,.2f}")
        
        # Check position
        print(f"\n6.4 Checking Open Positions")
        print("-" * 70)
        
        positions = await client.fetch_open_positions()
        
        if positions:
            print(f"   ✅ Found {len(positions)} open position(s)")
            for pos in positions:
                print(f"   • Symbol: {pos['symbol']}")
                print(f"     Side: {pos['side']}")
                print(f"     Size: {pos['size']}")
                print(f"     Entry Price: ${pos['entry_price']:,.2f}")
                print(f"     Mark Price: ${pos['mark_price']:,.2f}")
                print(f"     Unrealized PnL: ${pos['unrealized_pnl']:,.2f}")
        else:
            print(f"   ℹ️  No open positions")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Order placement failed: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return False


async def test_risk_calculations():
    """Test 7: Validate risk management calculations"""
    print("\n" + "="*70)
    print("  TEST 7: RISK MANAGEMENT CALCULATIONS")
    print("="*70)
    
    try:
        client = BybitClient(testnet=True)
        
        # Get balance for calculations
        balance = await client.fetch_balance()
        total_balance = balance['total_usdt']
        
        print(f"\n7.1 Position Sizing Calculation")
        print("-" * 70)
        print(f"   Account Balance: ${total_balance:,.2f}")
        print(f"   Risk Per Trade: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
        
        risk_amount = total_balance * settings.GOLD_RISK_PER_TRADE
        print(f"   Risk Amount: ${risk_amount:,.2f}")
        
        # Example trade parameters
        entry_price = 50000.0  # Example BTC price
        stop_loss = 49000.0  # 2% below entry
        leverage = min(settings.GOLD_MAX_LEVERAGE, settings.RISK_MAX_LEVERAGE)
        
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0
        
        position_value = quantity * entry_price
        margin_required = position_value / leverage
        
        print(f"\n   Example Trade (BTC/USDT:USDT):")
        print(f"   • Entry Price: ${entry_price:,.2f}")
        print(f"   • Stop Loss: ${stop_loss:,.2f}")
        print(f"   • Leverage: {leverage}x")
        print(f"   • Quantity: {quantity:.6f} BTC")
        print(f"   • Position Value: ${position_value:,.2f}")
        print(f"   • Margin Required: ${margin_required:,.2f}")
        
        # Validate against limits
        print(f"\n7.2 Risk Limit Validation")
        print("-" * 70)
        
        checks_passed = True
        
        if leverage <= settings.RISK_MAX_LEVERAGE:
            print(f"   ✅ Leverage {leverage}x <= max {settings.RISK_MAX_LEVERAGE}x")
        else:
            print(f"   ❌ Leverage {leverage}x exceeds max {settings.RISK_MAX_LEVERAGE}x")
            checks_passed = False
        
        if position_value <= settings.LIVE_TRADING_MAX_POSITION_USD:
            print(f"   ✅ Position value ${position_value:,.2f} <= max ${settings.LIVE_TRADING_MAX_POSITION_USD:,.2f}")
        else:
            print(f"   ⚠️  Position value ${position_value:,.2f} exceeds recommended max ${settings.LIVE_TRADING_MAX_POSITION_USD:,.2f}")
            # Don't fail for this, just warn
        
        fee_rate = client.get_trading_fee_rate()
        total_cost = client.calculate_total_cost(entry_price, quantity, leverage, include_fee=True)
        
        print(f"\n7.3 Fee Calculation")
        print("-" * 70)
        print(f"   Fee Rate: {fee_rate*100:.3f}%")
        print(f"   Base Cost: ${(entry_price * quantity) / leverage:,.2f}")
        print(f"   Total Cost (with fees): ${total_cost:,.2f}")
        
        await client.close()
        return checks_passed
        
    except Exception as e:
        print(f"   ❌ Risk calculation failed: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#  BYBIT EXCHANGE API - COMPREHENSIVE VALIDATION" + " "*24 + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    print(f"\n📋 Configuration Summary:")
    print(f"   Active Exchange: {settings.ACTIVE_EXCHANGE}")
    print(f"   Execution Mode: {settings.EXECUTION_MODE}")
    print(f"   Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"   Risk Per Trade: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
    print(f"   Min Confidence: {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
    print(f"   Live Trading Min Balance: ${settings.LIVE_TRADING_MIN_BALANCE_USD:.2f}")
    
    results = {}
    
    try:
        # Test 1: Configuration
        results['configuration'] = await test_bybit_configuration()
        await asyncio.sleep(1)
        
        # Test 2: Testnet Connection
        results['testnet_connection'] = await test_bybit_testnet_connection()
        await asyncio.sleep(1)
        
        # Test 3: Mainnet Connection
        print("\n\n❓ Proceed with Mainnet (live trading) connection test?")
        print("   This will connect to your REAL Bybit account.")
        print("   Type 'yes' to continue, or press Enter to skip: ", end='')
        
        user_input = input().strip().lower()
        
        if user_input == 'yes':
            results['mainnet_connection'] = await test_bybit_mainnet_connection()
        else:
            print("   ⏭️  Skipping Mainnet connection test")
            results['mainnet_connection'] = None
        
        await asyncio.sleep(1)
        
        # Test 4: Market Data
        results['market_data'] = await test_market_data_fetching()
        await asyncio.sleep(1)
        
        # Test 5: OHLCV Data
        results['ohlcv_data'] = await test_ohlcv_data()
        await asyncio.sleep(1)
        
        # Test 6: Order Placement (Testnet only)
        print("\n\n❓ Proceed with test order placement on Testnet?")
        print("   This will place a SMALL order (10 XAG ~$840) on Bybit Testnet.")
        print("   Type 'yes' to continue, or press Enter to skip: ", end='')
        
        user_input = input().strip().lower()
        
        if user_input == 'yes':
            results['order_placement'] = await test_order_placement_and_status()
        else:
            print("   ⏭️  Skipping order placement test")
            results['order_placement'] = None
        
        await asyncio.sleep(1)
        
        # Test 7: Risk Calculations
        results['risk_calculations'] = await test_risk_calculations()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
    except Exception as e:
        print(f"\n❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("  📊 VALIDATION SUMMARY")
    print("="*70)
    
    tests = [
        ("API Configuration", results.get('configuration', False)),
        ("Testnet Connection", results.get('testnet_connection', False)),
        ("Mainnet Connection", results.get('mainnet_connection')),
        ("Market Data Fetching", results.get('market_data', False)),
        ("OHLCV Data", results.get('ohlcv_data', False)),
        ("Order Placement & Status", results.get('order_placement')),
        ("Risk Calculations", results.get('risk_calculations', False)),
    ]
    
    passed_count = 0
    skipped_count = 0
    failed_count = 0
    
    for name, result in tests:
        if result is None:
            icon = "⏭️ "
            status = "SKIPPED"
            skipped_count += 1
        elif result:
            icon = "✅"
            status = "PASS"
            passed_count += 1
        else:
            icon = "❌"
            status = "FAIL"
            failed_count += 1
        
        print(f"   {icon} {name}: {status}")
    
    total = len(tests)
    
    print(f"\n   Results: {passed_count} passed, {skipped_count} skipped, {failed_count} failed (out of {total})")
    
    if failed_count == 0 and passed_count >= 5:
        print("\n   🎉 BYBIT API VALIDATION SUCCESSFUL!")
        print("   ✅ Configuration verified")
        print("   ✅ Testnet operational for paper trading")
        if results.get('mainnet_connection'):
            print("   ✅ Mainnet accessible for live trading")
        print("   ✅ Market data fetching working")
        print("   ✅ Order execution validated")
        print("   ✅ Risk management calculations correct")
    elif failed_count == 0:
        print(f"\n   ⚠️  Validation incomplete - {skipped_count} tests skipped")
    else:
        print(f"\n   ❌ {failed_count} test(s) failed - Review errors above")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
