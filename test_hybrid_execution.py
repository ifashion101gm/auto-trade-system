#!/usr/bin/env python3
"""
Test script for Hybrid Execution Mode.

Demonstrates position-based auto-execution logic:
- Positions ≤ $100 USD: Auto-execute
- Positions > $100 USD: Require confirmation
"""
import asyncio
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.config import settings
from app.ai.optimized_agents import DeterministicRiskManager


def test_position_sizing():
    """Test position sizing calculations with different scenarios."""
    print("=" * 80)
    print("HYBRID EXECUTION MODE - POSITION SIZING TEST")
    print("=" * 80)
    print()
    
    # Initialize risk manager
    risk_mgr = DeterministicRiskManager(
        max_risk_per_trade=0.01,  # 1% risk
        account_balance=1000.0     # $1000 balance
    )
    
    print(f"Configuration:")
    print(f"  Account Balance: ${risk_mgr.account_balance:,.2f}")
    print(f"  Risk Per Trade: {risk_mgr.max_risk_per_trade * 100}%")
    print(f"  Auto-Execute Threshold: ${settings.AUTO_EXECUTE_THRESHOLD_USD:.2f}")
    print()
    
    # Test scenarios
    scenarios = [
        {
            'name': 'Small Position (Auto-Execute)',
            'entry_price': 50000.0,
            'stop_loss': 49500.0,
            'confidence': 0.5,
            'regime': 'Normal'
        },
        {
            'name': 'Medium Position (Requires Confirmation)',
            'entry_price': 50000.0,
            'stop_loss': 49000.0,
            'confidence': 0.7,
            'regime': 'Normal'
        },
        {
            'name': 'Large Position (Requires Confirmation)',
            'entry_price': 50000.0,
            'stop_loss': 48500.0,
            'confidence': 0.8,
            'regime': 'Normal'
        }
    ]
    
    print("-" * 80)
    print("Testing Scenarios:")
    print("-" * 80)
    print()
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}. {scenario['name']}")
        print(f"   Entry Price: ${scenario['entry_price']:,.2f}")
        print(f"   Stop Loss: ${scenario['stop_loss']:,.2f}")
        print(f"   Confidence: {scenario['confidence']:.0%}")
        
        # Calculate position size
        result = risk_mgr.calculate_position_size(
            entry_price=scenario['entry_price'],
            stop_loss_price=scenario['stop_loss'],
            confidence=scenario['confidence'],
            regime=scenario['regime']
        )
        
        if result['allowed']:
            quantity = result['quantity']
            position_value = scenario['entry_price'] * quantity
            
            print(f"   Quantity: {quantity:.6f}")
            print(f"   Leverage: {result['leverage']}x")
            print(f"   Position Value: ${position_value:,.2f}")
            print(f"   Risk Amount: ${result['risk_amount']:.2f}")
            
            # Determine execution behavior
            threshold = settings.AUTO_EXECUTE_THRESHOLD_USD
            if position_value <= threshold:
                print(f"   ✅ AUTO-EXECUTE (${position_value:,.2f} ≤ ${threshold:.2f})")
            else:
                print(f"   ⏸️  REQUIRES CONFIRMATION (${position_value:,.2f} > ${threshold:.2f})")
        else:
            print(f"   ❌ NOT ALLOWED: {result['reason']}")
        
        print()
    
    print("=" * 80)
    print("HYBRID EXECUTION LOGIC SUMMARY")
    print("=" * 80)
    print()
    print(f"Current Configuration:")
    print(f"  EXECUTION_MODE: {settings.EXECUTION_MODE}")
    print(f"  AUTO_EXECUTE_THRESHOLD_USD: ${settings.AUTO_EXECUTE_THRESHOLD_USD:.2f}")
    print()
    print("Behavior in semi-auto mode:")
    print(f"  • Position ≤ ${settings.AUTO_EXECUTE_THRESHOLD_USD:.2f}: Auto-execute immediately")
    print(f"  • Position > ${settings.AUTO_EXECUTE_THRESHOLD_USD:.2f}: Save proposal, await confirmation")
    print()
    print("Benefits:")
    print("  ✅ Small trades automated (convenience)")
    print("  ✅ Large trades require approval (safety)")
    print("  ✅ Configurable threshold (flexibility)")
    print("  ✅ Best of both worlds!")
    print()


if __name__ == "__main__":
    test_position_sizing()
