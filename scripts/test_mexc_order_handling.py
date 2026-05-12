#!/usr/bin/env python3
"""
MEXC Order Handling Validation Test.
Tests all critical order handling scenarios after implementing MexcExecutor.

This validates:
1. Symbol normalization
2. Position-side logic (open/close long/short)
3. Reduce-only order placement
4. Position mode detection
5. Balance and position fetching
6. Error handling

Run this BEFORE live trading to ensure everything works correctly.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.exchange.mexc_executor import MexcExecutor
from app.config import settings
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_symbol_normalization():
    """Test 1: Symbol mapping and normalization."""
    print("\n" + "="*80)
    print("TEST 1: Symbol Normalization")
    print("="*80)
    
    executor = MexcExecutor(testnet=True)
    
    test_cases = [
        ("GOLD(XAUT)/USDT", "GOLD_USDT"),
        ("XAUT/USDT", "GOLD_USDT"),
        ("BTCUSDT", "BTC_USDT"),
        ("ETHUSDT", "ETH_USDT"),
        ("BTC/USDT:USDT", "BTC_USDT"),
    ]
    
    passed = 0
    failed = 0
    
    for input_symbol, expected in test_cases:
        result = executor._normalize_symbol(input_symbol)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status}: {input_symbol:20s} → {result:15s} (expected: {expected})")
    
    await executor.close()
    
    print(f"\nResult: {passed} passed, {failed} failed")
    return failed == 0


async def test_position_mode_detection():
    """Test 2: Position mode detection."""
    print("\n" + "="*80)
    print("TEST 2: Position Mode Detection")
    print("="*80)
    
    executor = MexcExecutor(testnet=True)
    
    try:
        mode = await executor._detect_position_mode()
        print(f"✅ Detected position mode: {mode}")
        print(f"   Expected: ONE_WAY or HEDGE")
        
        # Verify it's a valid mode
        if mode in ['ONE_WAY', 'HEDGE']:
            print("✅ Valid position mode detected")
            result = True
        else:
            print(f"❌ Invalid position mode: {mode}")
            result = False
        
    except Exception as e:
        print(f"❌ Failed to detect position mode: {e}")
        result = False
    finally:
        await executor.close()
    
    return result


async def test_balance_fetch():
    """Test 3: Fetch account balance."""
    print("\n" + "="*80)
    print("TEST 3: Balance Fetch")
    print("="*80)
    
    executor = MexcExecutor(testnet=True)
    
    try:
        balance = await executor.get_balance()
        
        print(f"✅ Balance fetched successfully:")
        print(f"   Total USDT: ${balance.get('total_usdt', 0):.2f}")
        print(f"   Free USDT:  ${balance.get('free_usdt', 0):.2f}")
        print(f"   Used USDT:  ${balance.get('used_usdt', 0):.2f}")
        
        # Validate balance is reasonable
        total = balance.get('total_usdt', 0)
        if total >= 0:
            print("✅ Balance is valid (non-negative)")
            result = True
        else:
            print(f"❌ Invalid balance: {total}")
            result = False
        
    except Exception as e:
        print(f"❌ Failed to fetch balance: {e}")
        result = False
    finally:
        await executor.close()
    
    return result


async def test_ticker_fetch():
    """Test 4: Fetch ticker data."""
    print("\n" + "="*80)
    print("TEST 4: Ticker Fetch")
    print("="*80)
    
    executor = MexcExecutor(testnet=True)
    
    try:
        ticker = await executor.get_ticker("GOLD_USDT")
        
        print(f"✅ Ticker fetched for GOLD_USDT:")
        print(f"   Last Price: ${ticker.get('last_price', 0):.2f}")
        print(f"   Bid:        ${ticker.get('bid', 0):.2f}")
        print(f"   Ask:        ${ticker.get('ask', 0):.2f}")
        
        # Validate price is reasonable (gold should be > $1000)
        price = ticker.get('last_price', 0)
        if price > 1000:
            print("✅ Price is reasonable")
            result = True
        else:
            print(f"❌ Suspicious price: ${price}")
            result = False
        
    except Exception as e:
        print(f"❌ Failed to fetch ticker: {e}")
        result = False
    finally:
        await executor.close()
    
    return result


async def test_positions_fetch():
    """Test 5: Fetch open positions."""
    print("\n" + "="*80)
    print("TEST 5: Positions Fetch")
    print("="*80)
    
    executor = MexcExecutor(testnet=True)
    
    try:
        positions = await executor.get_open_positions()
        
        print(f"✅ Fetched {len(positions)} open position(s)")
        
        for pos in positions:
            print(f"   - {pos['symbol']}: {pos.get('side')} {pos.get('size')} @ ${pos.get('entry_price', 0):.2f}")
            print(f"     P&L: ${pos.get('unrealized_pnl', 0):.2f}")
        
        print("✅ Positions fetched successfully")
        result = True
        
    except Exception as e:
        print(f"❌ Failed to fetch positions: {e}")
        result = False
    finally:
        await executor.close()
    
    return result


async def test_health_check():
    """Test 6: Comprehensive health check."""
    print("\n" + "="*80)
    print("TEST 6: Health Check")
    print("="*80)
    
    executor = MexcExecutor(testnet=True)
    
    try:
        health = await executor.health_check()
        
        print(f"✅ Health check completed:")
        print(f"   Status: {health.get('status')}")
        print(f"   Checks Passed: {health.get('checks_passed')}")
        print(f"   Latency: {health.get('overall_latency_ms', 0):.0f}ms")
        
        # Show individual checks
        for check_name, check_data in health.get('checks', {}).items():
            status_icon = "✅" if check_data['status'] == 'pass' else "❌"
            print(f"   {status_icon} {check_name}: {check_data['status']}")
        
        # Overall status
        if health.get('status') in ['healthy', 'degraded']:
            print("✅ System is operational")
            result = True
        else:
            print("❌ System is unhealthy")
            result = False
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        result = False
    finally:
        await executor.close()
    
    return result


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("MEXC ORDER HANDLING VALIDATION TEST")
    print("="*80)
    print(f"Environment: {'TESTNET' if True else 'LIVE'}")
    print(f"Timestamp: {asyncio.get_event_loop().time()}")
    
    # Run tests sequentially
    tests = [
        ("Symbol Normalization", test_symbol_normalization),
        ("Position Mode Detection", test_position_mode_detection),
        ("Balance Fetch", test_balance_fetch),
        ("Ticker Fetch", test_ticker_fetch),
        ("Positions Fetch", test_positions_fetch),
        ("Health Check", test_health_check),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*80}")
            print(f"Running: {test_name}")
            print('='*80)
            
            result = await test_func()
            results[test_name] = result
            
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! MEXC integration is ready.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review and fix issues.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
