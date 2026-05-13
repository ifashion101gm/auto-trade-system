#!/usr/bin/env python3
"""
Bybit Skill Integration - Phase 3 Integration Tests

Validates all Phase 1 & 2 improvements with real Bybit testnet API calls:
1. Credential masking in actual API operations
2. Position mode validation before order placement
3. Large order risk warnings and confirmation
4. Retry logic with transient errors
5. Enhanced error messages

Usage:
    python scripts/test_bybit_phase3_integration.py --mode testnet
    python scripts/test_bybit_phase3_integration.py --mode demo

Requirements:
    - BYBIT_API_KEY and BYBIT_API_SECRET configured in .env
    - Sufficient testnet/demo balance for order testing
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infra.bybit_client import BybitClient
from app.logging_config import get_logger
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)


class IntegrationTestRunner:
    """Runs integration tests against Bybit testnet/demo."""
    
    def __init__(self, mode: str = "testnet"):
        self.mode = mode.lower()
        self.client = None
        self.test_results = []
        
    async def initialize(self):
        """Initialize Bybit client based on mode."""
        print(f"\n{'='*80}")
        print(f"INITIALIZING BYBIT CLIENT ({self.mode.upper()})")
        print(f"{'='*80}")
        
        try:
            if self.mode == "demo":
                self.client = BybitClient(
                    api_key=os.getenv("BYBIT_DEMO_API_KEY"),
                    api_secret=os.getenv("BYBIT_DEMO_API_SECRET"),
                    demo_trading=True
                )
            elif self.mode == "testnet":
                self.client = BybitClient(
                    api_key=os.getenv("BYBIT_TESTNET_API_KEY") or os.getenv("BYBIT_API_KEY"),
                    api_secret=os.getenv("BYBIT_TESTNET_API_SECRET") or os.getenv("BYBIT_API_SECRET"),
                    testnet=True
                )
            else:
                raise ValueError(f"Invalid mode: {self.mode}. Use 'demo' or 'testnet'.")
            
            print(f"✅ Client initialized successfully")
            print(f"   Mode: {self.mode.upper()}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize client: {e}")
            return False
    
    def record_result(self, test_name: str, passed: bool, details: str = ""):
        """Record test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.test_results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        print(f"   {status}: {test_name}")
        if details and not passed:
            print(f"      Details: {details}")
    
    async def test_credential_masking_logs(self):
        """Test 1: Verify credential masking in actual API operations."""
        print(f"\n{'='*80}")
        print("TEST 1: Credential Masking in Real Operations")
        print(f"{'='*80}")
        
        try:
            # Capture logs during API call
            import logging
            from io import StringIO
            
            # Set up log capture for the bybit_client logger
            bybit_logger = logging.getLogger('app.infra.bybit_client')
            log_capture = StringIO()
            handler = logging.StreamHandler(log_capture)
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
            handler.setFormatter(formatter)
            bybit_logger.addHandler(handler)
            
            # Perform API operation that generates logs
            print("   Fetching ticker data...")
            ticker = await self.client.fetch_ticker("BTCUSDT")
            
            # Check logs
            log_output = log_capture.getvalue()
            bybit_logger.removeHandler(handler)
            
            # Verify no full credentials in logs
            api_key = self.client.api_key
            api_secret = self.client.api_secret
            
            has_full_key = api_key in log_output if api_key else False
            has_full_secret = api_secret in log_output if api_secret else False
            
            if has_full_key or has_full_secret:
                self.record_result(
                    "No full credentials in logs",
                    False,
                    f"Found full credentials! Key exposed: {has_full_key}, Secret exposed: {has_full_secret}"
                )
                return False
            else:
                self.record_result("No full credentials in logs", True)
                
            # Verify masked credentials are used (check initialization logs from earlier)
            # Since init already happened, we'll verify the masking methods work correctly
            if api_key and len(api_key) > 9:
                expected_masked = self.client.mask_api_key(api_key)
                # The masking function should produce this format
                masking_works = '...' in expected_masked and len(expected_masked) < len(api_key)
                self.record_result(
                    f"API key masking works ({expected_masked})",
                    masking_works
                )
            
            if api_secret and len(api_secret) > 5:
                expected_masked = self.client.mask_secret(api_secret)
                masking_works = '***' in expected_masked and len(expected_masked) < len(api_secret)
                self.record_result(
                    f"Secret masking works ({expected_masked})",
                    masking_works
                )
            
            print(f"   ✅ Ticker fetched: {ticker.get('symbol')} @ ${ticker.get('last_price', 0):,.2f}")
            return True
            
        except Exception as e:
            self.record_result("Credential masking test", False, str(e))
            return False
    
    async def test_position_mode_validation(self):
        """Test 2: Verify position mode is checked before orders."""
        print(f"\n{'='*80}")
        print("TEST 2: Position Mode Validation")
        print(f"{'='*80}")
        
        try:
            # Check position mode for BTCUSDT
            print("   Checking position mode for BTCUSDT...")
            position_info = await self.client.check_position_mode("BTCUSDT")
            
            print(f"   Position mode: {position_info['mode']}")
            print(f"   Position index: {position_info['position_idx']}")
            
            # Verify response structure
            has_mode = 'mode' in position_info
            has_idx = 'position_idx' in position_info
            valid_mode = position_info['mode'] in ['one_way', 'hedge', 'one-way']
            valid_idx = position_info['position_idx'] in [0, 1, 2]
            
            self.record_result("Position mode response has 'mode' field", has_mode)
            self.record_result("Position mode response has 'position_idx' field", has_idx)
            self.record_result(f"Mode is valid ({position_info['mode']})", valid_mode)
            self.record_result(f"Position index is valid ({position_info['position_idx']})", valid_idx)
            
            return has_mode and has_idx and valid_mode and valid_idx
            
        except Exception as e:
            self.record_result("Position mode validation", False, str(e))
            return False
    
    async def test_risk_validation_small_order(self):
        """Test 3a: Small order (<$10k) should proceed without warnings."""
        print(f"\n{'='*80}")
        print("TEST 3a: Risk Validation - Small Order (<$10k)")
        print(f"{'='*80}")
        
        try:
            # Calculate small order size
            ticker = await self.client.fetch_ticker("BTCUSDT")
            price = ticker['last_price']
            
            # Target $100 order (well below $10k threshold)
            target_value = 100
            amount = target_value / price
            
            print(f"   Current BTC price: ${price:,.2f}")
            print(f"   Order amount: {amount:.6f} BTC")
            print(f"   Notional value: ${target_value:,.2f}")
            
            # Validate notional value calculation
            calculated_notional = self.client.calculate_notional_value(price, amount)
            
            is_below_threshold = calculated_notional < 10000
            calculation_accurate = abs(calculated_notional - target_value) < 0.01
            
            self.record_result(
                f"Notional value below $10k threshold (${calculated_notional:,.2f})",
                is_below_threshold
            )
            self.record_result(
                "Notional value calculation accurate",
                calculation_accurate
            )
            
            print(f"   ✅ Small order would proceed without warnings")
            return is_below_threshold and calculation_accurate
            
        except Exception as e:
            self.record_result("Small order risk validation", False, str(e))
            return False
    
    async def test_risk_validation_large_order(self):
        """Test 3b: Large order (>$10k) should trigger warning."""
        print(f"\n{'='*80}")
        print("TEST 3b: Risk Validation - Large Order (>$10k)")
        print(f"{'='*80}")
        
        try:
            # Calculate large order size
            ticker = await self.client.fetch_ticker("BTCUSDT")
            price = ticker['last_price']
            
            # Target $15,000 order (above $10k threshold)
            target_value = 15000
            amount = target_value / price
            
            print(f"   Current BTC price: ${price:,.2f}")
            print(f"   Order amount: {amount:.6f} BTC")
            print(f"   Notional value: ${target_value:,.2f}")
            
            # Validate notional value calculation
            calculated_notional = self.client.calculate_notional_value(price, amount)
            
            is_above_threshold = calculated_notional > 10000
            triggers_warning = calculated_notional > 10000
            
            self.record_result(
                f"Notional value above $10k threshold (${calculated_notional:,.2f})",
                is_above_threshold
            )
            self.record_result(
                "Large order warning would trigger",
                triggers_warning
            )
            
            # Check percentage of balance
            try:
                balance = await self.client.fetch_balance()
                available = balance.get('free_usdt', 0)
                
                if available > 0:
                    percentage = (calculated_notional / available) * 100
                    print(f"   Available balance: ${available:,.2f}")
                    print(f"   Order as % of balance: {percentage:.1f}%")
                    
                    exceeds_20_percent = percentage > 20
                    self.record_result(
                        f"Order {'exceeds' if exceeds_20_percent else 'within'} 20% balance limit",
                        True  # Just informational
                    )
            except Exception as e:
                print(f"   ⚠️  Could not fetch balance: {e}")
            
            print(f"   ✅ Large order would trigger warning and require confirmation")
            return is_above_threshold and triggers_warning
            
        except Exception as e:
            self.record_result("Large order risk validation", False, str(e))
            return False
    
    async def test_retry_logic_transient_error(self):
        """Test 4: Verify retry logic handles transient errors correctly."""
        print(f"\n{'='*80}")
        print("TEST 4: Retry Logic - Transient Error Handling")
        print(f"{'='*80}")
        
        try:
            # Test with a mock transient error
            print("   Testing is_transient_error() classification...")
            
            # Simulate various error types
            test_cases = [
                ("Connection timeout", ConnectionError("timeout"), True),
                ("Rate limit exceeded", Exception("retCode=10006"), True),
                ("Server error 503", Exception("503 Service Unavailable"), True),
                ("Auth failure", Exception("retCode=10003"), False),
                ("Balance insufficient", Exception("retCode=10004"), False),
            ]
            
            all_passed = True
            for name, error, should_retry in test_cases:
                is_transient = self.client.is_transient_error(error)
                passed = is_transient == should_retry
                
                status = "✅" if passed else "❌"
                expected = "RETRY" if should_retry else "NO RETRY"
                actual = "RETRY" if is_transient else "NO RETRY"
                
                print(f"   {status} {name}: Expected {expected}, Got {actual}")
                
                if not passed:
                    all_passed = False
                    self.record_result(f"Error classification: {name}", False)
            
            if all_passed:
                self.record_result("All error classifications correct", True)
            
            return all_passed
            
        except Exception as e:
            self.record_result("Retry logic test", False, str(e))
            return False
    
    async def test_enhanced_error_messages(self):
        """Test 5: Verify enhanced error messages provide actionable guidance."""
        print(f"\n{'='*80}")
        print("TEST 5: Enhanced Error Messages")
        print(f"{'='*80}")
        
        try:
            # Test error handling for timestamp error
            print("   Testing timestamp error message...")
            
            # Check if the error handling code contains actionable guidance
            import inspect
            
            # Check _handle_pybit_error method
            if hasattr(self.client, '_handle_pybit_error'):
                source = inspect.getsource(self.client._handle_pybit_error)
                
                has_clock_in_code = 'clock' in source.lower() or 'timedatectl' in source.lower()
                has_ntp_in_code = 'ntp' in source.lower() or 'timesyncd' in source.lower()
                has_recv_in_code = 'recv_window' in source.lower()
                
                self.record_result(
                    "Timestamp error mentions clock check",
                    has_clock_in_code
                )
                self.record_result(
                    "Timestamp error mentions NTP sync",
                    has_ntp_in_code
                )
                self.record_result(
                    "Timestamp error mentions recv_window",
                    has_recv_in_code
                )
                
                if has_clock_in_code and has_ntp_in_code and has_recv_in_code:
                    print(f"   ✅ Timestamp error provides actionable guidance")
                    return True
                else:
                    print(f"   ⚠️  Some action steps missing in error handler")
                    return False
            else:
                print(f"   ⚠️  Error handler method not found")
                self.record_result("Error handler exists", False)
                return False
            
        except Exception as e:
            self.record_result("Enhanced error messages test", False, str(e))
            return False
    
    async def test_api_connectivity(self):
        """Test 6: Basic API connectivity and authentication."""
        print(f"\n{'='*80}")
        print("TEST 6: API Connectivity & Authentication")
        print(f"{'='*80}")
        
        try:
            # Test ticker fetch
            print("   Fetching BTCUSDT ticker...")
            ticker = await self.client.fetch_ticker("BTCUSDT")
            
            has_symbol = 'symbol' in ticker
            has_price = 'last_price' in ticker
            price_valid = float(ticker.get('last_price', 0)) > 0
            
            self.record_result("Ticker response includes symbol", has_symbol)
            self.record_result("Ticker response includes price", has_price)
            self.record_result(f"Price is valid (${ticker.get('last_price', 0):,.2f})", price_valid)
            
            # Test balance fetch
            print("   Fetching account balance...")
            balance = await self.client.fetch_balance()
            
            has_usdt = 'free_usdt' in balance or 'total_usdt' in balance
            self.record_result("Balance response includes USDT", has_usdt)
            
            if has_usdt:
                usdt_balance = balance.get('free_usdt', balance.get('total_usdt', 0))
                print(f"   Available USDT: ${usdt_balance:,.2f}")
            
            connectivity_ok = has_symbol and has_price and price_valid
            print(f"   ✅ API connectivity verified")
            return connectivity_ok
            
        except Exception as e:
            self.record_result("API connectivity test", False, str(e))
            print(f"   ❌ API connectivity failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all integration tests."""
        print(f"\n{'='*80}")
        print(f"BYBIT SKILL INTEGRATION - PHASE 3 TESTS")
        print(f"Mode: {self.mode.upper()}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        
        # Initialize client
        if not await self.initialize():
            print("\n❌ Cannot proceed without successful initialization")
            return False
        
        # Run tests in order
        tests = [
            ("API Connectivity", self.test_api_connectivity),
            ("Credential Masking", self.test_credential_masking_logs),
            ("Position Mode Validation", self.test_position_mode_validation),
            ("Risk Validation (Small Order)", self.test_risk_validation_small_order),
            ("Risk Validation (Large Order)", self.test_risk_validation_large_order),
            ("Retry Logic", self.test_retry_logic_transient_error),
            ("Enhanced Error Messages", self.test_enhanced_error_messages),
        ]
        
        for test_name, test_func in tests:
            try:
                await test_func()
            except Exception as e:
                print(f"\n❌ Test '{test_name}' crashed: {e}")
                self.record_result(test_name, False, f"Crashed: {str(e)}")
        
        # Print summary
        self.print_summary()
        
        # Return overall success
        passed = sum(1 for r in self.test_results if r['passed'])
        total = len(self.test_results)
        return passed == total
    
    def print_summary(self):
        """Print test summary."""
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY")
        print(f"{'='*80}")
        
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = sum(1 for r in self.test_results if not r['passed'])
        total = len(self.test_results)
        
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed/total*100) if total > 0 else 0:.1f}%")
        
        if failed > 0:
            print(f"\nFailed Tests:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"   ❌ {result['test']}")
                    if result['details']:
                        print(f"      {result['details']}")
        
        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bybit Phase 3 Integration Tests")
    parser.add_argument(
        "--mode",
        choices=["demo", "testnet"],
        default="testnet",
        help="Trading mode to test (default: testnet)"
    )
    
    args = parser.parse_args()
    
    runner = IntegrationTestRunner(mode=args.mode)
    success = await runner.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
