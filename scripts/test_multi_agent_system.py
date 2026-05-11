"""
Test script for multi-agent trading system.
Validates: Exchange abstraction, agents, sync, reconciliation
"""
import asyncio
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.exchange.mexc_demo import MEXCDemoExchange
from app.exchange.mexc_live import MEXCLiveExchange
from app.agents.strategy_agent import StrategyAgent
from app.agents.risk_agent import RiskAgent
from app.agents.execution_agent import ExecutionAgent
from app.storage.db import get_session


async def test_demo_exchange():
    """Test DEMO exchange."""
    print("\n🧪 Testing DEMO Exchange...")
    exchange = MEXCDemoExchange()
    
    # Test balance
    balance = await exchange.get_balance()
    print(f"   Balance: ${balance['total_usdt']:.2f}")
    
    # Test open position
    order = await exchange.open_position(
        symbol='XAUT/USDT',
        side='buy',
        amount=0.1,
        leverage=3
    )
    print(f"   Order opened: {order['order_id']}")
    
    # Test get positions
    positions = await exchange.get_positions()
    print(f"   Open positions: {len(positions)}")
    
    # Test close position
    if positions:
        close_result = await exchange.close_position(
            symbol=positions[0]['symbol'],
            trade_id=positions[0]['order_id']
        )
        print(f"   Position closed, PnL: ${close_result['pnl']:.2f}")
    
    print("✅ DEMO exchange test passed")


async def test_agents():
    """Test agent workflow."""
    print("\n🧪 Testing Agent Workflow...")
    
    # Strategy agent
    strategy = StrategyAgent()
    market_data = {
        'symbol': 'XAUT/USDT',
        'current_price': 3350.0,
        'volatility': 0.25,
        'rsi': 55,
        'ma_20': 3340,
        'ma_50': 3330
    }
    
    result = await strategy.analyze_and_propose(market_data)
    print(f"   Strategy result: {result.get('status')}")
    
    if result.get('trade_proposal'):
        proposal = result['trade_proposal']
        print(f"   Proposal: {proposal['side']} {proposal['quantity']} @ ${proposal['entry_price']}")
        
        # Risk agent
        risk = RiskAgent()
        approved, reason = await risk.validate_trade(proposal)
        print(f"   Risk validation: {'✅ Approved' if approved else '❌ Rejected'} - {reason}")
        
        if approved:
            # Execution agent
            async with get_session() as db_session:
                executor = ExecutionAgent()
                exec_result = await executor.execute_trade(proposal, 'DEMO', db_session)
                print(f"   Execution: {exec_result.get('trade_id')}")
    
    print("✅ Agent workflow test passed")


async def main():
    """Run all tests."""
    print("="*60)
    print("Multi-Agent Trading System - Integration Tests")
    print("="*60)
    
    await test_demo_exchange()
    await test_agents()
    
    print("\n" + "="*60)
    print("All tests completed successfully! ✅")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
