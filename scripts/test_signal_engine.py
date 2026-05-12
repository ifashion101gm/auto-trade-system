"""Test Signal Engine architecture end-to-end."""
import asyncio
import sys
sys.path.insert(0, '/home/admin/.openclaw/workspace/auto-trade-system')

from app.strategy.strategy_manager import StrategyManager
from app.strategy.signal_proposal import SignalProposal

async def test_strategies():
    """Test all strategy modules."""
    print("Testing Signal Engine...")
    
    # Test 1: Mean Reversion Signal (oversold condition)
    print("\n=== Test 1: Mean Reversion (Oversold) ===")
    market_data_mr = {
        'symbol': 'BTC/USDT',
        'current_price': 48900.0,  # Below lower BB
        'rsi': 25.0,  # Oversold
        'ma_20': 49500.0,
        'ma_50': 49000.0,
        'macd': 100.0,
        'atr': 500.0,
        'volume_24h': 1000000,
        'regime': 'Normal',
        'volatility': 0.02,
        'bb_upper': 51000.0,
        'bb_middle': 50000.0,
        'bb_lower': 49000.0,
        'ohlcv': [[50000, 50500, 51000, 49500, 50000, 100000] for _ in range(30)]
    }
    
    mgr = StrategyManager(use_ai_filter=False)
    signal = await mgr.generate_signals(market_data_mr)
    
    if signal:
        print(f"✅ Signal generated: {signal.strategy_name} - {signal.side}")
        print(f"   Confidence: {signal.confidence}")
        print(f"   Entry: ${signal.entry_price}")
        print(f"   Stop Loss: ${signal.stop_loss}")
        print(f"   Take Profit: ${signal.take_profit}")
    else:
        print("❌ No signal generated")
    
    # Test 2: Trend Following Signal (golden cross)
    print("\n=== Test 2: Trend Following (Golden Cross) ===")
    market_data_trend = {
        'symbol': 'BTC/USDT',
        'current_price': 50000.0,
        'rsi': 55.0,
        'ma_20': 50500.0,  # Above MA50
        'ma_50': 49000.0,
        'macd': 150.0,  # Positive
        'atr': 500.0,
        'volume_24h': 1000000,
        'regime': 'Normal',
        'volatility': 0.02,
        'bb_upper': 51000.0,
        'bb_middle': 50000.0,
        'bb_lower': 49000.0,
        'ohlcv': [[50000, 50500, 51000, 49500, 50000, 100000] for _ in range(30)]
    }
    
    signal = await mgr.generate_signals(market_data_trend)
    
    if signal:
        print(f"✅ Signal generated: {signal.strategy_name} - {signal.side}")
        print(f"   Confidence: {signal.confidence}")
        print(f"   Entry: ${signal.entry_price}")
        print(f"   Stop Loss: ${signal.stop_loss}")
        print(f"   Take Profit: ${signal.take_profit}")
    else:
        print("❌ No signal generated")
    
    print("\nStrategy Info:")
    for info in mgr.get_strategy_info():
        print(f"  - {info['name']}: {info['parameters']}")
    
    print("\n✅ Signal Engine test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_strategies())
