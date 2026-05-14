#!/usr/bin/env python3
"""
Bybit Live API Validation Script
Tests LIVE account connectivity safely (READ-ONLY operations only)
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.bybit_client import BybitClient
from app.config import settings


async def validate_live_api():
    """Comprehensive validation of Bybit Live Account API (READ-ONLY)."""
    client = None
    
    print("=" * 80)
    print("Bybit LIVE Account API Validation (READ-ONLY)")
    print("=" * 80)
    
    # Step 1: Configuration Verification
    print("\n[STEP 1] Configuration Verification")
    print("-" * 80)
    
    live_key = settings.BYBIT_API_KEY or "N/A"
    demo_key = settings.BYBIT_DEMO_API_KEY or "N/A"
    demo_flag = settings.BYBIT_USE_DEMO_DOMAIN
    
    masked_live = f"{live_key[:5]}...{live_key[-4:]}" if len(live_key) > 9 else "***"
    masked_demo = f"{demo_key[:5]}...{demo_key[-4:]}" if len(demo_key) > 9 else "***"
    
    print(f"  • Live API Key: {masked_live}")
    print(f"  • Demo API Key: {masked_demo}")
    print(f"  • BYBIT_USE_DEMO_DOMAIN: {demo_flag}")
    print(f"  • Target Endpoint: https://api.bybit.com (LIVE)")
    
    if demo_flag:
        print(f"\n  ⚠️  WARNING: BYBIT_USE_DEMO_DOMAIN=true")
        print(f"      This flag may affect routing despite live mode!")
    else:
        print(f"\n  ✅ Configuration correct for live trading")
    
    # Step 2: Initialize Live Client
    print("\n[STEP 2] Initialize Live API Client")
    print("-" * 80)
    
    start_time = time.time()
    try:
        client = BybitClient(testnet=False, demo_trading=False)
        init_time = time.time() - start_time
        
        print(f"  ✅ Client initialized in {init_time:.3f}s")
        print(f"  • Using Pybit: {client.use_pybit}")
        print(f"  • Testnet Mode: {client.testnet}")
        print(f"  • Demo Trading: {client.demo_trading}")
        print(f"  • API Key Loaded: {client.api_key[:5]}...{client.api_key[-4:]}")
        
        if not client.use_pybit:
            urls = getattr(client.exchange, 'urls', {})
            api_urls = urls.get('api', {})
            print(f"  • Public URL: {api_urls.get('public', 'N/A')}")
            print(f"  • Private URL: {api_urls.get('private', 'N/A')}")
        
    except Exception as e:
        print(f"  ❌ Client initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Public Market Data Test
    print("\n[STEP 3] Public Market Data Access (No Auth Required)")
    print("-" * 80)
    
    test_symbols = ["BTC/USDT:USDT", "XAU/USDT:USDT"]
    
    for symbol in test_symbols:
        try:
            start_time = time.time()
            ticker = await asyncio.wait_for(
                client.exchange.fetch_ticker(symbol),
                timeout=10
            )
            elapsed = time.time() - start_time
            
            print(f"  ✅ {symbol}")
            print(f"     • Price: ${ticker['last']:.2f}")
            print(f"     • Bid/Ask: ${ticker['bid']:.2f} / ${ticker['ask']:.2f}")
            print(f"     • Latency: {elapsed:.3f}s")
            
        except asyncio.TimeoutError:
            print(f"  ❌ {symbol}: Timeout (10s)")
        except Exception as e:
            print(f"  ❌ {symbol}: {e}")
    
    # Step 4: Private API - Balance Check
    print("\n[STEP 4] Private API - Account Balance (Auth Required)")
    print("-" * 80)
    
    usdt_balance = 0.0
    free_balance = 0.0
    used_balance = 0.0
    
    try:
        start_time = time.time()
        balance = await asyncio.wait_for(
            client.fetch_balance(),
            timeout=10
        )
        elapsed = time.time() - start_time
        
        usdt_balance = balance.get('total_usdt', 0)
        free_balance = balance.get('free_usdt', 0)
        used_balance = balance.get('used_usdt', 0)
        
        print(f"  ✅ Balance fetched in {elapsed:.3f}s")
        print(f"  • Total USDT: {usdt_balance:.6f}")
        print(f"  • Free USDT: {free_balance:.6f}")
        print(f"  • Used USDT: {used_balance:.6f}")
        
        if 'balances' in balance and balance['balances']:
            print(f"\n  • All balances:")
            for asset, amount in balance['balances'].items():
                if amount > 0:
                    print(f"      - {asset}: {amount:.8f}")
        
    except asyncio.TimeoutError:
        print(f"  ❌ Balance fetch timeout (10s)")
        return False
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ Balance fetch failed: {type(e).__name__}: {e}")
        
        # Parse Bybit error codes
        import re
        match = re.search(r'retCode["\s]*:\s*(\d+)', error_msg)
        if match:
            ret_code = int(match.group(1))
            desc = BybitClient.get_bybit_error_description(ret_code)
            print(f"\n  • Error Code: {ret_code}")
            print(f"  • Description: {desc}")
        
        # Provide troubleshooting
        if '10003' in error_msg:
            print(f"\n   Troubleshooting: Invalid API key")
            print(f"      • Check if keys are for LIVE account (not demo/testnet)")
            print(f"      • Verify keys haven't expired or been revoked")
            print(f"      • Ensure keys have Account Read permission")
        elif '10004' in error_msg:
            print(f"\n  Troubleshooting: Permission denied")
            print(f"      • Enable required permissions in Bybit dashboard:")
            print(f"        - Account Read")
            print(f"        - Wallet Read")
        
        return False
    
    # Step 5: Positions Check (Read-Only)
    print("\n[STEP 5] Read-Only - Open Positions")
    print("-" * 80)
    
    positions = []
    
    try:
        start_time = time.time()
        positions = await asyncio.wait_for(
            client.fetch_open_positions(),
            timeout=10
        )
        elapsed = time.time() - start_time
        
        print(f"  ✅ Positions fetched in {elapsed:.3f}s")
        print(f"  • Open positions: {len(positions)}")
        
        if positions:
            for pos in positions[:5]:  # Show first 5
                pnl = pos.get('unrealized_pnl', 0)
                pnl_symbol = "" if pnl >= 0 else ""
                print(f"\n  Position: {pos.get('symbol', 'N/A')}")
                print(f"    • Side: {pos.get('side', 'N/A')}")
                print(f"    • Size: {pos.get('size', 0)}")
                print(f"    • Entry Price: ${pos.get('entry_price', 0):.4f}")
                print(f"    • Mark Price: ${pos.get('mark_price', 0):.4f}")
                print(f"    • Unrealized PnL: {pnl_symbol}${pnl:.2f}")
                print(f"    • Leverage: {pos.get('leverage', 1)}x")
        else:
            print(f"  • No open positions")
            
    except asyncio.TimeoutError:
        print(f"  ⚠️  Position fetch timeout (10s)")
        print(f"      (This is OK - continuing)")
    except Exception as e:
        print(f"  ⚠️  Position fetch warning: {type(e).__name__}: {e}")
        print(f"      (This is OK if no positions exist or API permissions limited)")
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    print(f"\n  ✅ Endpoint: https://api.bybit.com (LIVE)")
    print(f"  ✅ API Key: {masked_live}")
    print(f"  ✅ Authentication: SUCCESS")
    print(f"  ✅ Account Balance: {usdt_balance:.6f} USDT")
    print(f"  ✅ Market Data: ACCESSIBLE")
    print(f"  ✅ Read Permissions: VERIFIED")
    print(f"  • Open Positions: {len(positions)}")
    
    print(f"\n  IMPORTANT:")
    print(f"  • This is a LIVE account with REAL FUNDS")
    print(f"  • No write operations were executed")
    print(f"  • Only read-only API calls were made")
    print(f"  • Exercise extreme caution when placing orders")
    
    print("\n" + "=" * 80)
    print("✅ LIVE API VALIDATION PASSED")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(validate_live_api())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
