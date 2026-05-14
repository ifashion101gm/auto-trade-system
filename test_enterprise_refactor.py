#!/usr/bin/env python3
"""
Quick validation script for Gold Bot Enterprise refactoring.
Tests critical components without starting full system.
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test that all new modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        from app.runtime.task_supervisor import TaskSupervisor
        print("  ✅ TaskSupervisor imported")
    except Exception as e:
        print(f"  ❌ TaskSupervisor import failed: {e}")
        return False
    
    try:
        from app.risk.circuit_breaker import CircuitBreaker, get_circuit_breaker
        print("  ✅ CircuitBreaker imported")
    except Exception as e:
        print(f"  ❌ CircuitBreaker import failed: {e}")
        return False
    
    try:
        from app.strategies.gold_opening_reversal import GoldOpeningReversalStrategy
        print("  ✅ GoldOpeningReversalStrategy imported")
    except Exception as e:
        print(f"  ❌ GoldOpeningReversalStrategy import failed: {e}")
        return False
    
    try:
        from app.worker_gold_bot import main as worker_main
        print("  ✅ worker_gold_bot imported")
    except Exception as e:
        print(f"  ❌ worker_gold_bot import failed: {e}")
        return False
    
    return True


def test_task_supervisor():
    """Test TaskSupervisor basic functionality."""
    print("\n🔍 Testing TaskSupervisor...")
    
    from app.runtime.task_supervisor import TaskSupervisor
    
    supervisor = TaskSupervisor(max_restart_attempts=2)
    
    # Test task creation
    async def dummy_task():
        await asyncio.sleep(0.1)
        return "done"
    
    task = supervisor.create_task(dummy_task(), name="test_task", critical=True)
    
    if supervisor.get_task_count() == 1:
        print("  ✅ Task created successfully")
    else:
        print(f"  ❌ Expected 1 task, got {supervisor.get_task_count()}")
        return False
    
    # Test health check
    health = supervisor.get_health()
    if 'total_tasks' in health and 'healthy_tasks' in health:
        print("  ✅ Health check works")
    else:
        print("  ❌ Health check missing fields")
        return False
    
    print(f"  ℹ️  Task count: {health['total_tasks']}")
    
    return True


def test_circuit_breaker():
    """Test CircuitBreaker logic."""
    print("\n🔍 Testing CircuitBreaker...")
    
    from app.risk.circuit_breaker import CircuitBreaker
    
    cb = CircuitBreaker()
    
    # Test normal operation
    metrics_normal = {
        'consecutive_losses': 0,
        'drawdown_pct': 0.01,
        'api_latency_ms': 500,
        'ws_disconnects_last_hour': 2,
        'infrastructure_failures': 0
    }
    
    if cb.check_and_update(metrics_normal):
        print("  ✅ Trading allowed under normal conditions")
    else:
        print("  ❌ Trading incorrectly blocked")
        return False
    
    # Test consecutive losses trigger
    metrics_losses = {
        'consecutive_losses': 3,
        'drawdown_pct': 0.01,
        'api_latency_ms': 500,
        'ws_disconnects_last_hour': 2,
        'infrastructure_failures': 0
    }
    
    if not cb.check_and_update(metrics_losses):
        print("  ✅ Circuit breaker trips on consecutive losses")
    else:
        print("  ❌ Circuit breaker should trip on 3 consecutive losses")
        return False
    
    # Test reset
    cb.reset("Test reset")
    if not cb.trading_disabled:
        print("  ✅ Circuit breaker resets correctly")
    else:
        print("  ❌ Circuit breaker failed to reset")
        return False
    
    return True


def test_gold_strategy():
    """Test GoldOpeningReversalStrategy initialization."""
    print("\n🔍 Testing GoldOpeningReversalStrategy...")
    
    from app.strategies.gold_opening_reversal import GoldOpeningReversalStrategy
    
    strategy = GoldOpeningReversalStrategy()
    
    if strategy.name == "gold_opening_reversal":
        print("  ✅ Strategy name correct")
    else:
        print(f"  ❌ Wrong strategy name: {strategy.name}")
        return False
    
    # Test session detection (may vary based on current time)
    is_session = strategy.is_trading_session()
    print(f"  ℹ️  Currently in trading session: {is_session}")
    
    # Test parameter retrieval
    params = strategy.get_parameters()
    if 'min_confidence' in params and 'risk_per_trade' in params:
        print("  ✅ Strategy parameters accessible")
    else:
        print("  ❌ Missing strategy parameters")
        return False
    
    return True


def test_position_sync_optimization():
    """Test PositionSyncService WebSocket-first optimization."""
    print("\n🔍 Testing PositionSyncService optimization...")
    
    from app.sync.position_sync import PositionSyncService
    
    sync_service = PositionSyncService(testnet=True)
    
    # Check optimized attributes exist
    if hasattr(sync_service, '_ws_update_received'):
        print("  ✅ WebSocket tracking attribute exists")
    else:
        print("  ❌ Missing WebSocket tracking")
        return False
    
    if hasattr(sync_service, '_rest_sync_interval'):
        if sync_service._rest_sync_interval == 15:
            print("  ✅ REST sync interval optimized to 15s")
        else:
            print(f"  ⚠️  REST sync interval is {sync_service._rest_sync_interval}s (expected 15s)")
    else:
        print("  ❌ Missing REST sync interval")
        return False
    
    # Test on_websocket_update method
    if hasattr(sync_service, 'on_websocket_update'):
        print("  ✅ WebSocket update handler exists")
    else:
        print("  ❌ Missing WebSocket update handler")
        return False
    
    return True


async def main():
    """Run all tests."""
    print("=" * 80)
    print("GOLD BOT ENTERPRISE VALIDATION")
    print("=" * 80)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("TaskSupervisor", test_task_supervisor()))
    results.append(("CircuitBreaker", test_circuit_breaker()))
    results.append(("GoldStrategy", test_gold_strategy()))
    results.append(("PositionSync", test_position_sync_optimization()))
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print("=" * 80)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validations passed! System ready for deployment.")
        return 0
    else:
        print("⚠️  Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
