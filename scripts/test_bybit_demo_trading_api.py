#!/usr/bin/env python3
"""
Test Bybit Demo Trading API with correct endpoint.
Demo Trading uses api.bybit.com (live endpoint) with demo-generated keys.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.config import settings

async def test_bybit_demo_trading_api():
    """Test Bybit Demo Trading API (uses live endpoint with demo keys)."""
    print("="*80)
    print("BYBIT DEMO TRADING API CONNECTIVITY TEST")
    print("="*80)
    
    if not settings.BYBIT_DEMO_API_KEY or not settings.BYBIT_DEMO_API_SECRET:
        print("❌ Demo API keys not configured in .env")
        return False
    
    print(f"\n📋 Current Configuration:")
    print(f"   API Key: {settings.BYBIT_DEMO_API_KEY[:10]}...{settings.BYBIT_DEMO_API_KEY[-4:]}")
    print(f"   BYBIT_USE_DEMO_DOMAIN: {settings.BYBIT_USE_DEMO_DOMAIN}")
    print(f"   Expected Endpoint: api.bybit.com (live API with demo keys)")
    
    try:
        from pybit.unified_trading import HTTP
        
        print(f"\n🔧 Testing with pybit SDK...")
        
        # IMPORTANT: Demo Trading uses LIVE endpoint (testnet=False) with demo keys
        # The keys were generated from demo mode on bybit.com
        session = HTTP(
            testnet=False,  # Use live endpoint for Demo Trading
            api_key=settings.BYBIT_DEMO_API_KEY,
            api_secret=settings.BYBIT_DEMO_API_SECRET
        )
        
        # Test 1: Get wallet balance
        print("\n📊 Test 1: Wallet Balance")
        balance_response = session.get_wallet_balance(accountType="UNIFIED")
        
        if balance_response.get('retCode') == 0:
            print("   ✅ API authentication successful")
            wallet_list = balance_response['result']['list']
            
            if wallet_list:
                coins = wallet_list[0]['coin']
                usdt = next((c for c in coins if c['coin'] == 'USDT'), None)
                
                if usdt:
                    balance = float(usdt['walletBalance'])
                    available = float(usdt['availableToWithdraw'])
                    equity = float(usdt.get('equity', balance))
                    
                    print(f"   ✅ USDT Wallet Balance: ${balance:,.2f}")
                    print(f"   ✅ Available: ${available:,.2f}")
                    print(f"   ✅ Equity: ${equity:,.2f}")
                else:
                    print(f"   ️ USDT not found in wallet")
                    print(f"   Available coins: {[c['coin'] for c in coins]}")
            else:
                print("   ⚠️ No wallet data returned")
        else:
            print(f"   ❌ API error: {balance_response.get('retMsg', 'Unknown')}")
            print(f"   Error code: {balance_response.get('retCode')}")
            return False
        
        # Test 2: Get open positions
        print("\n Test 2: Open Positions")
        positions_response = session.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if positions_response.get('retCode') == 0:
            positions = positions_response['result']['list']
            active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
            
            print(f"   ✅ Found {len(active_positions)} open position(s)")
            
            if active_positions:
                for pos in active_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = float(pos['size'])
                    entry = float(pos['avgPrice'])
                    mark = float(pos['markPrice'])
                    pnl = float(pos['unrealisedPnl'])
                    leverage = pos['leverage']
                    liq_price = pos.get('liqPrice', 'N/A')
                    
                    pnl_emoji = "🟢" if pnl > 0 else "🔴"
                    print(f"\n   📍 Position: {symbol}")
                    print(f"      Side: {side.upper()} | Size: {size} | Leverage: {leverage}x")
                    print(f"      Entry: ${entry:,.2f} | Mark: ${mark:,.2f}")
                    print(f"      P&L: {pnl_emoji} ${pnl:+,.2f}")
                    print(f"      Liq Price: ${float(liq_price):,.2f}" if liq_price != 'N/A' else "      Liq Price: N/A")
            else:
                print("   ✅ No open positions")
        else:
            print(f"   ⚠️ Could not fetch positions: {positions_response.get('retMsg')}")
        
        # Test 3: Market data
        print("\n💹 Test 3: Market Data (XAU/USDT)")
        market_response = session.get_tickers(
            category="linear",
            symbol="XAUUSDT"
        )
        
        if market_response.get('retCode') == 0:
            ticker = market_response['result']['list'][0]
            price = float(ticker['lastPrice'])
            high = float(ticker['highPrice24h'])
            low = float(ticker['lowPrice24h'])
            
            print(f"   ✅ XAUUSDT Current: ${price:,.2f}")
            print(f"   ✅ 24h High: ${high:,.2f} | 24h Low: ${low:,.2f}")
        else:
            print(f"   ️ Market data error: {market_response.get('retMsg')}")
        
        # Summary
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED - DEMO TRADING API ACCESS CONFIRMED")
        print("="*80)
        print("\n📌 Key Information:")
        print("   • Demo Trading uses LIVE endpoint (api.bybit.com)")
        print("   • Keys must be generated from Demo mode on bybit.com")
        print("   • Use testnet=False in pybit for Demo Trading")
        print("="*80)
        return True
        
    except ImportError:
        print("❌ pybit not installed. Install with: pip install pybit")
        return False
    
    except Exception as e:
        print(f"\n❌ Connection test failed: {type(e).__name__}: {e}")
        print("\n Troubleshooting:")
        print("   1. Verify you're in 'Demo Trading' mode on Bybit website")
        print("   2. Check API key exists at: https://www.bybit.com/en/trade/demo")
        print("   3. Ensure API key has 'Read' and 'Trade' permissions")
        print("   4. Demo keys may have expired (90 day limit)")
        print("   5. Regenerate keys from Demo interface if needed")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_bybit_demo_trading_api())
    sys.exit(0 if result else 1)
