#!/usr/bin/env python3
"""
Test ADMIN_API_KEY Security Validation

This script tests that the ADMIN_API_KEY validation properly rejects
placeholder values and accepts valid keys.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings


def test_placeholder_values():
    """Test that placeholder values are rejected."""
    print("=" * 80)
    print("TEST 1: Placeholder Values Should Be Rejected")
    print("=" * 80)
    
    placeholder_values = [
        'CHANGE_ME_IN_PRODUCTION',
        'change_me_in_production',
        'your_admin_api_key_here',
        'admin123',
        'test_key',
        'placeholder',
        'default_key',
        'secret',
        'password',
        '123456',
        'admin',
        'root',
        'apikey',
        'api_key',
        'API_KEY',
        'ADMIN_API_KEY',
        '',
    ]
    
    failed_tests = []
    
    for placeholder in placeholder_values:
        try:
            settings = Settings(ADMIN_API_KEY=placeholder)
            settings.validate_admin_api_key()
            print(f"❌ FAIL: '{placeholder}' was accepted (should be rejected)")
            failed_tests.append(placeholder)
        except ValueError as e:
            print(f"✅ PASS: '{placeholder}' correctly rejected")
            print(f"   Error: {str(e)[:100]}...")
    
    print()
    return len(failed_tests) == 0, failed_tests


def test_short_keys():
    """Test that short keys are rejected."""
    print("=" * 80)
    print("TEST 2: Short Keys (< 16 chars) Should Be Rejected")
    print("=" * 80)
    
    short_keys = [
        'short',
        '123456789012345',  # 15 chars
        'abcdefghijklmnop',  # 16 chars - should pass
    ]
    
    failed_tests = []
    
    for key in short_keys:
        try:
            settings = Settings(ADMIN_API_KEY=key)
            settings.validate_admin_api_key()
            if len(key) < 16:
                print(f"❌ FAIL: '{key}' ({len(key)} chars) was accepted (should be rejected)")
                failed_tests.append(key)
            else:
                print(f"✅ PASS: '{key}' ({len(key)} chars) correctly accepted")
        except ValueError as e:
            if len(key) < 16:
                print(f"✅ PASS: '{key}' ({len(key)} chars) correctly rejected")
            else:
                print(f"❌ FAIL: '{key}' ({len(key)} chars) was rejected (should be accepted)")
                print(f"   Error: {str(e)[:100]}...")
                failed_tests.append(key)
    
    print()
    return len(failed_tests) == 0, failed_tests


def test_valid_keys():
    """Test that valid keys are accepted."""
    print("=" * 80)
    print("TEST 3: Valid Keys Should Be Accepted")
    print("=" * 80)
    
    valid_keys = [
        'a' * 32,  # 32 char key
        'b' * 64,  # 64 char key
        'c7f8e9d0a1b2c3d4e5f6a7b8c9d0e1f2',  # 32 char hex-like key
        'my-super-secret-admin-key-2026!',  # Complex key
    ]
    
    failed_tests = []
    
    for key in valid_keys:
        try:
            settings = Settings(ADMIN_API_KEY=key)
            settings.validate_admin_api_key()
            print(f"✅ PASS: Valid key accepted (length: {len(key)})")
        except ValueError as e:
            print(f"❌ FAIL: Valid key rejected (length: {len(key)})")
            print(f"   Key: {key[:20]}...")
            print(f"   Error: {str(e)[:100]}...")
            failed_tests.append(key)
    
    print()
    return len(failed_tests) == 0, failed_tests


def test_none_value():
    """Test that None value is handled correctly."""
    print("=" * 80)
    print("TEST 4: None Value Should Be Rejected")
    print("=" * 80)
    
    try:
        settings = Settings(ADMIN_API_KEY=None)
        settings.validate_admin_api_key()
        print("❌ FAIL: None value was accepted (should be rejected)")
        return False, [None]
    except ValueError as e:
        print(f"✅ PASS: None value correctly rejected")
        print(f"   Error: {str(e)[:100]}...")
        print()
        return True, []


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "ADMIN_API_KEY SECURITY VALIDATION TESTS" + " " * 21 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    all_passed = True
    all_failures = []
    
    # Test 1: Placeholder values
    passed, failures = test_placeholder_values()
    all_passed = all_passed and passed
    all_failures.extend(failures)
    
    # Test 2: Short keys
    passed, failures = test_short_keys()
    all_passed = all_passed and passed
    all_failures.extend(failures)
    
    # Test 3: Valid keys
    passed, failures = test_valid_keys()
    all_passed = all_passed and passed
    all_failures.extend(failures)
    
    # Test 4: None value
    passed, failures = test_none_value()
    all_passed = all_passed and passed
    all_failures.extend(failures)
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print()
        print("The ADMIN_API_KEY validation is working correctly:")
        print("  • Placeholder values are rejected")
        print("  • Short keys (< 16 chars) are rejected")
        print("  • Valid keys (≥ 16 chars) are accepted")
        print("  • None values are rejected")
        print()
        print("Security baseline is enforced! 🛡️")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print()
        print(f"Failed tests: {len(all_failures)}")
        for failure in all_failures:
            print(f"  • {failure}")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
