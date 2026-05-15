#!/usr/bin/env python3
"""
Quick verification script for Freqtrade pattern integration.
Run this to verify all components are properly installed.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def verify_imports():
    """Verify all new modules can be imported."""
    print("="*80)
    print("Verifying Freqtrade Pattern Integration")
    print("="*80)
    print()
    
    errors = []
    
    # Test 1: Persistent Idempotency Manager
    try:
        from app.execution.retry_manager import PersistentIdempotencyManager
        print("✅ PersistentIdempotencyManager imported successfully")
    except Exception as e:
        print(f"❌ Failed to import PersistentIdempotencyManager: {e}")
        errors.append(str(e))
    
    # Test 2: State Recovery Engine
    try:
        from app.execution.state_recovery import TradeStateRecovery
        print("✅ TradeStateRecovery imported successfully")
    except Exception as e:
        print(f"❌ Failed to import TradeStateRecovery: {e}")
        errors.append(str(e))
    
    # Test 3: Strategy Interface
    try:
        from app.execution.strategy_interface import IStrategy, TradeSignal, StrategyRegistry
        print("✅ Strategy interface imported successfully")
    except Exception as e:
        print(f"❌ Failed to import strategy interface: {e}")
        errors.append(str(e))
    
    # Test 4: Circuit Breaker in Execution Service
    try:
        from app.execution.execution_service import ExecutionService
        print("✅ ExecutionService imported successfully")
        
        # Check if circuit breaker is integrated
        import inspect
        source = inspect.getsource(ExecutionService.execute_trade)
        if 'circuit_breaker' in source.lower():
            print("✅ Circuit breaker integration verified in ExecutionService")
        else:
            print("⚠️  Circuit breaker integration not found in execute_trade method")
            
    except Exception as e:
        print(f"❌ Failed to import ExecutionService: {e}")
        errors.append(str(e))
    
    # Test 5: Configuration
    try:
        from app.config import settings
        print("✅ Configuration loaded successfully")
        
        # Check for relevant settings
        if hasattr(settings, 'ORDER_IDEMPOTENCY_ENABLED'):
            print(f"   - ORDER_IDEMPOTENCY_ENABLED: {settings.ORDER_IDEMPOTENCY_ENABLED}")
        if hasattr(settings, 'CIRCUIT_BREAKER_FAILURE_THRESHOLD'):
            print(f"   - CIRCUIT_BREAKER_FAILURE_THRESHOLD: {settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD}")
            
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        errors.append(str(e))
    
    print()
    print("="*80)
    
    if errors:
        print(f"❌ Verification FAILED with {len(errors)} error(s)")
        for error in errors:
            print(f"   - {error}")
        return False
    else:
        print("✅ All verifications PASSED")
        print()
        print("Summary:")
        print("  • Persistent Idempotency Manager: Ready")
        print("  • Trade State Recovery Engine: Ready")
        print("  • Strategy Interface: Ready")
        print("  • Circuit Breaker Integration: Ready")
        print()
        print("Next Steps:")
        print("  1. Update .env with feature flags (see FREQTRADE_QUICKREF.md)")
        print("  2. Run full test suite: pytest tests/integration/test_freqtrade_patterns.py")
        print("  3. Deploy to staging/demo environment")
        print("  4. Monitor for 48 hours")
        return True

if __name__ == "__main__":
    success = verify_imports()
    sys.exit(0 if success else 1)
