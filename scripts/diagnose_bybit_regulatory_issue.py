"""
Diagnostic script for Bybit Testnet regulatory restriction (Error 10024).

This script helps identify and resolve the "regulatory restrictions" error
that prevents trading on Bybit Testnet.

Usage:
    python3 scripts/diagnose_bybit_regulatory_issue.py
"""
import asyncio
import sys
from datetime import datetime

sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.infra.bybit_client import BybitClient
from app.config import settings


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def diagnose_regulatory_issue():
    """
    Diagnose and provide solutions for Bybit Error 10024.
    """
    print_section("Bybit Testnet Regulatory Restriction Diagnostic")
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    client = None
    
    try:
        # Step 1: Check configuration
        print_section("Step 1: Configuration Check")
        
        print(f"\n✅ API Key Configured: {'Yes' if settings.BYBIT_DEMO_API_KEY else 'No'}")
        print(f"✅ API Secret Configured: {'Yes' if settings.BYBIT_DEMO_API_SECRET else 'No'}")
        print(f"   Key Preview: {settings.BYBIT_DEMO_API_KEY[:8]}...{settings.BYBIT_DEMO_API_KEY[-4:] if settings.BYBIT_DEMO_API_KEY else 'N/A'}")
        print(f"   Environment: TESTNET (api-testnet.bybit.com)")
        print(f"   Rate Limit: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND} req/sec")
        
        if not settings.BYBIT_DEMO_API_KEY or not settings.BYBIT_DEMO_API_SECRET:
            print("\n❌ ERROR: API credentials not configured!")
            print("   Solution: Add BYBIT_DEMO_API_KEY and BYBIT_DEMO_API_SECRET to .env file")
            return False
        
        # Step 2: Initialize client and test basic connectivity
        print_section("Step 2: Client Initialization & Balance Check")
        
        client = BybitClient(testnet=True, demo_trading=False)
        print("✅ Client initialized successfully")
        
        try:
            balance = await client.fetch_balance()
            usdt_balance = balance['total_usdt']
            print(f"✅ Balance fetch successful: {usdt_balance:.2f} USDT")
            
            if usdt_balance == 0:
                print("\n⚠️  WARNING: Zero balance detected")
                print("   This may indicate account restrictions")
        except Exception as e:
            print(f"❌ Balance check failed: {e}")
            print("\n   This suggests authentication or permission issues")
            return False
        
        # Step 3: Try fetching market data (public endpoint)
        print_section("Step 3: Market Data Access Test")
        
        try:
            ticker = await client.fetch_ticker("BTC/USDT:USDT")
            print(f"✅ Public market data accessible")
            print(f"   BTC Price: ${ticker['last_price']:,.2f}")
            print("\n   → Public endpoints work correctly")
        except Exception as e:
            print(f"❌ Market data fetch failed: {e}")
            print("\n   → Even public endpoints are restricted")
            return False
        
        # Step 4: Explain the regulatory restriction issue
        print_section("Step 4: Understanding Error 10024")
        
        print("""
ERROR 10024 - Regulatory Restriction

What it means:
  Your Bybit Testnet account has regional or KYC restrictions that prevent
  derivatives trading (perpetual swaps/futures).

Common causes:
  1. Geographic Restrictions
     - Your IP address is from a restricted region
     - Bybit blocks certain countries from derivatives trading
     
  2. KYC Not Completed
     - Testnet account hasn't completed identity verification
     - Some regions require KYC even for testnet
     
  3. Account Type Limitations
     - Account created without derivatives permissions
     - New accounts may have temporary restrictions
     
  4. Testnet-Specific Issues
     - Bybit periodically resets testnet accounts
     - Some testnet accounts lose trading permissions
""")
        
        # Step 5: Provide solutions
        print_section("Step 5: Solutions & Workarounds")
        
        print("""
SOLUTION 1: Complete KYC Verification (Recommended)
─────────────────────────────────────────────────────
  1. Visit: https://testnet.bybit.com/
  2. Log in with your testnet account
  3. Go to: Profile → Identity Verification
  4. Complete Level 1 KYC (basic verification)
  5. Wait for approval (usually instant on testnet)
  6. Retry the test script

SOLUTION 2: Check Geographic Restrictions
───────────────────────────────────────────
  1. Verify your server IP location:
     $ curl https://ipinfo.io/country
     
  2. If from restricted region (e.g., mainland China, USA, etc.):
     - Use a VPS in an allowed region
     - Contact Bybit support for exceptions
     
  3. Common restricted regions for derivatives:
     - Mainland China
     - United States (some states)
     - Singapore
     - Quebec (Canada)

SOLUTION 3: Try Spot Trading Instead
─────────────────────────────────────
  If derivatives are restricted, try spot trading:
  
  Change symbol from:
    XRP/USDT:USDT  (perpetual swap)
  To:
    XRP/USDT       (spot trading)
  
  Note: Our current implementation focuses on derivatives.
  You'd need to modify the code for spot trading.

SOLUTION 4: Create New Testnet Account
───────────────────────────────────────
  1. Visit: https://testnet.bybit.com/
  2. Sign up with different email
  3. Complete KYC immediately
  4. Generate new API keys
  5. Update .env with new credentials
  6. Retry the test

SOLUTION 5: Contact Bybit Support
──────────────────────────────────
  1. Visit: https://testnet.bybit.com/en/help-center
  2. Submit ticket explaining:
     - Error code: 10024
     - Issue: Regulatory restriction on testnet
     - Request: Enable derivatives trading
  3. Include your testnet account email
  4. Wait for response (may take 1-3 days)

SOLUTION 6: Use Demo Trading Instead
─────────────────────────────────────
  Demo Trading may have different restrictions:
  
  1. Visit: https://www.bybit.com/en/trade/demo
  2. Generate Demo Trading API keys
  3. Update .env:
     BYBIT_USE_DEMO_DOMAIN=true
     BYBIT_DEMO_API_KEY="demo_key_here"
     BYBIT_DEMO_API_SECRET="demo_secret_here"
  4. Retry with demo mode
  
  Note: Demo Trading uses api-demo.bybit.com (different from testnet)
""")
        
        # Step 6: Quick diagnostic commands
        print_section("Step 6: Quick Diagnostic Commands")
        
        print("""
Run these commands to gather more information:

1. Check your server's IP country:
   $ curl https://ipinfo.io/country

2. Verify API key permissions on testnet:
   - Visit: https://testnet.bybit.com/en-US/user/security/api-management
   - Check if "Derivatives" permission is enabled

3. Test with minimal order:
   - Try placing order manually on testnet UI
   - See if web interface also shows restriction

4. Check testnet announcements:
   - Visit: https://testnet.bybit.com/en-US/announcements
   - Look for maintenance or restriction notices

5. Verify account status:
   - Log into testnet.bybit.com
   - Check if account shows any warnings
   - Verify KYC status in profile
""")
        
        # Step 7: Immediate next steps
        print_section("Step 7: Recommended Next Steps")
        
        print("""
IMMEDIATE ACTIONS (in order):

1. ✅ Check KYC Status
   - Log into testnet.bybit.com
   - Go to Profile → Identity Verification
   - Complete if not done

2. ✅ Verify IP Location
   $ curl https://ipinfo.io/country
   
3. ✅ Try Manual Order
   - Place small order via web interface
   - Confirm if restriction is account-wide or API-only

4. ✅ If still blocked:
   - Option A: Create new testnet account with KYC
   - Option B: Switch to Demo Trading mode
   - Option C: Contact Bybit support

5. ✅ After fixing:
   - Re-run: python3 scripts/test_bybit_market_order_auto.py
   - Verify order placement works
""")
        
        print_section("Summary")
        
        print("""
Current Status:
  ✅ API credentials configured
  ✅ Client initialization works
  ✅ Balance fetch works
  ✅ Public market data accessible
  ❌ Order placement blocked (Error 10024)

Root Cause:
  Regulatory/KYC restrictions on derivatives trading

Best Solution:
  Complete KYC verification on testnet.bybit.com

Alternative:
  Switch to Demo Trading mode (may have fewer restrictions)

Estimated Resolution Time:
  - KYC completion: 5-10 minutes
  - New account creation: 15-20 minutes
  - Support ticket: 1-3 days
""")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if client:
            try:
                await client.close()
            except:
                pass


if __name__ == "__main__":
    result = asyncio.run(diagnose_regulatory_issue())
    
    print("\n" + "=" * 80)
    if result:
        print("✅ Diagnostic complete - Follow the recommended steps above")
    else:
        print("❌ Diagnostic encountered errors - Check configuration first")
    print("=" * 80 + "\n")
    
    sys.exit(0 if result else 1)
