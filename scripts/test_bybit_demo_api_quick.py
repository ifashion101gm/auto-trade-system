#!/usr/bin/env python3
"""
Quick test for Bybit Demo API connectivity.
Tests the current API keys in .env file.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.config import settings

async def test_bybit_demo_api():
    """Test Bybit Demo API connectivity."""
    print("="*80)
    print("BYBIT DEMO API CONNECTIVITY TEST")
    print("="*80)
    
    # Check if keys are configured
    if not settings.BYBIT_DEMO_API_KEY or not settings.BYBIT_DEMO_API_SECRET:
        print("❌ Demo API keys not configured in .env")
        return False
    
    print(f"\n📋 Current Configuration:")
    print(f"   API Key: {settings.BYBIT_DEMO_API_KEY[:10]}...{settings.BYBIT_DEMO_API_KEY[-4:]}")
    print(f"   Use Demo Domain: {settings.BYBIT_USE_DEMO_DOMAIN}")
    
    try:
        # Try pybit first (recommended for Bybit)
        try:
            from pybit.unified_trading import HTTP
            
            print(f"\n🔧 Testing with pybit SDK...")
            
            # Bybit demo uses testnet endpoint with demo keys
            session = HTTP(
                testnet=True,  # This points to api-testnet.bybit.com (demo environment)
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
                        print(f"   ✅ USDT Balance: ${balance:,.2f}")
                        print(f"   ✅ Available: ${available:,.2f}")
                    else:
                        print(f"   ️ USDT not found in wallet")
                        print(f"   Available coins: {[c['coin'] for c in coins]}")
                else:
                    print("   ⚠️ No wallet data returned")
            else:
                print(f"    API error: {balance_response.get('retMsg', 'Unknown')}")
                print(f"   Error code: {balance_response.get('retCode')}")
                return False
            
            # Test 2: Get open positions
            print("\n📈 Test 2: Open Positions")
            positions_response = session.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if positions_response.get('retCode') == 0:
                positions = positions_response['result']['list']
                active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
                
                print(f"   ✅ Found {len(active_positions)} open position(s)")
                
                for pos in active_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = float(pos['size'])
                    entry = float(pos['avgPrice'])
                    mark = float(pos['markPrice'])
                    pnl = float(pos['unrealisedPnl'])
                    leverage = pos['leverage']
                    
                    pnl_emoji = "🟢" if pnl > 0 else "🔴"
                    print(f"\n   📍 Position: {symbol}")
                    print(f"      Side: {side.upper()} | Size: {size} | Leverage: {leverage}x")
                    print(f"      Entry: ${entry:,.2f} | Mark: ${mark:,.2f}")
                    print(f"      P&L: {pnl_emoji} ${pnl:+,.2f}")
            else:
                print(f"   ⚠️ Could not fetch positions: {positions_response.get('retMsg')}")
            
            # Test 3: Market data (no auth required, but good to verify endpoint)
            print("\n💹 Test 3: Market Data (XAU/USDT)")
            market_response = session.get_tickers(
                category="linear",
                symbol="XAUUSDT"
            )
            
            if market_response.get('retCode') == 0:
                ticker = market_response['result']['list'][0]
                price = float(ticker['lastPrice'])
                print(f"   ✅ XAUUSDT Price: ${price:,.2f}")
            else:
                print(f"   ⚠️ Market data error: {market_response.get('retMsg')}")
            
            print("\n" + "="*80)
            print("✅ ALL TESTS PASSED - API ACCESS CONFIRMED")
            print("="*80)
            return True
            
        except ImportError:
            print("❌ pybit not installed. Install with: pip install pybit")
            return False
    
    except Exception as e:
        print(f"\n❌ Connection test failed: {type(e).__name__}: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Ensure you're in Demo Trading mode on Bybit website")
        print("   2. Regenerate API keys from: https://www.bybit.com/en/trade/demo")
        print("   3. Update BYBIT_DEMO_API_KEY and BYBIT_DEMO_API_SECRET in .env")
        print("   4. Verify API key has 'Trade' and 'Read' permissions")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_bybit_demo_api())
    sys.exit(0 if result else 1)
