#!/usr/bin/env python3
"""Test Bybit Demo API connection using Pybit SDK"""
import asyncio
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Get demo API credentials
api_key = os.getenv("BYBIT_DEMO_API_KEY")
api_secret = os.getenv("BYBIT_DEMO_API_SECRET")

print("=" * 70)
print("Bybit Demo API Connection Test - Pybit SDK")
print("=" * 70)
print(f"API Key: {api_key[:10]}...{api_key[-5:]}")
print(f"API Secret: {api_secret[:10]}...{api_secret[-5:]}")
print(f"Demo Domain: {os.getenv('BYBIT_USE_DEMO_DOMAIN')}")
print(f"Client Library: {os.getenv('BYBIT_CLIENT_LIBRARY')}")
print()

# Test connection
try:
    session = HTTP(
        api_key=api_key,
        api_secret=api_secret,
        recv_window=5000,
        demo=True  # Enables api-demo.bybit.com
    )
    
    print("✅ Pybit session created successfully")
    print()
    
    # Test server time
    print("Testing server time...")
    server_time = session.get_server_time()
    if server_time.get('retCode') == 0:
        print(f"✅ Server time: {server_time.get('result', {}).get('timeSecond')}")
    else:
        print(f"❌ Server time failed: {server_time.get('retMsg')}")
    print()
    
    # Test balance endpoint
    print("Testing wallet balance...")
    balance = session.get_wallet_balance(accountType="UNIFIED")
    print(f"Response Code: {balance.get('retCode')}")
    print(f"Response Message: {balance.get('retMsg')}")
    
    if balance.get('retCode') == 0:
        result = balance.get('result', {})
        list_data = result.get('list', [])
        if list_data:
            for coin in list_data[0].get('coin', []):
                if coin.get('coin') == 'USDT':
                    usdt_balance = float(coin.get('walletBalance', 0))
                    print(f"✅ USDT Balance: ${usdt_balance:,.2f}")
        
        print("\n" + "=" * 70)
        print("✅ Connection successful - Pybit SDK working!")
        print("=" * 70)
        print("\n🎉 You can now proceed with trade execution.")
    else:
        print(f"\n❌ Connection failed: {balance.get('retMsg')}")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
