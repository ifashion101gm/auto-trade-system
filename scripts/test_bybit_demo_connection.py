#!/usr/bin/env python3
"""
Bybit Demo Environment Connection Test using pybit SDK.

This script validates:
1. Configuration settings (.env)
2. pybit SDK installation and imports
3. API authentication with demo credentials
4. Connectivity to api-demo.bybit.com
5. Basic API operations (server time, balance, ticker)

Usage:
    python scripts/test_bybit_demo_connection.py
"""

import sys
import time
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "="*70)
    print(f" {title}")
    print("="*70)

def print_success(message: str):
    """Print success message."""
    print(f"✅ {message}")

def print_error(message: str):
    """Print error message."""
    print(f"❌ {message}")

def print_warning(message: str):
    """Print warning message."""
    print(f"️  {message}")

def print_info(message: str):
    """Print info message."""
    print(f"ℹ️  {message}")

def test_configuration():
    """Test 1: Validate environment configuration."""
    print_section("TEST 1: Configuration Validation")
    
    try:
        from app.config import settings
        
        # Check required settings
        checks = {
            'BYBIT_CLIENT_LIBRARY': settings.BYBIT_CLIENT_LIBRARY,
            'BYBIT_USE_DEMO_DOMAIN': settings.BYBIT_USE_DEMO_DOMAIN,
            'BYBIT_DEMO_API_KEY': settings.BYBIT_DEMO_API_KEY,
            'BYBIT_DEMO_API_SECRET': settings.BYBIT_DEMO_API_SECRET,
            'BYBIT_RECV_WINDOW': settings.BYBIT_RECV_WINDOW,
            'BYBIT_RATE_LIMIT_CALLS_PER_SECOND': settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND,
        }
        
        print_info("Configuration values loaded from .env:")
        for key, value in checks.items():
            if 'SECRET' in key or 'KEY' in key:
                display_value = f"{str(value)[:10]}..." if value else "NOT SET"
            else:
                display_value = value
            status = "✅" if value else "❌"
            print(f"  {status} {key}: {display_value}")
        
        # Validate critical settings
        if not settings.BYBIT_DEMO_API_KEY:
            print_error("BYBIT_DEMO_API_KEY is NOT SET")
            return False
        
        if not settings.BYBIT_DEMO_API_SECRET:
            print_error("BYBIT_DEMO_API_SECRET is NOT SET")
            return False
        
        if not settings.BYBIT_USE_DEMO_DOMAIN:
            print_warning("BYBIT_USE_DEMO_DOMAIN is False - will use live domain!")
            return False
        
        if settings.BYBIT_CLIENT_LIBRARY != 'pybit':
            print_error(f"BYBIT_CLIENT_LIBRARY should be 'pybit', got '{settings.BYBIT_CLIENT_LIBRARY}'")
            return False
        
        print_success("Configuration validation PASSED")
        return True
        
    except Exception as e:
        print_error(f"Configuration validation FAILED: {e}")
        return False

def test_pybit_import():
    """Test 2: Validate pybit SDK installation."""
    print_section("TEST 2: pybit SDK Import")
    
    try:
        from pybit.unified_trading import HTTP as PybitHTTP
        print_success("pybit.unified_trading.HTTP imported successfully")
        
        import pybit
        print_info(f"pybit version: {getattr(pybit, '__version__', 'unknown')}")
        return True
        
    except ImportError as e:
        print_error(f"pybit SDK not installed: {e}")
        print_info("Install with: pip install pybit")
        return False
    except Exception as e:
        print_error(f"pybit import FAILED: {e}")
        return False

def test_demo_connection():
    """Test 3: Connect to Bybit Demo environment and fetch server time."""
    print_section("TEST 3: Demo Connection Test (Server Time)")
    
    try:
        from app.config import settings
        from pybit.unified_trading import HTTP as PybitHTTP
        
        print_info(f"Connecting to: https://api-demo.bybit.com")
        print_info(f"API Key: {settings.BYBIT_DEMO_API_KEY[:10]}...")
        print_info(f"Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
        
        # Initialize Pybit session with demo=True
        session = PybitHTTP(
            api_key=settings.BYBIT_DEMO_API_KEY,
            api_secret=settings.BYBIT_DEMO_API_SECRET,
            recv_window=settings.BYBIT_RECV_WINDOW,
            demo=True  # This tells pybit to use api-demo.bybit.com
        )
        
        print_info("Pybit HTTP session created successfully")
        
        # Test public endpoint: Fetch server time
        print_info("Fetching server time (public endpoint)...")
        response = session.get_server_time()
        
        if response.get('retCode') == 0:
            server_time = response.get('result', {}).get('timeSecond')
            server_time_ms = response.get('result', {}).get('timeNano')
            print_success(f"Server time retrieved: {server_time} (epoch seconds)")
            
            # Check clock sync
            local_time = int(time.time())
            time_diff = abs(int(server_time) - local_time)
            
            if time_diff <= 5:
                print_success(f"Clock synchronized: difference={time_diff}s")
            else:
                print_warning(f"Clock sync warning: difference={time_diff}s (should be <5s)")
            
            return True, session
        else:
            ret_code = response.get('retCode')
            ret_msg = response.get('retMsg', 'Unknown error')
            print_error(f"Server time request failed: retCode={ret_code}, retMsg={ret_msg}")
            
            # Get error description
            from app.infra.bybit_client import BybitClient
            description = BybitClient.get_bybit_error_description(ret_code)
            print_error(f"Description: {description}")
            
            return False, None
            
    except Exception as e:
        print_error(f"Demo connection test FAILED: {type(e).__name__}")
        print_error(f"Error: {str(e)}")
        return False, None

def test_authentication(session):
    """Test 4: Test authenticated endpoints (wallet balance)."""
    print_section("TEST 4: Authentication Test (Wallet Balance)")
    
    if not session:
        print_error("No valid session available")
        return False
    
    try:
        print_info("Fetching unified wallet balance (private endpoint)...")
        response = session.get_wallet_balance(accountType="UNIFIED")
        
        if response.get('retCode') == 0:
            print_success("Authentication successful!")
            
            # Extract balance info
            result = response.get('result', {})
            list_data = result.get('list', [])
            
            if list_data:
                account = list_data[0]
                total_balance = float(account.get('totalEquity', 0))
                print_info(f"Total Equity: ${total_balance:,.2f} USDT")
                
                # Show coin balances
                coins = account.get('coin', [])
                usdt_balance = 0
                
                for coin in coins:
                    if coin.get('coin') == 'USDT':
                        usdt_balance = float(coin.get('walletBalance', 0))
                        print_info(f"USDT Wallet Balance: ${usdt_balance:,.2f}")
                        break
                
                # Show balance breakdown
                print_info(f"Available Balance: ${float(account.get('availableToBorrow', 0)):,.2f}")
                print_info(f"Unrealized P&L: ${float(account.get('unrealisedPnl', 0)):,.2f}")
                
            return True
        else:
            ret_code = response.get('retCode')
            ret_msg = response.get('retMsg', 'Unknown error')
            print_error(f"Wallet balance request failed: retCode={ret_code}")
            print_error(f"Message: {ret_msg}")
            
            # Detailed error analysis
            from app.infra.bybit_client import BybitClient
            description = BybitClient.get_bybit_error_description(ret_code)
            print_error(f"Description: {description}")
            
            if ret_code == 10003:
                print_error("\n🔑 AUTHENTICATION FAILED (Error 10003)")
                print_error("Possible causes:")
                print_error("  1. API key/secret incorrect or expired")
                print_error("  2. API key generated from LIVE environment, not Demo")
                print_error("  3. API key lacks required permissions")
                print_error("  4. IP restriction blocking this server")
                print_info("\n💡 Solution:")
                print_info("  1. Go to https://www.bybit.com/en/trade/demo")
                print_info("  2. Navigate to API Management in Demo environment")
                print_info("  3. Create new API keys WITHIN the Demo interface")
                print_info("  4. Ensure 'Order - Trade' permission is enabled")
                print_info("  5. Add IP whitelist: 47.84.5.196 (optional but recommended)")
                print_info("  6. Update .env with new keys")
            
            elif ret_code == 10004:
                print_error("\n🔒 PERMISSIONS ERROR (Error 10004)")
                print_error("API key lacks required permissions")
                print_info("\n💡 Required permissions:")
                print_info("  - Order - Trade (Spot & Derivatives)")
                print_info("  - Position - Read & Write")
                print_info("  - Account - Read")
                print_info("  - Wallet - Read")
            
            elif ret_code == 10005:
                print_error("\n🌐 IP RESTRICTION (Error 10005)")
                print_error("IP address not whitelisted")
                print_info("\n💡 Solution:")
                print_info("  1. Get your server IP: curl https://api.ipify.org")
                print_info("  2. Add this IP to API key whitelist in Bybit dashboard")
            
            return False
            
    except Exception as e:
        print_error(f"Authentication test FAILED: {type(e).__name__}")
        print_error(f"Error: {str(e)}")
        return False

def test_market_data(session):
    """Test 5: Fetch market data for XAUUSDT."""
    print_section("TEST 5: Market Data Test (XAUUSDT Ticker)")
    
    if not session:
        print_error("No valid session available")
        return False
    
    try:
        symbol = "XAUUSDT"
        print_info(f"Fetching ticker for {symbol}...")
        
        response = session.get_tickers(
            category="linear",
            symbol=symbol
        )
        
        if response.get('retCode') == 0:
            result = response.get('result', {})
            list_data = result.get('list', [])
            
            if list_data:
                ticker = list_data[0]
                last_price = float(ticker.get('lastPrice', 0))
                bid_price = float(ticker.get('bid1Price', 0))
                ask_price = float(ticker.get('ask1Price', 0))
                high_24h = float(ticker.get('highPrice24h', 0))
                low_24h = float(ticker.get('lowPrice24h', 0))
                volume_24h = float(ticker.get('volume24h', 0))
                
                print_success(f"Market data retrieved for {symbol}")
                print_info(f"Last Price: ${last_price:,.2f}")
                print_info(f"Bid: ${bid_price:,.2f}")
                print_info(f"Ask: ${ask_price:,.2f}")
                print_info(f"Spread: ${(ask_price - bid_price):,.2f} ({((ask_price - bid_price) / bid_price * 100):.4f}%)")
                print_info(f"24h High: ${high_24h:,.2f}")
                print_info(f"24h Low: ${low_24h:,.2f}")
                print_info(f"24h Volume: {volume_24h:,.0f}")
                
                return True
            else:
                print_error(f"No ticker data found for {symbol}")
                return False
        else:
            ret_code = response.get('retCode')
            ret_msg = response.get('retMsg', 'Unknown error')
            print_error(f"Ticker request failed: retCode={ret_code}, retMsg={ret_msg}")
            return False
            
    except Exception as e:
        print_error(f"Market data test FAILED: {type(e).__name__}")
        print_error(f"Error: {str(e)}")
        return False

def test_positions(session):
    """Test 6: Check for existing positions."""
    print_section("TEST 6: Position Check")
    
    if not session:
        print_error("No valid session available")
        return False
    
    try:
        print_info("Fetching open positions for XAUUSDT...")
        
        response = session.get_positions(
            category="linear",
            symbol="XAUUSDT"
        )
        
        if response.get('retCode') == 0:
            result = response.get('result', {})
            positions = result.get('list', [])
            
            if positions:
                print_info(f"Found {len(positions)} open position(s):")
                for pos in positions:
                    try:
                        side = pos.get('side')
                        size_str = pos.get('size', '0')
                        size = float(size_str) if size_str else 0
                        
                        if size == 0:
                            continue  # Skip empty positions
                        
                        entry_price = float(pos.get('avgPrice', 0) or 0)
                        mark_price = float(pos.get('markPrice', 0) or 0)
                        unrealized_pnl = float(pos.get('unrealisedPnl', 0) or 0)
                        leverage = int(float(pos.get('leverage', 1) or 1))
                        
                        print_info(f"  {side} | Size: {size} | Entry: ${entry_price:,.2f} | "
                                  f"Mark: ${mark_price:,.2f} | P&L: ${unrealized_pnl:+.2f} | "
                                  f"Lev: {leverage}x")
                    except (ValueError, TypeError) as e:
                        print_warning(f"Skipping malformed position data: {e}")
            else:
                print_info("No open positions found")
            
            return True
        else:
            ret_code = response.get('retCode')
            ret_msg = response.get('retMsg', 'Unknown error')
            print_error(f"Position check failed: retCode={ret_code}, retMsg={ret_msg}")
            return False
            
    except Exception as e:
        print_error(f"Position check FAILED: {type(e).__name__}")
        print_error(f"Error: {str(e)}")
        return False

def main():
    """Run all connection tests."""
    print("\n" + "#"*70)
    print("# BYBIT DEMO ENVIRONMENT CONNECTION TEST")
    print("#"*70)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print(f"Python: {sys.version}")
    print(f"VPS IP: (checking...)")
    
    # Get VPS IP
    try:
        import urllib.request
        vps_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf-8')
        print(f"VPS IP: {vps_ip}")
    except:
        print("VPS IP: (unable to detect)")
    
    results = {
        'config': False,
        'import': False,
        'connection': False,
        'auth': False,
        'market': False,
        'positions': False,
    }
    
    # Test 1: Configuration
    results['config'] = test_configuration()
    
    # Test 2: Import
    results['import'] = test_pybit_import()
    
    # Test 3: Connection (Server Time)
    connection_success, session = test_demo_connection()
    results['connection'] = connection_success
    
    # Test 4: Authentication (if connection successful)
    if connection_success and session:
        results['auth'] = test_authentication(session)
    else:
        print_section("TEST 4: Authentication Test (SKIPPED)")
        print_error("Cannot test authentication without valid connection")
        results['auth'] = False
    
    # Test 5: Market Data (if connection successful)
    if connection_success and session:
        results['market'] = test_market_data(session)
    else:
        print_section("TEST 5: Market Data Test (SKIPPED)")
        print_error("Cannot test market data without valid connection")
        results['market'] = False
    
    # Test 6: Positions (if connection successful)
    if connection_success and session:
        results['positions'] = test_positions(session)
    else:
        print_section("TEST 6: Position Check (SKIPPED)")
        print_error("Cannot check positions without valid connection")
        results['positions'] = False
    
    # Summary
    print_section("TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name.upper()}: {status}")
    
    print("\n" + "-"*70)
    print(f"Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED - Bybit Demo environment is fully operational!")
        print("\nNext steps:")
        print("  1. Run validation cycle: python scripts/cleanup_and_restart_bybit_demo_cycle.py")
        print("  2. Monitor Telegram for trade notifications")
        print("  3. Check database: SELECT * FROM paper_trades WHERE exchange='bybit';")
        return 0
    else:
        print("\n⚠️  Some tests failed - review errors above")
        
        if not results['connection']:
            print("\n🔧 Connection Issue Detected:")
            print("  - Check if demo API keys are valid (generated from demo environment)")
            print("  - Verify IP is whitelisted if restriction is enabled")
            print("  - Ensure system clock is synchronized")
        elif not results['auth']:
            print("\n🔧 Authentication Issue Detected:")
            print("  - Verify API key permissions include Wallet Read")
            print("  - Check if API key has expired")
            print("  - Regenerate keys if necessary")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
