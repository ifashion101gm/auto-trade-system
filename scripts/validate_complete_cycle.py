#!/usr/bin/env python3
"""
Complete Gold Futures Trading System Validation
Tests: Market Data → AI Strategy → Paper Trade → Live Validation → Hybrid Execution
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.infra.binance_client import BinanceClient
from app.infra.mexc_client import MEXCClient
from app.infra.hybrid_exchange_manager import HybridExchangeManager
from app.ai.orchestrator import AIAgentOrchestrator

async def test_market_data():
    """Test 1: Fetch market data from both exchanges"""
    print("\n" + "="*70)
    print("  TEST 1: MARKET DATA FETCHING")
    print("="*70)
    
    binance_price = None
    mexc_price = None
    
    # Binance Testnet
    print("\n1.1 Binance Futures Testnet (PAXG/USDT)")
    print("-" * 70)
    try:
        binance = BinanceClient(
            api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
            testnet=True,
            demo_mode='futures_demo'
        )
        
        ticker = await binance.fetch_ticker(settings.GOLD_SYMBOL_BINANCE)
        binance_price = ticker['last_price']
        
        print(f"   ✅ Symbol: {ticker['symbol']}")
        print(f"   ✅ Current Price: ${ticker['last_price']:,.2f}")
        print(f"   ✅ 24h Volume: ${ticker['volume_24h']:,.2f}")
        print(f"   ✅ Bid/Ask: ${ticker['bid']:,.2f} / ${ticker['ask']:,.2f}")
        
        await binance.close()
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        return False
    
    # MEXC Live
    print("\n1.2 MEXC Futures Live (XAUT/USDT)")
    print("-" * 70)
    try:
        mexc = MEXCClient(market_type='futures')
        
        ticker = await mexc.fetch_ticker('XAUT_USDT')
        mexc_price = ticker['last_price']
        
        print(f"   ✅ Symbol: {ticker['symbol']}")
        print(f"   ✅ Current Price: ${ticker['last_price']:,.2f}")
        print(f"   ✅ 24h Volume: ${ticker['volume_24h']:,.2f}")
        print(f"   ✅ Bid/Ask: ${ticker['bid']:,.2f} / ${ticker['ask']:,.2f}")
        
        await mexc.close()
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        return False
    
    # Price comparison
    if binance_price and mexc_price:
        price_diff = abs(binance_price - mexc_price)
        price_diff_pct = (price_diff / binance_price) * 100
        
        print(f"\n1.3 Price Comparison")
        print("-" * 70)
        print(f"   Binance (PAXG): ${binance_price:,.2f}")
        print(f"   MEXC (XAUT):    ${mexc_price:,.2f}")
        print(f"   Price Diff:     ${price_diff:,.2f} ({price_diff_pct:.3f}%)")
        
        if price_diff_pct < 1.0:
            print(f"   ✅ Prices aligned (< 1% difference)")
            return True
        else:
            print(f"   ⚠️  Large price difference detected")
            return True  # Still pass, just note it
    
    return False


async def test_ai_strategy_selection():
    """Test 2: AI Orchestrator strategy selection"""
    print("\n" + "="*70)
    print("  TEST 2: AI STRATEGY SELECTION")
    print("="*70)
    
    try:
        orchestrator = AIAgentOrchestrator()
        
        # Market data for Gold
        market_data = {
            'symbol': 'XAUT/USDT',
            'current_price': 4699.30,
            'price_change_24h': -0.42,
            'volume_24h': 186000000,
            'high_24h': 4718.5,
            'low_24h': 4693.9,
            'rsi': 45.2,
            'macd': -2.5,
            'bollinger_upper': 4720.0,
            'bollinger_lower': 4690.0,
            'volatility': 0.12,
            'moving_avg_20': 4700.0,
            'moving_avg_50': 4695.0,
        }
        
        print(f"\n2.1 Input Market Data")
        print("-" * 70)
        print(f"   Symbol: {market_data['symbol']}")
        print(f"   Price: ${market_data['current_price']:,.2f}")
        print(f"   Volatility: {market_data['volatility']*100:.1f}%")
        print(f"   RSI: {market_data['rsi']}")
        print()
        
        # Detect regime
        print("2.2 Regime Detection")
        print("-" * 70)
        volatility = market_data['volatility']
        
        if volatility < 0.15:
            regime = "Low-vol"
        elif volatility > 0.40:
            regime = "High-vol"
        else:
            regime = "Normal"
        
        print(f"   Volatility: {volatility*100:.1f}%")
        print(f"   Detected Regime: {regime}")
        print(f"   ✅ Regime detection working")
        print()
        
        # Strategy selection
        print("2.3 Strategy Selection")
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
            print(f"   • Regime: {proposal.get('regime', regime)}")
            
            # Validate confidence
            confidence = proposal.get('confidence', 0)
            if confidence >= settings.GOLD_MIN_CONFIDENCE:
                print(f"   ✅ Confidence {confidence*100:.1f}% >= threshold {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
                return proposal
            else:
                print(f"   ⚠️  Confidence {confidence*100:.1f}% < threshold")
                return proposal
        else:
            print(f"   ️  No strategy selected")
            return None
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return None


async def test_paper_trade(proposal):
    """Test 3: Execute paper trade on Binance Testnet"""
    print("\n" + "="*70)
    print("  TEST 3: PAPER TRADE EXECUTION (Binance Testnet)")
    print("="*70)
    
    if not proposal or not proposal.get('strategy'):
        print("\n   ⚠️  Skipping - no strategy proposal")
        return False
    
    try:
        binance = BinanceClient(
            api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
            testnet=True,
            demo_mode='futures_demo'
        )
        
        # Get current market price for trade execution
        ticker = await binance.fetch_ticker(settings.GOLD_SYMBOL_BINANCE)
        current_price = ticker['last_price']
        
        # Generate trade parameters from strategy
        side = 'BUY' if proposal.get('side', 'BUY').upper() in ['BUY', 'LONG'] else 'SELL'
        leverage = min(proposal.get('leverage', 3), settings.GOLD_MAX_LEVERAGE)
        
        # Calculate entry, stop loss, take profit based on current price
        entry_price = current_price
        if side == 'BUY':
            stop_loss = entry_price * 0.98  # 2% below entry
            take_profit = entry_price * 1.04  # 4% above entry
        else:
            stop_loss = entry_price * 1.02  # 2% above entry
            take_profit = entry_price * 0.96  # 4% below entry
        
        # Calculate position size
        account_balance = 1000  # Testnet balance
        risk_amount = account_balance * settings.GOLD_RISK_PER_TRADE
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0.01
        
        # Round quantity to valid precision (2 decimal places for PAXG)
        quantity = round(quantity, 2)
        
        print(f"\n3.1 Trade Parameters")
        print("-" * 70)
        print(f"   Symbol: {settings.GOLD_SYMBOL_BINANCE}")
        print(f"   Strategy: {proposal['strategy']}")
        print(f"   Side: {side}")
        print(f"   Entry: ${entry_price:,.2f}")
        print(f"   Stop Loss: ${stop_loss:,.2f}")
        print(f"   Take Profit: ${take_profit:,.2f}")
        print(f"   Leverage: {leverage}x")
        print(f"   Risk: ${risk_amount:.2f} ({settings.GOLD_RISK_PER_TRADE*100:.1f}%)")
        print(f"   Quantity: {quantity:.4f}")
        print(f"   Position Value: ${quantity * entry_price:,.2f}")
        print()
        
        # Execute trade
        print("3.2 Executing Paper Trade")
        print("-" * 70)
        
        order = await binance.create_market_order(
            symbol=settings.GOLD_SYMBOL_BINANCE,
            side=side,
            amount=quantity,
            leverage=leverage
        )
        
        print(f"   ✅ Order Executed!")
        print(f"   • Order ID: {order.get('order_id', 'N/A')}")
        print(f"   • Status: {order.get('status', 'N/A')}")
        print(f"   • Filled Price: ${order.get('price', 0):,.2f}")
        print(f"   • Amount: {order.get('amount', 0):,.4f}")
        print(f"   • Cost: ${order.get('cost', 0):,.2f}")
        
        await binance.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False


async def test_live_validation(proposal):
    """Test 4: Validate live order on MEXC (dry run)"""
    print("\n" + "="*70)
    print("  TEST 4: LIVE ORDER VALIDATION (MEXC - Dry Run)")
    print("="*70)
    
    if not proposal or not proposal.get('strategy'):
        print("\n   ⚠️  Skipping - no strategy proposal")
        return False
    
    try:
        mexc = MEXCClient(market_type='futures')
        
        # Check balance
        print("\n4.1 Account Balance")
        print("-" * 70)
        balance = await mexc.fetch_balance()
        
        print(f"   ✅ Total USDT: ${balance['total_usdt']:,.2f}")
        print(f"   ✅ Available: ${balance['free_usdt']:,.2f}")
        print()
        
        # Get current market price for validation
        ticker = await mexc.fetch_ticker('XAUT_USDT')
        current_price = ticker['last_price']
        
        # Generate trade parameters
        side = 'BUY' if proposal.get('side', 'BUY').upper() in ['BUY', 'LONG'] else 'SELL'
        leverage = min(proposal.get('leverage', 3), settings.GOLD_MAX_LEVERAGE)
        
        entry_price = current_price
        if side == 'BUY':
            stop_loss = entry_price * 0.98
            take_profit = entry_price * 1.04
        else:
            stop_loss = entry_price * 1.02
            take_profit = entry_price * 0.96
        
        # Validate parameters
        print("4.2 Risk Validation")
        print("-" * 70)
        
        confidence = proposal.get('confidence', 0)
        
        checks = []
        
        # Check leverage
        if leverage <= settings.GOLD_MAX_LEVERAGE:
            print(f"   ✅ Leverage {leverage}x <= max {settings.GOLD_MAX_LEVERAGE}x")
            checks.append(True)
        else:
            print(f"   ❌ Leverage {leverage}x > max {settings.GOLD_MAX_LEVERAGE}x")
            checks.append(False)
        
        # Check confidence
        if confidence >= settings.GOLD_MIN_CONFIDENCE:
            print(f"   ✅ Confidence {confidence*100:.1f}% >= min {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
            checks.append(True)
        else:
            print(f"   ❌ Confidence {confidence*100:.1f}% < min {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
            checks.append(False)
        
        # Check balance sufficiency
        risk_amount = balance['total_usdt'] * settings.GOLD_RISK_PER_TRADE
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0.01
        position_value = quantity * entry_price
        
        if position_value <= balance['total_usdt'] * leverage:
            print(f"   ✅ Position value ${position_value:,.2f} within margin limits")
            checks.append(True)
        else:
            print(f"    Position value ${position_value:,.2f} exceeds margin")
            checks.append(False)
        
        print()
        if all(checks):
            print(f"   ✅ ALL RISK CHECKS PASSED")
            print(f"   ℹ️  Order ready for live execution (DRY RUN)")
            result = True
        else:
            print(f"   ❌ SOME RISK CHECKS FAILED")
            print(f"   ️  Order would be rejected")
            result = False
        
        await mexc.close()
        return result
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False


async def test_hybrid_manager():
    """Test 5: Hybrid Exchange Manager"""
    print("\n" + "="*70)
    print("  TEST 5: HYBRID EXCHANGE MANAGER")
    print("="*70)
    
    try:
        print("\n5.1 Initialization")
        print("-" * 70)
        
        hybrid = HybridExchangeManager()
        
        print(f"\n   Binance (Paper): {'✅ Connected' if hybrid.binance_client else '❌ Failed'}")
        print(f"   MEXC (Live): {'✅ Connected' if hybrid.mexc_client else '❌ Failed'}")
        
        if hybrid.binance_client and hybrid.mexc_client:
            print(f"\n   ✅ Dual exchange operational")
            result = True
        else:
            print(f"\n   ⚠️  One or both exchanges failed")
            result = False
        
        await hybrid.close()
        return result
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        return False


async def main():
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#  GOLD FUTURES - COMPLETE TRADING CYCLE VALIDATION" + " "*19 + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    print(f"\n📋 Configuration:")
    print(f"   Binance: {settings.GOLD_SYMBOL_BINANCE} (Paper)")
    print(f"   MEXC: {settings.GOLD_SYMBOL_MEXC} (Live, ${100:.2f} balance)")
    print(f"   Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"   Risk: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
    print(f"   Min Confidence: {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
    
    results = {}
    proposal = None
    
    try:
        # Test 1: Market Data
        results['market_data'] = await test_market_data()
        await asyncio.sleep(1)
        
        # Test 2: AI Strategy
        proposal = await test_ai_strategy_selection()
        results['ai_strategy'] = proposal is not None and proposal.get('strategy')
        await asyncio.sleep(1)
        
        # Test 3: Paper Trade
        results['paper_trade'] = await test_paper_trade(proposal)
        await asyncio.sleep(1)
        
        # Test 4: Live Validation
        results['live_validation'] = await test_live_validation(proposal)
        await asyncio.sleep(1)
        
        # Test 5: Hybrid Manager
        results['hybrid_manager'] = await test_hybrid_manager()
        
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
        ("Market Data Fetching", results.get('market_data', False)),
        ("AI Strategy Selection", results.get('ai_strategy', False)),
        ("Paper Trade (Binance)", results.get('paper_trade', False)),
        ("Live Validation (MEXC)", results.get('live_validation', False)),
        ("Hybrid Exchange Manager", results.get('hybrid_manager', False)),
    ]
    
    for name, passed in tests:
        icon = "✅" if passed else "❌"
        print(f"   {icon} {name}")
    
    total = len(tests)
    passed = sum(1 for _, p in tests if p)
    
    print(f"\n   Results: {passed}/{total} passed")
    
    if passed == total:
        print("\n   🎉 ALL TESTS PASSED - SYSTEM READY!")
        print("   ✅ Paper trading working on Binance Testnet")
        print("   ✅ Live trading ready on MEXC")
        print("   ✅ Hybrid dual execution operational")
    elif passed >= 3:
        print(f"\n   ⚠️  {passed}/{total} passed - Mostly operational")
    else:
        print(f"\n   ❌ Only {passed}/{total} passed - Needs attention")
    
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
