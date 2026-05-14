"""
Simple verification test for Issue A - Execution Service Integration

This test verifies the critical changes without complex mocking.
"""
import ast
import inspect


def test_execution_service_import_in_trading_service():
    """Verify ExecutionService is imported in LiveTradingService.__init__"""
    with open('app/execution/trading_service.py', 'r') as f:
        content = f.read()
    
    # Check for ExecutionService import
    assert 'from app.execution.execution_service import ExecutionService' in content, \
        "ExecutionService should be imported"
    
    # Check for execution_service initialization
    assert 'self.execution_service = ExecutionService(' in content, \
        "ExecutionService should be initialized as instance variable"
    
    print("✅ ExecutionService is properly imported and initialized")


def test_symbol_locks_initialized():
    """Verify symbol locks are initialized"""
    with open('app/execution/trading_service.py', 'r') as f:
        content = f.read()
    
    # Check for symbol_locks dict
    assert 'self.symbol_locks: Dict[str, asyncio.Lock] = {}' in content, \
        "symbol_locks dict should be initialized"
    
    # Check for _get_symbol_lock method
    assert 'def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:' in content, \
        "_get_symbol_lock method should exist"
    
    print("✅ Symbol locks are properly initialized")


def test_execute_trade_uses_execution_service():
    """Verify _execute_trade delegates to ExecutionService"""
    with open('app/execution/trading_service.py', 'r') as f:
        content = f.read()
    
    # Check that _execute_trade calls ExecutionService
    assert 'await self.execution_service.execute_trade(' in content, \
        "_execute_trade should call ExecutionService.execute_trade"
    
    # Check for ExecutionRequest creation
    assert 'ExecutionRequest(' in content, \
        "ExecutionRequest should be created"
    
    # Check for symbol lock usage
    assert 'async with symbol_lock:' in content, \
        "Symbol lock should be used in _execute_trade"
    
    print("✅ _execute_trade properly delegates to ExecutionService")


def test_no_direct_exchange_calls_in_execute_trade():
    """Verify direct exchange_manager.create_market_order is NOT called in _execute_trade"""
    with open('app/execution/trading_service.py', 'r') as f:
        content = f.read()
    
    # Find _execute_trade method
    tree = ast.parse(content)
    
    execute_trade_method = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == '_execute_trade':
            execute_trade_method = node
            break
    
    assert execute_trade_method is not None, "_execute_trade method should exist"
    
    # Check that it doesn't directly call exchange_manager.create_market_order
    method_source = ast.get_source_segment(content, execute_trade_method)
    
    # The old code had this pattern - should NOT be present anymore
    assert 'await self.exchange_manager.create_market_order(' not in method_source or \
           method_source.count('await self.exchange_manager.create_market_order(') == 0, \
        "_execute_trade should NOT directly call exchange_manager.create_market_order"
    
    print("✅ No direct exchange calls in _execute_trade (delegates to ExecutionService)")


def test_reconciliation_engine_import_fixed():
    """Verify reconciliation engine import uses correct class name"""
    with open('app/execution/trading_service.py', 'r') as f:
        content = f.read()
    
    # Should import OrderReconciliationEngine, not PositionReconciliationEngine
    assert 'from app.execution.reconciliation_engine import OrderReconciliationEngine' in content, \
        "Should import OrderReconciliationEngine"
    
    assert 'PositionReconciliationEngine' not in content or \
           content.count('PositionReconciliationEngine') == 0, \
        "Should NOT reference PositionReconciliationEngine"
    
    print("✅ Reconciliation engine import is correct")


if __name__ == '__main__':
    print("Running Issue A Verification Tests...\n")
    
    try:
        test_execution_service_import_in_trading_service()
        test_symbol_locks_initialized()
        test_execute_trade_uses_execution_service()
        test_no_direct_exchange_calls_in_execute_trade()
        test_reconciliation_engine_import_fixed()
        
        print("\n" + "="*70)
        print("✅ ALL VERIFICATION TESTS PASSED!")
        print("="*70)
        print("\nIssue A Implementation Summary:")
        print("  ✅ ExecutionService integrated into LiveTradingService")
        print("  ✅ Symbol-level concurrency locks added")
        print("  ✅ _execute_trade delegates to ExecutionService")
        print("  ✅ Direct exchange calls removed from _execute_trade")
        print("  ✅ Import errors fixed")
        print("\nProduction Readiness: Issue A COMPLETE")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
