#!/usr/bin/env python3
"""
Direct Bybit Live API Test using pybit SDK.
Tests authentication and basic API calls.
"""
import sys
from pathlib import Path
from pybit.unified_trading import HTTP

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def test_live_api():
    """Test live API connection using pybit directly."""
    
    print("=" * 70)
    print("Bybit LIVE API Direct Test (pybit SDK)")
    print("=" * 70)
    
    api_key = settings.BYBIT_API_KEY
    api_secret = settings.BYBIT_API_SECRET
    
    print(f"\nAPI Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"Endpoint: https://api.bybit.com")
    
    try:
        # Initialize pybit session for LIVE trading
        print("\n[1/3] Initializing pybit HTTP session...")
        session = HTTP(
            testnet=False,  # LIVE mode
            demo=False,     # Not demo
            api_key=api_key,
            api_secret=api_secret,
            recv_window=5000
        )
        print("✅ Session created")
        
        # Test 1: Get server time (public endpoint)
        print("\n[2/3] Testing public endpoint (server time)...")
        response = session.get_server_time()
        
        if response.get('retCode') == 0:
            timestamp = response.get('result', {}).get('timeSecond', 'N/A')
            print(f"✅ Server time: {timestamp}")
        else:
            print(f"❌ Server time failed: {response.get('retMsg')}")
            return False
        
        # Test 2: Get wallet balance (private endpoint - requires auth)
        print("\n[3/3] Testing private endpoint (wallet balance)...")
        response = session.get_wallet_balance(accountType="UNIFIED")
        
        ret_code = response.get('retCode')
        
        if ret_code == 0:
            result = response.get('result', {})
            list_data = result.get('list', [])
            
            if list_data:
                account = list_data[0]
                coin_list = account.get('coin', [])
                
                usdt_balance = 0
                for coin_data in coin_list:
                    if coin_data.get('coin') == 'USDT':
                        wallet_balance = coin_data.get('walletBalance', '0')
                        usdt_balance = float(wallet_balance) if wallet_balance else 0
                        break
                
                print(f"✅ Authentication SUCCESS")
                print(f"✅ USDT Balance: {usdt_balance:.2f} USDT")
                
                if usdt_balance == 0:
                    print(f"   ℹ️  Account balance is 0 (expected for new/test account)")
                
            else:
                print(f"✅ Authentication SUCCESS")
                print(f"⚠️  No account data returned")
                
        elif ret_code == 10003:
            print(f"❌ Error 10003: Invalid API key")
            print(f"   Check BYBIT_API_KEY and BYBIT_API_SECRET in .env")
            print(f"   Ensure keys are for LIVE account (not testnet/demo)")
            return False
            
        elif ret_code == 10002:
            print(f"❌ Error 10002: Invalid parameters")
            print(f"   Check API key format")
            return False
            
        elif ret_code == 10004:
            print(f"❌ Error 10004: Permission denied")
            print(f"   Enable 'Account Read' and 'Wallet Read' permissions")
            return False
            
        elif ret_code == 10024:
            print(f"❌ Error 10024: Regulatory restriction")
            print(f"   Account has geographic/KYC restrictions")
            return False
            
        else:
            error_msg = response.get('retMsg', 'Unknown error')
            print(f"❌ Error {ret_code}: {error_msg}")
            return False
        
        print("\n" + "=" * 70)
        print("✅ LIVE API CONNECTION VERIFIED")
        print("=" * 70)
        print(f"\nStatus:")
        print(f"  • Endpoint: https://api.bybit.com")
        print(f"  • Authentication: ✅ Working")
        print(f"  • API Keys: ✅ Valid")
        print(f"  • Permissions: ✅ Sufficient")
        print(f"  • Balance: {usdt_balance:.2f} USDT")
        
        print(f"\n⚠️  This is a LIVE account - use caution with real orders!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_live_api()
    sys.exit(0 if success else 1)
