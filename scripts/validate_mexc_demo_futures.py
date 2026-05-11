#!/usr/bin/env python3
"""
Validate Gold Futures Trading on MEXC Demo Environment.
Tests: Market Data → AI Strategy → Order Execution → Balance Tracking
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.infra.mexc_client import MEXCClient
from app.ai.orchestrator import AIAgentOrchestrator


async def test_mexc_connectivity():
    """Test 1: Verify MEXC Demo Futures connectivity"""
    print("\n" + "="*70)
    print("  TEST 1: MEXC DEMO FUTURES CONNECTIVITY")
    print("="*70)
    
    try:
        mexc = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures'
        )
        
        # Fetch balance
        print("\n1.1 Account Balance")
        print("-" * 70)
        balance = await mexc.fetch_balance()
        
        print(f"   ✅ Total USDT: ${balance['total_usdt']:,.2f}")
        print(f"   ✅ Available: ${balance['free_usdt']:,.2f}")
        print(f"   ✅ Used: ${balance['used_usdt']:,.2f}")
        
        if balance['total_usdt'] < 10:
            print(f"   ⚠️  Warning: Low balance (${balance['total_usdt']:.2f})")
        
        await mexc.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return False


async def test_market_data():
    """Test 2: Fetch XAUT/USDT market data"""
    print("\n" + "="*70)
    print("  TEST 2: MARKET DATA (XAUT/USDT)")
    print("="*70)
    
    try:
        mexc = MEXCClient(market_type='futures')
        
        print("\n2.1 Ticker Data")
        print("-" * 70)
        ticker = await mexc.fetch_ticker('XAUT/USDT')
        
        print(f"   ✅ Symbol: {ticker['symbol']}")
        print(f"   ✅ Current Price: ${ticker['last_price']:,.2f}")
        print(f"   ✅ 24h High: ${ticker['high_24h']:,.2f}")
        print(f"   ✅ 24h Low: ${ticker['low_24h']:,.2f}")
        print(f"   ✅ 24h Volume: ${ticker['volume_24h']:,.2f}")
        print(f"   ✅ Bid/Ask: ${ticker['bid']:,.2f} / ${ticker['ask']:,.2f}")
        
        # Fetch OHLCV
        print("\n2.2 OHLCV Data (1h candles)")
        print("-" * 70)
        ohlcv = await mexc.fetch_ohlcv('XAUT/USDT', timeframe='1h', limit=10)
        
        print(f"   ✅ Fetched {len(ohlcv)} candles")
        if ohlcv:
            latest = ohlcv[-1]
            print(f"   Latest Candle:")
            print(f"     • Open: ${latest[1]:,.2f}")
            print(f"     • High: ${latest[2]:,.2f}")
            print(f"     • Low: ${latest[3]:,.2f}")
            print(f"     • Close: ${latest[4]:,.2f}")
            print(f"     • Volume: ${latest[5]:,.2f}")
        
        await mexc.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return False


async def test_ai_strategy():
    """Test 3: AI Orchestrator strategy selection for Gold"""
    print("\n" + "="*70)
    print("  TEST 3: AI STRATEGY SELECTION")
    print("="*70)
    
    try:
        orchestrator = AIAgentOrchestrator()
        
        # Market data for Gold
        market_data = {
            'symbol': 'XAUT/USDT',
            'current_price': 4700.0,
            'price_change_24h': -0.5,
            'volume_24h': 186000000,
            'high_24h': 4720.0,
            'low_24h': 4690.0,
            'rsi': 45.0,
            'macd': -2.5,
            'volatility': 0.12,
            'ma_20': 4700.0,
            'ma_50': 4695.0,
        }
        
        print(f"\n3.1 Input Market Data")
        print("-" * 70)
        print(f"   Symbol: {market_data['symbol']}")
        print(f"   Price: ${market_data['current_price']:,.2f}")
        print(f"   Volatility: {market_data['volatility']*100:.1f}%")
        print(f"   RSI: {market_data['rsi']}")
        
        # Detect regime
        print("\n3.2 Regime Detection")
        print("-" * 70)
        regime = await orchestrator.detect_regime(market_data)
        print(f"   ✅ Detected Regime: {regime}")
        
        # Select strategy
        print("\n3.3 Strategy Selection")
        print("-" * 70)
        proposal = await orchestrator.select_strategy(market_data, regime=regime)
        
        if proposal and proposal.get('strategy'):
            print(f"   ✅ AI Strategy Selected: {proposal['strategy']}")
            print(f"   • Side: {proposal.get('side', 'N/A').upper()}")
            print(f"   • Entry: ${proposal.get('entry_price', 0):,.2f}")
            print(f"   • Stop Loss: ${proposal.get('stop_loss', 0):,.2f}")
            print(f"   • Take Profit: ${proposal.get('take_profit', 0):,.2f}")
            print(f"   • Leverage: {proposal.get('leverage', 0)}x")
            print(f"   • Confidence: {proposal.get('confidence', 0)*100:.1f}%")
            
            # Validate confidence
            confidence = proposal.get('confidence', 0)
            if confidence >= settings.GOLD_MIN_CONFIDENCE:
                print(f"   ✅ Confidence {confidence*100:.1f}% >= threshold {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
                return proposal
            else:
                print(f"   ⚠️  Confidence {confidence*100:.1f}% < threshold")
                return proposal
        else:
            print(f"   ❌ No strategy selected")
            return None
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return None


async def test_order_execution(proposal):
    """Test 4: Execute paper order on MEXC Demo Futures"""
    print("\n" + "="*70)
    print("  TEST 4: ORDER EXECUTION (MEXC Demo Futures)")
    print("="*70)
    
    if not proposal or not proposal.get('strategy'):
        print("\n   ⚠️  Skipping - no strategy proposal")
        return False
    
    try:
        mexc = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures'
        )
        
        # Get current market price
        ticker = await mexc.fetch_ticker('XAUT/USDT')
        current_price = ticker['last_price']
        
        # Generate trade parameters
        side = 'BUY' if proposal.get('side', 'BUY').upper() in ['BUY', 'LONG'] else 'SELL'
        leverage = min(proposal.get('leverage', 3), settings.GOLD_MAX_LEVERAGE)
        
        entry_price = current_price
        if side == 'BUY':
            stop_loss = entry_price * 0.98  # 2% below
            take_profit = entry_price * 1.04  # 4% above
        else:
            stop_loss = entry_price * 1.02  # 2% above
            take_profit = entry_price * 0.96  # 4% below
        
        # Calculate position size based on risk management
        account_balance = 100  # MEXC demo balance
        risk_amount = account_balance * settings.GOLD_RISK_PER_TRADE
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0.01
        
        # Round to valid precision (2 decimal places for XAUT)
        quantity = round(quantity, 2)
        position_value = quantity * entry_price
        
        print(f"\n4.1 Trade Parameters")
        print("-" * 70)
        print(f"   Symbol: XAUT/USDT")
        print(f"   Strategy: {proposal['strategy']}")
        print(f"   Side: {side}")
        print(f"   Entry: ${entry_price:,.2f}")
        print(f"   Stop Loss: ${stop_loss:,.2f}")
        print(f"   Take Profit: ${take_profit:,.2f}")
        print(f"   Leverage: {leverage}x")
        print(f"   Risk: ${risk_amount:.2f} ({settings.GOLD_RISK_PER_TRADE*100:.1f}%)")
        print(f"   Quantity: {quantity:.2f}")
        print(f"   Position Value: ${position_value:,.2f}")
        
        # Validate risk limits
        print("\n4.2 Risk Validation")
        print("-" * 70)
        
        checks = []
        
        if leverage <= settings.GOLD_MAX_LEVERAGE:
            print(f"   ✅ Leverage {leverage}x <= max {settings.GOLD_MAX_LEVERAGE}x")
            checks.append(True)
        else:
            print(f"   ❌ Leverage exceeds maximum")
            checks.append(False)
        
        confidence = proposal.get('confidence', 0)
        if confidence >= settings.GOLD_MIN_CONFIDENCE:
            print(f"   ✅ Confidence {confidence*100:.1f}% >= min {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
            checks.append(True)
        else:
            print(f"   ❌ Confidence below minimum")
            checks.append(False)
        
        if not all(checks):
            print("\n   ❌ Trade rejected due to risk violations")
            await mexc.close()
            return False
        
        print("\n   ✅ All risk checks passed")
        
        # Execute order
        print("\n4.3 Executing Order")
        print("-" * 70)
        
        order = await mexc.create_market_order(
            symbol='XAUT/USDT',
            side=side.lower(),
            amount=quantity,
            leverage=leverage
        )
        
        print(f"   ✅ Order Executed!")
        print(f"   • Order ID: {order.get('order_id', 'N/A')}")
        print(f"   • Status: {order.get('status', 'N/A')}")
        print(f"   • Filled Price: ${order.get('price', 0):,.2f}")
        print(f"   • Amount: {order.get('amount', 0):,.2f}")
        print(f"   • Cost: ${order.get('cost', 0):,.2f}")
        print(f"   • Fee: {order.get('fee', {})}")
        
        await mexc.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return False


async def test_position_tracking():
    """Test 5: Verify position tracking"""
    print("\n" + "="*70)
    print("  TEST 5: POSITION TRACKING")
    print("="*70)
    
    try:
        mexc = MEXCClient(market_type='futures')
        
        print("\n5.1 Open Positions")
        print("-" * 70)
        positions = await mexc.fetch_open_positions()
        
        if positions:
            print(f"   ✅ Found {len(positions)} open position(s)")
            for pos in positions:
                print(f"\n   Position Details:")
                print(f"     • Symbol: {pos['symbol']}")
                print(f"     • Side: {pos['side']}")
                print(f"     • Size: {pos['size']}")
                print(f"     • Entry Price: ${pos['entry_price']:,.2f}")
                print(f"     • Mark Price: ${pos['mark_price']:,.2f}")
                print(f"     • Unrealized P&L: ${pos['unrealized_pnl']:,.2f}")
                print(f"     • Leverage: {pos['leverage']}x")
        else:
            print(f"   ✅ No open positions")
        
        await mexc.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:150]}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#  MEXC DEMO FUTURES - GOLD TRADING VALIDATION" + " "*23 + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    print(f"\n📋 Configuration:")
    print(f"   Exchange: MEXC Demo Futures")
    print(f"   Symbol: XAUT/USDT")
    print(f"   Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"   Risk: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
    print(f"   Min Confidence: {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
    print(f"   Active Exchange: {settings.ACTIVE_EXCHANGE}")
    
    results = {}
    proposal = None
    
    try:
        # Test 1: Connectivity
        results['connectivity'] = await test_mexc_connectivity()
        await asyncio.sleep(1)
        
        # Test 2: Market Data
        results['market_data'] = await test_market_data()
        await asyncio.sleep(1)
        
        # Test 3: AI Strategy
        proposal = await test_ai_strategy()
        results['ai_strategy'] = proposal is not None and proposal.get('strategy')
        await asyncio.sleep(1)
        
        # Test 4: Order Execution
        results['order_execution'] = await test_order_execution(proposal)
        await asyncio.sleep(1)
        
        # Test 5: Position Tracking
        results['position_tracking'] = await test_position_tracking()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("  📊 VALIDATION SUMMARY")
    print("="*70)
    
    tests = [
        ("MEXC Connectivity", results.get('connectivity', False)),
        ("Market Data Fetching", results.get('market_data', False)),
        ("AI Strategy Selection", results.get('ai_strategy', False)),
        ("Order Execution", results.get('order_execution', False)),
        ("Position Tracking", results.get('position_tracking', False)),
    ]
    
    for name, passed in tests:
        icon = "✅" if passed else "❌"
        print(f"   {icon} {name}")
    
    total = len(tests)
    passed = sum(1 for _, p in tests if p)
    
    print(f"\n   Results: {passed}/{total} passed")
    
    if passed == total:
        print("\n   🎉 ALL TESTS PASSED - MEXC DEMO FUTURES READY!")
        print("   ✅ XAUT/USDT trading operational")
        print("   ✅ AI pipeline integrated")
        print("   ✅ Order execution working")
    elif passed >= 3:
        print(f"\n   ⚠️  {passed}/{total} passed - Mostly operational")
    else:
        print(f"\n   ❌ Only {passed}/{total} passed - Needs attention")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
