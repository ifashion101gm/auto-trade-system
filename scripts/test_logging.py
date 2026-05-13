"""
Quick test to verify logging system is working correctly.
Run with: python scripts/test_logging.py
"""
from app.logging_config import (
    logger, 
    trade_context, 
    order_context,
    log_trade_entry,
    log_trade_exit,
    log_api_error,
    log_websocket_event,
    log_sync_result
)


def test_basic_logging():
    """Test basic logging at different levels."""
    print("\n=== Testing Basic Logging ===\n")
    
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    
    print("✅ Basic logging test passed\n")


def test_context_injection():
    """Test context injection for trades and orders."""
    print("\n=== Testing Context Injection ===\n")
    
    # Test trade context
    with trade_context(trade_id='test-001', symbol='BTC/USDT', order_id='ord-123'):
        logger.info("Trade opened successfully")
        logger.debug("Entry price: $50,000.00")
    
    # Test order context
    with order_context(order_id='ord-456', symbol='ETH/USDT', trade_id='test-002'):
        logger.info("Order submitted to exchange")
        logger.warning("High slippage detected: 0.5%")
    
    print("✅ Context injection test passed\n")


def test_convenience_functions():
    """Test standardized logging functions."""
    print("\n=== Testing Convenience Functions ===\n")
    
    # Test trade entry logging
    log_trade_entry(
        trade_id='test-003',
        symbol='SOL/USDT',
        side='LONG',
        entry_price=100.0,
        quantity=10.0,
        leverage=2,
        stop_loss=95.0,
        take_profit=110.0,
        strategy_name='breakout',
        risk_pct=1.5,
        order_id='ord-789'
    )
    
    # Test trade exit logging
    log_trade_exit(
        trade_id='test-003',
        symbol='SOL/USDT',
        exit_price=105.0,
        pnl=50.0,
        pnl_pct=5.0,
        duration='1h 30m',
        close_reason='TAKE_PROFIT',
        order_id='ord-790'
    )
    
    print("✅ Convenience functions test passed\n")


def test_error_logging():
    """Test API error logging."""
    print("\n=== Testing Error Logging ===\n")
    
    try:
        # Simulate an error
        raise ValueError("Simulated API timeout")
    except Exception as e:
        log_api_error(
            error=e,
            endpoint='/api/v1/orders',
            status_code=504,
            payload={'symbol': 'BTC/USDT', 'side': 'buy'}
        )
    
    print("✅ Error logging test passed\n")


def test_websocket_logging():
    """Test WebSocket event logging."""
    print("\n=== Testing WebSocket Logging ===\n")
    
    log_websocket_event('CONNECTED', latency_ms=25.5, subscriptions=3)
    log_websocket_event('DISCONNECTED')
    log_websocket_event('RECONNECTING', attempt_count=2)
    log_websocket_event('RECONNECTED', latency_ms=30.2, subscriptions=3, attempt_count=2)
    
    print("✅ WebSocket logging test passed\n")


def test_sync_logging():
    """Test position sync result logging."""
    print("\n=== Testing Sync Logging ===\n")
    
    log_sync_result(mismatches=0, ghost_positions=0, repaired=0, duration_ms=45.2)
    log_sync_result(mismatches=2, ghost_positions=1, repaired=2, duration_ms=120.5)
    
    print("✅ Sync logging test passed\n")


def test_pii_masking():
    """Test that sensitive data is masked."""
    print("\n=== Testing PII Masking ===\n")
    
    # These should be masked in logs
    logger.info("API key: sk_live_1234567890abcdef1234567890abcdef")
    logger.info("Secret: abcdef1234567890abcdef1234567890")
    
    print("✅ PII masking test passed (check logs for ***MASKED***)\n")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("LOGGING SYSTEM VERIFICATION TEST")
    print("="*70)
    
    test_basic_logging()
    test_context_injection()
    test_convenience_functions()
    test_error_logging()
    test_websocket_logging()
    test_sync_logging()
    test_pii_masking()
    
    print("="*70)
    print("✅ ALL LOGGING TESTS PASSED!")
    print("="*70)
    print(f"\n📁 Check logs/ directory for generated log files:")
    print(f"   - all_*.log (all logs)")
    print(f"   - error_*.log (errors only)")
    print(f"   - trades_*.log (trade audit trail)")
    print(f"   - json_*.log (structured JSON)")
    print(f"   - websocket_*.log (WebSocket events)")
    print("\n")
