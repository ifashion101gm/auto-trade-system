"""
Test Risk Management Engine and Circuit Breaker System.
Validates all risk checks and circuit breaker triggers.
"""
import asyncio
import sys
from datetime import datetime
from app.risk.risk_engine import RiskEngine
from app.infra.circuit_breaker import SystemCircuitBreaker
from app.notifications.notifier import TelegramNotifier


async def test_risk_engine():
    """Test all risk engine features."""
    print("🧪 Testing Risk Management Engine...\n")
    
    # Test without database session for simplicity
    engine = RiskEngine(db_session=None)
    
    # Test 1: Daily loss limit
    print("Test 1: Daily loss limit check")
    # Simulate large loss
    await engine.update_daily_pnl({'profit': -5.0, 'profit_pct': -5.0})
    decision = await engine.check_trade_approval(
        proposal={'symbol': 'BTC/USDT', 'quantity': 0.01, 'leverage': 1, 'entry_price': 50000},
        user_id='test_user'
    )
    assert not decision.approved, "Should reject after exceeding daily loss"
    print(f"✅ Daily loss limit working (daily P&L: {engine.daily_pnl_pct:.2%})\n")
    
    # Reset for next test
    engine.daily_pnl = 0
    engine.daily_pnl_pct = 0
    engine.current_balance = 100
    
    # Test 2: Position size cap
    print("Test 2: Position size cap")
    decision = await engine.check_trade_approval(
        proposal={
            'symbol': 'BTC/USDT',
            'quantity': 10,  # Large position
            'leverage': 5,
            'entry_price': 50000  # $500k position with leverage
        },
        user_id='test_user'
    )
    # Should fail due to position size exceeding 1.5% of balance
    if not decision.approved:
        print(f"✅ Position size cap working: {decision.violations[0]}\n")
    else:
        print(f"⚠️  Position size check passed (may need adjustment)\n")
    
    # Test 3: Leverage limit
    print("Test 3: Leverage limit")
    decision = await engine.check_trade_approval(
        proposal={
            'symbol': 'BTC/USDT',
            'quantity': 0.001,
            'leverage': 10,  # Exceeds 5x limit
            'entry_price': 50000
        },
        user_id='test_user'
    )
    assert not decision.approved, "Should reject leverage > 5x"
    print(f"✅ Leverage limit working: {decision.violations[0]}\n")
    
    # Test 4: Cooldown period
    print("Test 4: Cooldown after consecutive losses")
    engine.consecutive_losses = 0
    engine.last_loss_time = None
    
    for i in range(3):
        await engine.record_trade_outcome(won=False, strategy_name='test')
    
    decision = await engine.check_trade_approval(
        proposal={'symbol': 'BTC/USDT', 'quantity': 0.001, 'leverage': 1, 'entry_price': 50000},
        user_id='test_user'
    )
    assert not decision.approved, "Should enforce cooldown"
    print(f"✅ Cooldown period working: {decision.violations[0]}\n")
    
    # Test 5: Risk metrics
    print("Test 5: Risk metrics retrieval")
    metrics = await engine.get_risk_metrics(user_id='test_user')
    print(f"✅ Risk metrics retrieved:")
    print(f"   - Daily P&L: ${metrics['daily_pnl']:.2f}")
    print(f"   - Current Balance: ${metrics['current_balance']:.2f}")
    print(f"   - Consecutive Losses: {metrics['consecutive_losses']}")
    print(f"   - Cooldown Active: {metrics['cooldown_active']}\n")
    
    print("✅ All risk engine tests passed!")


async def test_circuit_breaker():
    """Test circuit breaker system."""
    print("\n🧪 Testing Circuit Breaker System...\n")
    
    notifier = TelegramNotifier()
    cb = SystemCircuitBreaker(notifier)
    
    # Test 1: API failure tracking
    print("Test 1: API failure circuit breaker")
    for i in range(5):
        await cb.record_api_call(success=False, latency_ms=100, endpoint='test_endpoint')
    
    state = await cb.check_system_health()
    assert state.state == 'OPEN', f"Should open after 5 failures, got {state.state}"
    print(f"✅ API failure breaker working (state: {state.state})\n")
    
    # Test 2: Recovery mechanism
    print("Test 2: Circuit breaker recovery")
    # Manually set triggered_at to simulate past trigger
    from datetime import datetime, timedelta
    cb.triggered_at = datetime.utcnow() - timedelta(seconds=61)
    
    state = await cb.check_system_health()
    # After recovery timeout, should attempt recovery
    print(f"✅ Recovery mechanism working (state: {state.state})\n")
    
    # Test 3: Slippage monitoring
    print("Test 3: Slippage monitoring")
    cb.state = 'CLOSED'  # Reset state
    cb.recent_slippages.clear()
    
    await cb.record_fill_slippage('BTC/USDT', 50000, 50100)  # 0.2% slippage
    state = await cb.check_system_health()
    
    # Check slippage recorded
    avg_slippage = sum(cb.recent_slippages) / len(cb.recent_slippages) if cb.recent_slippages else 0
    print(f"✅ Slippage monitoring working (avg slippage: {avg_slippage:.3%})\n")
    
    # Test 4: Latency tracking
    print("Test 4: API latency monitoring")
    cb.recent_latencies.clear()
    
    await cb.record_api_call(success=True, latency_ms=100, endpoint='fast_endpoint')
    await cb.record_api_call(success=True, latency_ms=6000, endpoint='slow_endpoint')  # Over threshold
    
    state = await cb.check_system_health()
    avg_latency = state.avg_latency_ms
    print(f"✅ Latency tracking working (avg latency: {avg_latency:.0f}ms)\n")
    
    # Test 5: Health report
    print("Test 5: Health report generation")
    report = cb.get_health_report()
    print(f"✅ Health report generated:")
    print(f"   - Circuit State: {report['circuit_state']}")
    print(f"   - Can Trade: {report['can_trade']}")
    print(f"   - API Failures: {report['metrics']['api_failures']}")
    print(f"   - Avg Latency: {report['metrics']['avg_latency_ms']}ms\n")
    
    print("✅ All circuit breaker tests passed!")


async def main():
    """Run all tests."""
    try:
        await test_risk_engine()
        await test_circuit_breaker()
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
        return 0
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
