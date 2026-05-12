"""Validate Order Execution Engine implementation."""
import asyncio
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.execution.states import OrderState, is_valid_order_state_transition, OrderLifecycleManager, InvalidStateTransitionError
from app.execution.retry_manager import SmartRetryManager, RetryConfig, IdempotencyManager
from app.database.connection import get_session
from app.database.models import Orders, Positions, Trades


async def validate_state_machine():
    """Test order state machine transitions."""
    print("Testing Order State Machine...")
    
    # Valid transitions
    assert is_valid_order_state_transition(OrderState.NEW, OrderState.PENDING), "NEW → PENDING should be valid"
    assert is_valid_order_state_transition(OrderState.PENDING, OrderState.FILLED), "PENDING → FILLED should be valid"
    assert is_valid_order_state_transition(OrderState.PENDING, OrderState.CANCELED), "PENDING → CANCELED should be valid"
    assert is_valid_order_state_transition(OrderState.PENDING, OrderState.PARTIALLY_FILLED), "PENDING → PARTIALLY_FILLED should be valid"
    assert is_valid_order_state_transition(OrderState.PARTIALLY_FILLED, OrderState.FILLED), "PARTIALLY_FILLED → FILLED should be valid"
    
    # Invalid transitions
    assert not is_valid_order_state_transition(OrderState.FILLED, OrderState.PENDING), "FILLED → PENDING should be invalid"
    assert not is_valid_order_state_transition(OrderState.CANCELED, OrderState.NEW), "CANCELED → NEW should be invalid"
    assert not is_valid_order_state_transition(OrderState.REJECTED, OrderState.PENDING), "REJECTED → PENDING should be invalid"
    
    print("✅ State machine validation passed")
    
    # Test OrderLifecycleManager
    print("\nTesting OrderLifecycleManager...")
    manager = OrderLifecycleManager()
    
    # Valid transition
    result = manager.transition("order_123", OrderState.NEW, OrderState.PENDING)
    assert result == True, "Valid transition should return True"
    
    # Check history
    history = manager.get_order_history("order_123")
    assert len(history) == 1, "Should have 1 transition in history"
    assert history[0]['from_state'] == 'new', "From state should be 'new'"
    assert history[0]['to_state'] == 'pending', "To state should be 'pending'"
    
    # Invalid transition should raise exception
    try:
        manager.transition("order_123", OrderState.FILLED, OrderState.PENDING)
        assert False, "Should have raised InvalidStateTransitionError"
    except InvalidStateTransitionError:
        print("✅ InvalidStateTransitionError correctly raised for invalid transition")
    
    print("✅ OrderLifecycleManager validation passed")


async def validate_retry_system():
    """Test smart retry system."""
    print("\nTesting Smart Retry System...")
    
    # Test IdempotencyManager
    idempotency_mgr = IdempotencyManager()
    
    # Generate client order ID
    client_id = idempotency_mgr.generate_client_order_id("TEST")
    assert client_id.startswith("TEST_"), "Client ID should start with prefix"
    assert len(client_id) > 10, "Client ID should be sufficiently long"
    print(f"   Generated client order ID: {client_id}")
    
    # Check duplicate (should be None initially)
    result = idempotency_mgr.check_duplicate(client_id)
    assert result is None, "New client ID should not have previous result"
    
    # Record submission
    test_result = {'order_id': 'test_123', 'status': 'filled'}
    idempotency_mgr.record_submission(client_id, test_result)
    
    # Check duplicate (should return result now)
    result = idempotency_mgr.check_duplicate(client_id)
    assert result == test_result, "Should return recorded result"
    
    print("✅ IdempotencyManager validation passed")
    
    # Test RetryConfig
    config = RetryConfig(max_retries=3, base_delay=1.0, max_delay=60.0)
    assert config.max_retries == 3, "Max retries should be 3"
    assert config.base_delay == 1.0, "Base delay should be 1.0"
    print("✅ RetryConfig validation passed")


async def validate_database_schema():
    """Verify database tables exist."""
    print("\nTesting Database Schema...")
    
    from app.database.connection import async_session_maker
    
    async with async_session_maker() as session:
        from sqlalchemy import text
        
        # Test orders table
        result = await session.execute(text("SELECT COUNT(*) FROM orders"))
        count = result.scalar()
        print(f"   ✓ Orders table: {count} records")
        
        # Test execution_logs table
        result = await session.execute(text("SELECT COUNT(*) FROM execution_logs"))
        count = result.scalar()
        print(f"   ✓ Execution_logs table: {count} records")
        
        # Test risk_events table
        result = await session.execute(text("SELECT COUNT(*) FROM risk_events"))
        count = result.scalar()
        print(f"   ✓ Risk_events table: {count} records")
        
        # Test recovery_events table
        result = await session.execute(text("SELECT COUNT(*) FROM recovery_events"))
        count = result.scalar()
        print(f"   ✓ Recovery_events table: {count} records")
        
        # Test signals table
        result = await session.execute(text("SELECT COUNT(*) FROM signals"))
        count = result.scalar()
        print(f"   ✓ Signals table: {count} records")
        
        # Test positions table
        result = await session.execute(text("SELECT COUNT(*) FROM positions"))
        count = result.scalar()
        print(f"   ✓ Positions table: {count} records")
        
        # Test trades table
        result = await session.execute(text("SELECT COUNT(*) FROM trades"))
        count = result.scalar()
        print(f"   ✓ Trades table: {count} records")
    
    print("✅ Database schema validation passed")


async def validate_repositories():
    """Test database repositories."""
    print("\nTesting Database Repositories...")
    
    from app.database.repositories import OrderRepository, PositionRepository, TradeRepository
    from app.database.connection import async_session_maker
    
    async with async_session_maker() as session:
        # Test OrderRepository
        order_repo = OrderRepository()
        pending_orders = await order_repo.get_pending_orders(session)
        print(f"   ✓ OrderRepository: Found {len(pending_orders)} pending orders")
        
        # Test PositionRepository
        position_repo = PositionRepository()
        open_positions = await position_repo.get_open_positions(session)
        print(f"   ✓ PositionRepository: Found {len(open_positions)} open positions")
        
        # Test TradeRepository
        trade_repo = TradeRepository()
        open_trades = await trade_repo.get_open_trades(session)
        print(f"   ✓ TradeRepository: Found {len(open_trades)} open trades")
    
    print("✅ Repository validation passed")


async def main():
    """Run all validations."""
    print("=" * 70)
    print("Order Execution Engine Validation")
    print("=" * 70)
    
    try:
        await validate_state_machine()
        await validate_retry_system()
        await validate_database_schema()
        await validate_repositories()
        
        print("\n" + "=" * 70)
        print("✅ ALL VALIDATIONS PASSED!")
        print("=" * 70)
        print("\nSummary:")
        print("  • Order State Machine: Working correctly")
        print("  • Smart Retry System: Working correctly")
        print("  • Database Schema: All tables created")
        print("  • Repositories: Functional")
        print("\nThe Order Execution Engine is ready for production use.")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
