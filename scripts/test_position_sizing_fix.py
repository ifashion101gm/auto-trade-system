#!/usr/bin/env python3
"""
Test script to verify dynamic position sizing fix in AI Orchestrator.
Tests that position sizes are calculated based on account balance and risk limits.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.ai_agents.orchestrator import AIAgentOrchestrator
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


async def test_position_sizing():
    """Test that position sizing respects account balance and risk limits."""
    
    print("\n" + "="*80)
    print("🧪 TESTING DYNAMIC POSITION SIZING FIX")
    print("="*80)
    
    # Initialize orchestrator
    orchestrator = AIAgentOrchestrator(use_openrouter=True)
    
    print(f"\n📋 Configuration:")
    print(f"  • GOLD_RISK_PER_TRADE: {settings.GOLD_RISK_PER_TRADE:.2%}")
    print(f"  • RISK_MAX_POSITION_SIZE_PCT: {settings.RISK_MAX_POSITION_SIZE_PCT:.2%}")
    print(f"  • GOLD_MAX_LEVERAGE: {settings.GOLD_MAX_LEVERAGE}x")
    
    # Test 1: Fetch account balance
    print(f"\n🔍 Test 1: Fetching account balance...")
    try:
        balance = await orchestrator._get_account_balance()
        print(f"  ✅ Account balance: ${balance:.2f}")
        
        # Calculate expected max position
        expected_max = balance * settings.RISK_MAX_POSITION_SIZE_PCT
        print(f"  📊 Expected max position (1.5%): ${expected_max:.2f}")
    except Exception as e:
        print(f"  ❌ Failed to fetch balance: {e}")
        return False
    
    # Test 2: Assess risk with sample position
    print(f"\n🔍 Test 2: Testing risk assessment...")
    sample_position = {
        'strategy': 'momentum',
        'confidence': 0.75,
        'symbol': 'XAUUSDT'
    }
    
    sample_market_data = {
        'current_price': 2800.0,
        'volatility': 0.45,
        'rsi': 55,
        'macd': 0.5,
        'ma_20': 2790.0,
        'ma_50': 2780.0,
        'symbol': 'XAUUSDT'
    }
    
    try:
        risk_assessment = await orchestrator.assess_risk(sample_position, sample_market_data)
        print(f"  ✅ Risk assessment completed")
        print(f"  • Risk level: {risk_assessment['risk_level']}")
        print(f"  • Max position size: ${risk_assessment['max_position_size']:.2f}")
        print(f"  • Stop loss: {risk_assessment['stop_loss']:.2%}")
        print(f"  • Leverage recommendation: {risk_assessment.get('leverage_recommendation', 'N/A')}x")
        
        # Verify position size is within limits
        max_allowed = balance * settings.RISK_MAX_POSITION_SIZE_PCT
        actual_pct = risk_assessment['max_position_size'] / balance if balance > 0 else 0
        
        print(f"\n  📊 Validation:")
        print(f"    • Max allowed: ${max_allowed:.2f} ({settings.RISK_MAX_POSITION_SIZE_PCT:.1%})")
        print(f"    • Actual: ${risk_assessment['max_position_size']:.2f} ({actual_pct:.1%})")
        
        if risk_assessment['max_position_size'] <= max_allowed * 1.01:  # 1% tolerance
            print(f"    ✅ Position size WITHIN limits")
            test2_pass = True
        else:
            print(f"    ❌ Position size EXCEEDS limits!")
            test2_pass = False
            
    except Exception as e:
        print(f"  ❌ Risk assessment failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Generate trade proposal
    print(f"\n🔍 Test 3: Testing trade proposal generation...")
    try:
        trade_proposal = orchestrator._generate_trade_proposal(
            market_data=sample_market_data,
            regime='Normal',
            strategy={'strategy': 'momentum', 'confidence': 0.75},
            risk=risk_assessment
        )
        
        if trade_proposal:
            print(f"  ✅ Trade proposal generated")
            print(f"  • Symbol: {trade_proposal['symbol']}")
            print(f"  • Side: {trade_proposal['side']}")
            print(f"  • Entry price: ${trade_proposal['entry_price']:.2f}")
            print(f"  • Quantity: {trade_proposal['quantity']:.6f}")
            print(f"  • Leverage: {trade_proposal['leverage']}x")
            
            # Calculate position value
            position_value = trade_proposal['entry_price'] * trade_proposal['quantity'] * trade_proposal['leverage']
            position_pct = position_value / balance if balance > 0 else 0
            
            print(f"\n  📊 Position Value Analysis:")
            print(f"    • Position value (with leverage): ${position_value:.2f}")
            print(f"    • Position % of balance: {position_pct:.2%}")
            print(f"    • Max allowed: ${max_allowed:.2f} ({settings.RISK_MAX_POSITION_SIZE_PCT:.1%})")
            
            if position_value <= max_allowed * 1.01:  # 1% tolerance
                print(f"    ✅ Position value WITHIN limits")
                test3_pass = True
            else:
                print(f"    ❌ Position value EXCEEDS limits by ${(position_value - max_allowed):.2f}!")
                test3_pass = False
        else:
            print(f"  ⚠️  No trade proposal generated (strategy returned no_trade)")
            test3_pass = True  # This is acceptable
            
    except Exception as e:
        print(f"  ❌ Trade proposal generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Summary
    print(f"\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    print(f"  Test 1 (Balance Fetch): {'✅ PASS' if balance > 0 else '❌ FAIL'}")
    print(f"  Test 2 (Risk Assessment): {'✅ PASS' if test2_pass else '❌ FAIL'}")
    print(f"  Test 3 (Trade Proposal): {'✅ PASS' if test3_pass else '❌ FAIL'}")
    
    all_pass = balance > 0 and test2_pass and test3_pass
    print(f"\n  Overall: {'✅ ALL TESTS PASSED' if all_pass else '❌ SOME TESTS FAILED'}")
    print("="*80 + "\n")
    
    return all_pass


if __name__ == "__main__":
    try:
        result = asyncio.run(test_position_sizing())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
