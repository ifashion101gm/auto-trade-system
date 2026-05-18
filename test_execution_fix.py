#!/usr/bin/env python3
"""
Test script to verify the CodeBasedExecutionEngine fix.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_execution_engine():
    """Test that CodeBasedExecutionEngine has execute_with_retry method."""
    print("Testing CodeBasedExecutionEngine...")
    
    try:
        from app.ai_agents.optimized_agents import CodeBasedExecutionEngine
        
        # Create instance with proper parameters
        engine = CodeBasedExecutionEngine(
            max_slippage_pct=0.5,
            max_spread_pct=0.1,
            max_retries=3
        )
        
        print(f"✅ CodeBasedExecutionEngine created successfully")
        print(f"   max_slippage_pct: {engine.max_slippage_pct}")
        print(f"   max_spread_pct: {engine.max_spread_pct}")
        print(f"   max_retries: {engine.max_retries}")
        
        # Check if execute_with_retry method exists
        if hasattr(engine, 'execute_with_retry'):
            print(f"✅ execute_with_retry method exists")
            
            # Check if it's callable
            if callable(engine.execute_with_retry):
                print(f"✅ execute_with_retry is callable")
                
                # Check signature
                import inspect
                sig = inspect.signature(engine.execute_with_retry)
                params = list(sig.parameters.keys())
                print(f"✅ Method signature: {params}")
                
                expected_params = ['exchange_manager', 'symbol', 'side', 'quantity', 'leverage', 'expected_price']
                if all(p in params for p in expected_params):
                    print(f"✅ All expected parameters present")
                else:
                    print(f"❌ Missing parameters. Expected: {expected_params}, Got: {params}")
                    return False
            else:
                print(f"❌ execute_with_retry is not callable")
                return False
        else:
            print(f"❌ execute_with_retry method does NOT exist")
            return False
        
        print("\n✅ ALL TESTS PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_execution_engine())
    sys.exit(0 if result else 1)
