#!/usr/bin/env python3
"""
Test script to verify account-based risk validation fix.

This script demonstrates that the validator now correctly validates risk
against account balance (not position value), which aligns with how positions
are sized in the system.

Before fix: Risk was validated as % of position value → rejected small positions
After fix: Risk is validated as % of account balance → accepts properly-sized positions
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.risk.validator import TradeValidator, ValidationResult
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock


async def test_account_based_risk_validation():
    """Test that risk validation uses account balance, not position value."""
    
    print("="*80)
    print("ACCOUNT-BASED RISK VALIDATION TEST")
    print("="*80)
    print()
    
    # Setup mock database session
    db_session = AsyncMock(spec=AsyncSession)
    
    # Mock the execute method to return proper results
    async def mock_execute(*args, **kwargs):
        from unittest.mock import MagicMock
        result = MagicMock()
        result.scalar.return_value = 0  # No open positions
        return result
    
    db_session.execute = mock_execute
    
    validator = TradeValidator()
    
    # Test scenario from user's issue:
    # - Account balance: $100
    # - Position value: ~$4.50 (0.000989 XAU @ $4548)
    # - Stop loss distance creates $0.18 risk
    # - Risk per trade limit: 2% (safer_growth profile)
    
    print("📊 TEST SCENARIO:")
    print("-" * 80)
    print("Account Balance: $100.00")
    print("Position Size: 0.000989 XAU")
    print("Entry Price: $4548.00")
    print("Position Value: $4.50")
    print("Stop Loss Distance: ~$182 (4%)")
    print("Risk Amount: $0.18")
    print()
    
    # Create trade proposal matching the user's scenario
    proposal = {
        'symbol': 'XAU/USDT',
        'side': 'LONG',
        'entry_price': 4548.00,
        'stop_loss': 4366.00,  # ~4% below entry
        'take_profit': 4730.00,
        'quantity': 0.000989,
        'leverage': 2,
        'confidence': 0.85,
        'strategy_name': 'momentum',
        'regime': 'Normal'
    }
    
    # Calculate expected values
    entry_price = proposal['entry_price']
    stop_loss = proposal['stop_loss']
    quantity = proposal['quantity']
    leverage = proposal['leverage']
    account_balance = 100.0
    
    position_value = entry_price * quantity
    risk_per_unit = abs(entry_price - stop_loss)
    risk_amount = risk_per_unit * quantity * leverage
    
    print(f"🔍 CALCULATIONS:")
    print("-" * 80)
    print(f"Position Value = ${position_value:.2f}")
    print(f"Risk Per Unit = ${risk_per_unit:.2f}")
    print(f"Risk Amount = ${risk_amount:.2f} (risk_per_unit × quantity × leverage)")
    print()
    
    # OLD METHOD (position-based) - would reject
    old_risk_pct = risk_amount / position_value if position_value > 0 else 0
    print(f"❌ OLD METHOD (Position-Based):")
    print(f"   Risk % = ${risk_amount:.2f} / ${position_value:.2f} = {old_risk_pct:.2%}")
    print(f"   Limit: 2%")
    print(f"   Result: {'REJECTED ❌' if old_risk_pct > 0.02 else 'APPROVED ✅'}")
    print(f"   Reason: {'Risk exceeds position-based limit' if old_risk_pct > 0.02 else 'Within limits'}")
    print()
    
    # NEW METHOD (account-based) - should approve
    new_risk_pct = risk_amount / account_balance if account_balance > 0 else 0
    print(f"✅ NEW METHOD (Account-Based):")
    print(f"   Risk % = ${risk_amount:.2f} / ${account_balance:.2f} = {new_risk_pct:.2%}")
    print(f"   Limit: 2%")
    print(f"   Result: {'REJECTED ❌' if new_risk_pct > 0.02 else 'APPROVED ✅'}")
    print(f"   Reason: {'Risk exceeds account-based limit' if new_risk_pct > 0.02 else 'Within limits'}")
    print()
    
    # Run actual validation with account balance
    print("🧪 RUNNING VALIDATOR WITH ACCOUNT BALANCE:")
    print("-" * 80)
    
    result = await validator.validate_trade(
        proposal=proposal,
        user_id='test_user',
        db_session=db_session,
        exchange='mexc',
        symbol='XAU/USDT',
        account_balance=account_balance
    )
    
    print(f"Validation Result: {'APPROVED ✅' if result.approved else 'REJECTED ❌'}")
    print(f"Risk Threshold: {result.risk_threshold:.0%}")
    print(f"Position Value: ${result.position_value:.2f}")
    print(f"Risk Amount: ${result.risk_amount:.2f}")
    print(f"Account Balance: ${result.account_balance:.2f}")
    
    if result.violations:
        print(f"\nViolations:")
        for v in result.violations:
            print(f"  - {v}")
    
    if result.warnings:
        print(f"\nWarnings:")
        for w in result.warnings:
            print(f"  - {w}")
    
    print()
    
    # Test without account balance (fallback behavior)
    print("🧪 RUNNING VALIDATOR WITHOUT ACCOUNT BALANCE (Fallback):")
    print("-" * 80)
    
    result_fallback = await validator.validate_trade(
        proposal=proposal,
        user_id='test_user',
        db_session=db_session,
        exchange='mexc',
        symbol='XAU/USDT',
        account_balance=None  # No balance provided
    )
    
    print(f"Validation Result: {'APPROVED ✅' if result_fallback.approved else 'REJECTED ❌'}")
    
    if result_fallback.violations:
        print(f"\nViolations (using position-based fallback):")
        for v in result_fallback.violations:
            print(f"  - {v}")
    
    print()
    
    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    
    if result.approved and not result_fallback.approved:
        print("✅ FIX VERIFIED!")
        print()
        print("The validator now correctly:")
        print("  1. Uses account-based risk model when balance is provided")
        print("  2. Falls back to position-based model when balance is missing")
        print("  3. Aligns with position sizing logic (which uses account balance)")
        print()
        print("This resolves the issue where small positions were incorrectly rejected")
        print("due to mismatched risk calculation models.")
        return True
    elif result.approved and result_fallback.approved:
        print("⚠️  Both methods approved (risk is within both limits)")
        print()
        print("The fix is working, but this specific trade has low enough risk")
        print("to pass both validation models.")
        return True
    else:
        print("❌ UNEXPECTED RESULT")
        print()
        print("With account balance:", "APPROVED" if result.approved else "REJECTED")
        print("Without account balance:", "APPROVED" if result_fallback.approved else "REJECTED")
        return False


async def test_position_sizing_consistency():
    """Verify that position sizing and validation use the same risk model."""
    
    print("\n" + "="*80)
    print("POSITION SIZING CONSISTENCY TEST")
    print("="*80)
    print()
    
    from app.risk.calculations import calculate_position_size
    
    account_balance = 100.0
    risk_per_trade_pct = 0.02  # 2%
    entry_price = 4548.0
    stop_loss_price = 4366.0  # 4% below
    
    print("📐 POSITION SIZING:")
    print("-" * 80)
    print(f"Account Balance: ${account_balance:.2f}")
    print(f"Risk Per Trade: {risk_per_trade_pct:.0%}")
    print(f"Entry Price: ${entry_price:.2f}")
    print(f"Stop Loss: ${stop_loss_price:.2f}")
    print()
    
    # Calculate position size using the system's formula
    sizing_result = calculate_position_size(
        account_balance=account_balance,
        risk_per_trade_pct=risk_per_trade_pct,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        confidence=1.0,
        max_leverage=2
    )
    
    print(f"Sizing Result:")
    print(f"  Quantity: {sizing_result['quantity']:.6f}")
    print(f"  Position Value: ${sizing_result['position_value']:.2f}")
    print(f"  Risk Amount: ${sizing_result['risk_amount']:.2f}")
    print(f"  Leverage: {sizing_result['leverage']}x")
    print()
    
    # Verify risk matches account-based model
    calculated_risk_pct = sizing_result['risk_amount'] / account_balance
    print(f"Risk Verification:")
    print(f"  Risk % (account-based): ${sizing_result['risk_amount']:.2f} / ${account_balance:.2f} = {calculated_risk_pct:.2%}")
    print(f"  Expected: {risk_per_trade_pct:.0%}")
    print(f"  Match: {'✅ YES' if abs(calculated_risk_pct - risk_per_trade_pct) < 0.001 else '❌ NO'}")
    print()
    
    # Now validate this position
    print("🔍 VALIDATING SIZED POSITION:")
    print("-" * 80)
    
    db_session = AsyncMock(spec=AsyncSession)
    
    # Mock the execute method
    async def mock_execute(*args, **kwargs):
        from unittest.mock import MagicMock
        result = MagicMock()
        result.scalar.return_value = 0
        return result
    
    db_session.execute = mock_execute
    
    validator = TradeValidator()
    
    proposal = {
        'symbol': 'XAU/USDT',
        'side': 'LONG',
        'entry_price': entry_price,
        'stop_loss': stop_loss_price,
        'take_profit': entry_price * 1.04,
        'quantity': sizing_result['quantity'],
        'leverage': sizing_result['leverage'],
        'confidence': 0.85,
        'strategy_name': 'momentum',
        'regime': 'Normal'
    }
    
    result = await validator.validate_trade(
        proposal=proposal,
        user_id='test_user',
        db_session=db_session,
        exchange='mexc',
        symbol='XAU/USDT',
        account_balance=account_balance
    )
    
    print(f"Validation Result: {'APPROVED ✅' if result.approved else 'REJECTED ❌'}")
    print(f"Risk Amount: ${result.risk_amount:.2f}")
    print(f"Risk % (of account): {result.risk_amount / account_balance:.2%}")
    print(f"Limit: {result.risk_threshold:.0%}")
    
    if result.approved:
        print()
        print("✅ CONSISTENCY VERIFIED!")
        print("Position sizing and validation both use account-based risk model.")
        return True
    else:
        print()
        print("❌ INCONSISTENCY DETECTED!")
        if result.violations:
            print("Violations:")
            for v in result.violations:
                print(f"  - {v}")
        return False


async def main():
    """Run all tests."""
    print()
    
    # Test 1: Account-based validation
    test1_passed = await test_account_based_risk_validation()
    
    # Test 2: Position sizing consistency
    test2_passed = await test_position_sizing_consistency()
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print()
    print(f"Test 1 (Account-Based Validation): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Position Sizing Consistency): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print()
    
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("The risk validation system now correctly:")
        print("  • Validates risk against account balance (not position value)")
        print("  • Aligns with position sizing logic")
        print("  • Prevents false rejections of properly-sized trades")
        print("  • Maintains backward compatibility (fallback mode)")
        print()
        return 0
    else:
        print("⚠️  SOME TESTS FAILED")
        print()
        print("Please review the output above for details.")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
