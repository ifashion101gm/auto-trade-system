"""
Diagnostic script to investigate Bybit demo account balance discrepancy.
Tests various API endpoints to determine why balance shows $0.
"""
import asyncio
import ccxt.async_support as ccxt
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def diagnose_bybit_account():
    """Comprehensive diagnosis of Bybit account status."""
    
    print("\n" + "="*80)
    print("  BYBIT ACCOUNT DIAGNOSTIC TOOL")
    print("="*80)
    
    # Initialize exchange with mainnet (demo trading uses mainnet API)
    exchange = ccxt.bybit({
        'apiKey': settings.BYBIT_API_KEY,
        'secret': settings.BYBIT_API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
        }
    })
    
    try:
        # Test 1: Basic connectivity
        print("\n[TEST 1] Testing API Connectivity")
        print("-" * 80)
        try:
            await exchange.load_markets()
            print("✅ Successfully loaded markets")
            print(f"   Total markets available: {len(exchange.markets)}")
        except Exception as e:
            print(f"❌ Failed to load markets: {e}")
            return
        
        # Test 2: Fetch balance using standard endpoint
        print("\n[TEST 2] Standard Balance Endpoint (fetch_balance)")
        print("-" * 80)
        try:
            balance = await exchange.fetch_balance()
            usdt = balance.get('USDT', {})
            print(f"✅ Balance retrieved successfully")
            print(f"   USDT Total: ${usdt.get('total', 0):,.2f}")
            print(f"   USDT Free: ${usdt.get('free', 0):,.2f}")
            print(f"   USDT Used: ${usdt.get('used', 0):,.2f}")
            
            # Show all non-zero balances
            non_zero = {k: v for k, v in balance.items() 
                       if isinstance(v, dict) and v.get('total', 0) > 0}
            if non_zero:
                print(f"\n   Other balances:")
                for asset, info in non_zero.items():
                    if asset not in ['USDT', 'info', 'timestamp', 'datetime']:
                        print(f"   • {asset}: {info['total']}")
            else:
                print(f"   ℹ️  No non-zero balances found")
                
        except Exception as e:
            print(f"❌ Balance fetch failed: {e}")
        
        # Test 3: Try unified account endpoint (V5 API)
        print("\n[TEST 3] Unified Account Endpoint (V5 API)")
        print("-" * 80)
        try:
            # Bybit V5 unified account endpoint
            response = await exchange.private_get_v5_account_wallet_balance({
                'accountType': 'UNIFIED'
            })
            
            if response.get('retCode') == 0:
                print("✅ Unified account data retrieved")
                result = response.get('result', {})
                list_data = result.get('list', [])
                
                if list_data:
                    account = list_data[0]
                    print(f"   Account Type: {account.get('accountType')}")
                    print(f"   Margin Mode: {account.get('marginMode')}")
                    
                    # Get coin balances
                    coins = account.get('coin', [])
                    usdt_coin = next((c for c in coins if c.get('coin') == 'USDT'), None)
                    
                    if usdt_coin:
                        print(f"   USDT Wallet Balance: ${float(usdt_coin.get('walletBalance', 0)):,.2f}")
                        print(f"   USDT Available: ${float(usdt_coin.get('availableToWithdraw', 0)):,.2f}")
                        print(f"   USDT Locked: ${float(usdt_coin.get('locked', 0)):,.2f}")
                        print(f"   USDT Unrealized P&L: ${float(usdt_coin.get('unrealisedPnl', 0)):,.2f}")
                    else:
                        print(f"   ℹ️  USDT not found in coin list")
                        print(f"   Available coins: {[c.get('coin') for c in coins[:5]]}")
                else:
                    print(f"   ℹ️  No account data returned")
            else:
                print(f"❌ API error: {response.get('retMsg')}")
                
        except Exception as e:
            print(f"❌ Unified account endpoint failed: {e}")
            logger.debug(f"Unified account error details: {e}", exc_info=True)
        
        # Test 4: Check funding account
        print("\n[TEST 4] Funding Account Balance")
        print("-" * 80)
        try:
            response = await exchange.private_get_v5_account_wallet_balance({
                'accountType': 'FUND'
            })
            
            if response.get('retCode') == 0:
                print("✅ Funding account data retrieved")
                result = response.get('result', {})
                list_data = result.get('list', [])
                
                if list_data:
                    account = list_data[0]
                    coins = account.get('coin', [])
                    usdt_coin = next((c for c in coins if c.get('coin') == 'USDT'), None)
                    
                    if usdt_coin:
                        print(f"   USDT Funding Balance: ${float(usdt_coin.get('walletBalance', 0)):,.2f}")
                    else:
                        print(f"   ℹ️  No USDT in funding account")
            else:
                print(f"❌ API error: {response.get('retMsg')}")
                
        except Exception as e:
            print(f"❌ Funding account check failed: {e}")
        
        # Test 5: Check contract account
        print("\n[TEST 5] Contract (Derivatives) Account Balance")
        print("-" * 80)
        try:
            response = await exchange.private_get_v5_account_wallet_balance({
                'accountType': 'CONTRACT'
            })
            
            if response.get('retCode') == 0:
                print("✅ Contract account data retrieved")
                result = response.get('result', {})
                list_data = result.get('list', [])
                
                if list_data:
                    account = list_data[0]
                    coins = account.get('coin', [])
                    usdt_coin = next((c for c in coins if c.get('coin') == 'USDT'), None)
                    
                    if usdt_coin:
                        print(f"   USDT Contract Balance: ${float(usdt_coin.get('walletBalance', 0)):,.2f}")
                        print(f"   USDT Available: ${float(usdt_coin.get('availableToWithdraw', 0)):,.2f}")
                    else:
                        print(f"   ℹ️  No USDT in contract account")
            else:
                print(f"❌ API error: {response.get('retMsg')}")
                
        except Exception as e:
            print(f"❌ Contract account check failed: {e}")
        
        # Test 6: Check if demo mode is active
        print("\n[TEST 6] Demo Trading Status Check")
        print("-" * 80)
        print("ℹ️  Note: Bybit does not provide an API endpoint to check demo mode status")
        print("   Demo mode must be verified via web interface:")
        print("   https://www.bybit.com/en/trade/demo")
        print()
        print("   Indicators of Demo Mode:")
        print("   • Look for 'DEMO' badge in top-right corner")
        print("   • Balance should show virtual funds (e.g., 100M+ USDT)")
        print("   • Orders execute with virtual money")
        
        # Test 7: Check open orders
        print("\n[TEST 7] Open Orders Check")
        print("-" * 80)
        try:
            orders = await exchange.fetch_open_orders()
            print(f"✅ Retrieved {len(orders)} open orders")
            
            if orders:
                for order in orders[:5]:  # Show first 5
                    print(f"   • {order['symbol']}: {order['side']} {order['amount']} @ ${order['price']:,.2f}")
            else:
                print(f"   ℹ️  No open orders")
                
        except Exception as e:
            print(f"❌ Failed to fetch open orders: {e}")
        
        # Test 8: Check recent trades
        print("\n[TEST 8] Recent Trade History")
        print("-" * 80)
        try:
            trades = await exchange.fetch_my_trades(limit=5)
            print(f"✅ Retrieved {len(trades)} recent trades")
            
            if trades:
                for trade in trades:
                    print(f"   • {trade['symbol']}: {trade['side']} {trade['amount']} @ ${trade['price']:,.2f}")
            else:
                print(f"   ℹ️  No trade history")
                
        except Exception as e:
            print(f"❌ Failed to fetch trade history: {e}")
        
        # Test 9: Account upgrade status
        print("\n[TEST 9] Account Upgrade Status")
        print("-" * 80)
        try:
            response = await exchange.private_get_v5_account_upgrade_history()
            
            if response.get('retCode') == 0:
                print("✅ Account upgrade history retrieved")
                result = response.get('result', {})
                list_data = result.get('list', [])
                
                if list_data:
                    latest = list_data[0]
                    print(f"   Latest Upgrade: {latest.get('upgradeTime')}")
                    print(f"   Previous Mode: {latest.get('prevAccountMode')}")
                    print(f"   Current Mode: {latest.get('newAccountMode')}")
                else:
                    print(f"   ℹ️  No upgrade history")
            else:
                print(f"❌ API error: {response.get('retMsg')}")
                
        except Exception as e:
            print(f"❌ Upgrade status check failed: {e}")
        
        # Summary
        print("\n" + "="*80)
        print("  DIAGNOSTIC SUMMARY")
        print("="*80)
        print()
        print("If balance shows $0 but screenshot shows 100M+ USDT:")
        print()
        print("Possible Causes:")
        print("  1. API keys belong to different account than demo account")
        print("  2. Demo account requires separate API key generation")
        print("  3. Funds are in different sub-account")
        print("  4. Demo balance not accessible via standard API endpoints")
        print()
        print("Recommended Actions:")
        print("  1. Log into Bybit web interface")
        print("  2. Navigate to API Management")
        print("  3. Verify which account the API keys were generated from")
        print("  4. If needed, generate new API keys from demo account")
        print("  5. Ensure demo mode is activated at https://www.bybit.com/en/trade/demo")
        print()
        
    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(diagnose_bybit_account())
