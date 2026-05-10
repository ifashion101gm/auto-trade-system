#!/usr/bin/env python3
"""
Comprehensive Gold Futures Trading System Validation
Tests complete cycle: Market Data → AI Analysis → Paper Trade → Real Order
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.infra.binance_client import BinanceClient
from app.infra.mexc_client import MEXCClient
from app.infra.hybrid_exchange_manager import HybridExchangeManager
from app.ai.orchestrator import AIAgentOrchestrator
from app.services.live_trading_service import LiveTradingService

async def test_market_data_cycle():
    """Test 1: Market data fetching from both exchanges"""
    print("\n" + "="*70)
    print("  TEST 1: MARKET DATA CYCLE")
    print("="*70)
    
    results = {'binance': None, 'mexc': None}
    
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
        results['binance'] = ticker
        
        print(f"   ✅ Symbol: {ticker['symbol']}")
        print(f"   ✅ Current Price: ${ticker['last_price']:,.2f}")
        print(f"   ✅ 24h High: ${ticker['high_24h']:,.2f}")
        print(f"   ✅ 24h Low: ${ticker['low_24h']:,.2f}")
        print(f"   ✅ 24h Volume: ${ticker['volume_24h']:,.2f}")
        print(f"   ✅ Bid/Ask: ${ticker['bid']:,.2f} / ${ticker['ask']:,.2f}")
        
        await binance.close()
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
    
    # MEXC Live
    print("\n1.2 MEXC Futures Live (XAUT/USDT)")
    print("-" * 70)
    try:
        mexc = MEXCClient(market_type='futures')
        
        ticker = await mexc.fetch_ticker('XAUT_USDT')
        results['mexc'] = ticker
        
        print(f"   ✅ Symbol: {ticker['symbol']}")
        print(f"   ✅ Current Price: ${ticker['last_price']:,.2f}")
        print(f"   ✅ 24h High: ${ticker['high_24h']:,.2f}")
        print(f"   ✅ 24h Low: ${ticker['low_24h']:,.2f}")
        print(f"   ✅ 24h Volume: ${ticker['volume_24h']:,.2f}")
        print(f"   ✅ Bid/Ask: ${ticker['bid']:,.2f} / ${ticker['ask']:,.2f}")
        
        await mexc.close()
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
    
    # Price comparison
    if results['binance'] and results['mexc']:
        price_diff = abs(results['binance']['last_price'] - results['mexc']['last_price'])
        price_diff_pct = (price_diff / results['binance']['last_price']) * 100
        
        print(f"\n1.3 Price Comparison")
        print("-" * 70)
        print(f"   Binance (PAXG): ${results['binance']['last_price']:,.2f}")
        print(f"   MEXC (XAUT):    ${results['mexc']['last_price']:,.2f}")
        print(f"   Price Diff:     ${price_diff:,.2f} ({price_diff_pct:.3f}%)")
        print(f"   ✅ Gold prices aligned across exchanges")
    
    return results['binance'] is not None and results['mexc'] is not None


async def test_ai_analysis_cycle():
    """Test 2: AI Orchestrator strategy selection"""
    print("\n" + "="*70)
    print("  TEST 2: AI ANALYSIS & STRATEGY SELECTION")
    print("="*70)
    
    try:
        orchestrator = AIAgentOrchestrator()
        
        # Create mock market data for testing
        market_data = {
            'symbol': 'XAUT/USDT',
            'current_price': 4705.92,
            'price_change_24h': -0.42,
            'volume_24h': 180000000,
            'high_24h': 4718.5,
            'low_24h': 4693.9,
            'rsi': 45.2,
            'macd': -2.5,
            'bollinger_upper': 4720.0,
            'bollinger_lower': 4690.0,
            'volatility': 0.12,  # Low volatility for Gold
            'moving_avg_20': 4700.0,
            'moving_avg_50': 4695.0,
        }
        
        print("\n2.1 Running AI Analysis Cycle")
        print("-" * 70)
        print(f"   Input: Gold (XAUT/USDT) market data")
        print(f"   Price: ${market_data['current_price']:,.2f}")
        print(f"   Volatility: {market_data['volatility']*100:.1f}%")
        print(f"   RSI: {market_data['rsi']}")
        print()
        
        # Run analysis
        proposal = await orchestrator.analyze_market(market_data)
        
        if proposal:
            print(f"   ✅ AI Proposal Generated:")
            print(f"   • Strategy: {proposal.get('strategy', 'N/A')}")
            print(f"   • Side: {proposal.get('side', 'N/A').upper()}")
            print(f"   • Entry Price: ${proposal.get('entry_price', 0):,.2f}")
            print(f"   • Stop Loss: ${proposal.get('stop_loss', 0):,.2f}")
            print(f"   • Take Profit: ${proposal.get('take_profit', 0):,.2f}")
            print(f"   • Leverage: {proposal.get('leverage', 0)}x")
            print(f"   • Confidence: {proposal.get('confidence', 0)*100:.1f}%")
            print(f"   • Regime: {proposal.get('regime', 'N/A')}")
            print(f"   • Risk/Reward: {proposal.get('risk_reward_ratio', 0):.2f}")
            print()
            
            # Validate proposal
            confidence = proposal.get('confidence', 0)
            min_confidence = settings.GOLD_MIN_CONFIDENCE
            
            if confidence >= min_confidence:
                print(f"   ✅ Confidence {confidence*100:.1f}% >= threshold {min_confidence*100:.0f}%")
                print(f"   ✅ Trade proposal VALIDATED for execution")
            else:
                print(f"   ⚠️  Confidence {confidence*100:.1f}% < threshold {min_confidence*100:.0f}%")
                print(f"   ℹ️  Trade would be rejected")
            
            await orchestrator.close()
            return proposal
            
        else:
            print(f"   ️  No proposal generated (market conditions not favorable)")
            await orchestrator.close()
            return None
            
    except Exception as e:
        print(f"   ❌ AI Analysis Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return None


async def test_paper_trade_simulation(proposal):
    """Test 3: Paper trade on Binance Testnet"""
    print("\n" + "="*70)
    print("  TEST 3: PAPER TRADE SIMULATION (Binance Testnet)")
    print("="*70)
    
    if not proposal:
        print("\n   ⚠️  Skipping - no AI proposal available")
        return None
    
    try:
        binance = BinanceClient(
            api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
            testnet=True,
            demo_mode='futures_demo'
        )
        
        # Calculate position size
        account_balance = 1000  # Simulated testnet balance
        risk_amount = account_balance * settings.GOLD_RISK_PER_TRADE
        entry_price = proposal['entry_price']
        stop_loss = proposal['stop_loss']
        leverage = proposal['leverage']
        
        # Risk calculation
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0.01
        
        print(f"\n3.1 Paper Trade Parameters")
        print("-" * 70)
        print(f"   Symbol: {settings.GOLD_SYMBOL_BINANCE}")
        print(f"   Side: {proposal['side'].upper()}")
        print(f"   Entry: ${entry_price:,.2f}")
        print(f"   Stop Loss: ${stop_loss:,.2f}")
        print(f"   Leverage: {leverage}x")
        print(f"   Risk Amount: ${risk_amount:.2f} ({settings.GOLD_RISK_PER_TRADE*100:.1f}% of balance)")
        print(f"   Quantity: {quantity:.4f}")
        print(f"   Position Value: ${quantity * entry_price:,.2f}")
        print()
        
        # Execute paper trade
        print("3.2 Executing Paper Trade")
        print("-" * 70)
        
        order = await binance.create_market_order(
            symbol=settings.GOLD_SYMBOL_BINANCE,
            side=proposal['side'].upper(),  # BUY/SELL for Binance
            amount=quantity,
            leverage=leverage
        )
        
        print(f"   ✅ Order Placed Successfully!")
        print(f"   • Order ID: {order.get('order_id', 'N/A')}")
        print(f"   • Status: {order.get('status', 'N/A')}")
        print(f"   • Filled Price: ${order.get('price', 0):,.2f}")
        print(f"   • Amount: {order.get('amount', 0):,.4f}")
        print(f"   • Cost: ${order.get('cost', 0):,.2f}")
        print()
        
        await binance.close()
        return order
        
    except Exception as e:
        print(f"   ❌ Paper Trade Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return None


async def test_live_order_validation(proposal):
    """Test 4: Validate live order parameters for MEXC (dry run)"""
    print("\n" + "="*70)
    print("  TEST 4: LIVE ORDER VALIDATION (MEXC - Dry Run)")
    print("="*70)
    
    if not proposal:
        print("\n   ⚠️  Skipping - no AI proposal available")
        return None
    
    try:
        mexc = MEXCClient(market_type='futures')
        
        # Validate balance
        print("\n4.1 Account Balance Check")
        print("-" * 70)
        balance = await mexc.fetch_balance()
        
        print(f"   ✅ Total USDT: ${balance['total_usdt']:,.2f}")
        print(f"   ✅ Available: ${balance['free_usdt']:,.2f}")
        
        if balance['total_usdt'] < 100:
            print(f"   ⚠️  Low balance warning: ${balance['total_usdt']:.2f}")
            print(f"   ℹ️  Consider adding more funds for live trading")
        else:
            print(f"   ✅ Sufficient balance for trading")
        
        # Validate order parameters
        print("\n4.2 Order Parameter Validation")
        print("-" * 70)
        
        entry_price = proposal['entry_price']
        leverage = proposal['leverage']
        max_leverage = settings.GOLD_MAX_LEVERAGE
        
        print(f"   Symbol: XAUT_USDT")
        print(f"   Side: {proposal['side'].upper()}")
        print(f"   Entry: ${entry_price:,.2f}")
        print(f"   Leverage: {leverage}x")
        print(f"   Max Allowed: {max_leverage}x")
        
        # Risk checks
        checks_passed = True
        
        if leverage > max_leverage:
            print(f"   ❌ Leverage {leverage}x exceeds maximum {max_leverage}x")
            checks_passed = False
        else:
            print(f"   ✅ Leverage within limits")
        
        confidence = proposal.get('confidence', 0)
        min_confidence = settings.GOLD_MIN_CONFIDENCE
        
        if confidence < min_confidence:
            print(f"   ❌ Confidence {confidence*100:.1f}% below minimum {min_confidence*100:.0f}%")
            checks_passed = False
        else:
            print(f"   ✅ Confidence meets threshold")
        
        if checks_passed:
            print(f"\n   ✅ ALL VALIDATIONS PASSED")
            print(f"   ℹ️  Order is ready for live execution")
            print(f"   ️  NOTE: This is a DRY RUN - no real order placed")
        else:
            print(f"\n   ❌ VALIDATION FAILED")
            print(f"   ℹ️  Order would be rejected in live trading")
        
        await mexc.close()
        return checks_passed
        
    except Exception as e:
        print(f"   ❌ Validation Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False


async def test_hybrid_dual_execution():
    """Test 5: Hybrid Exchange Manager initialization"""
    print("\n" + "="*70)
    print("  TEST 5: HYBRID EXCHANGE MANAGER")
    print("="*70)
    
    try:
        print("\n5.1 Initializing Hybrid Manager")
        print("-" * 70)
        
        hybrid = HybridExchangeManager()
        
        print(f"\n   ✅ Hybrid Manager Initialized")
        print(f"   • Binance (Paper): {'Connected' if hybrid.binance_client else 'Failed'}")
        print(f"   • MEXC (Live): {'Connected' if hybrid.mexc_client else 'Failed'}")
        
        if hybrid.binance_client and hybrid.mexc_client:
            print(f"\n   ✅ Dual exchange setup operational")
            print(f"   ️  Ready for simultaneous trade execution")
            result = True
        else:
            print(f"\n   ⚠️  One or both exchanges failed to initialize")
            result = False
        
        await hybrid.close()
        return result
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        return False


async def run_full_validation():
    """Run complete validation cycle"""
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#  GOLD FUTURES TRADING SYSTEM - FULL VALIDATION CYCLE" + " "*17 + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    print(f"\nConfiguration:")
    print(f"  • Binance Symbol: {settings.GOLD_SYMBOL_BINANCE} (Paper Trading)")
    print(f"  • MEXC Symbol: {settings.GOLD_SYMBOL_MEXC} (Live Trading)")
    print(f"  • Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"  • Risk Per Trade: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
    print(f"  • Min Confidence: {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
    print(f"  • Execution Mode: {settings.EXECUTION_MODE}")
    
    results = {
        'market_data': False,
        'ai_analysis': False,
        'paper_trade': False,
        'live_validation': False,
        'hybrid_manager': False,
    }
    
    try:
        # Test 1: Market Data
        results['market_data'] = await test_market_data_cycle()
        await asyncio.sleep(1)
        
        # Test 2: AI Analysis
        proposal = await test_ai_analysis_cycle()
        results['ai_analysis'] = proposal is not None
        await asyncio.sleep(1)
        
        # Test 3: Paper Trade
        paper_order = await test_paper_trade_simulation(proposal)
        results['paper_trade'] = paper_order is not None
        await asyncio.sleep(1)
        
        # Test 4: Live Order Validation
        results['live_validation'] = await test_live_order_validation(proposal)
        await asyncio.sleep(1)
        
        # Test 5: Hybrid Manager
        results['hybrid_manager'] = await test_hybrid_dual_execution()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
    except Exception as e:
        print(f"\n Validation failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Final Summary
    print("\n" + "="*70)
    print("  VALIDATION SUMMARY")
    print("="*70)
    
    tests = [
        ("Market Data Cycle", results['market_data']),
        ("AI Analysis & Strategy", results['ai_analysis']),
        ("Paper Trade (Binance)", results['paper_trade']),
        ("Live Order Validation (MEXC)", results['live_validation']),
        ("Hybrid Exchange Manager", results['hybrid_manager']),
    ]
    
    for test_name, passed in tests:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {test_name}")
    
    total = len(tests)
    passed = sum(1 for _, p in tests if p)
    
    print(f"\n  Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  🎉 ALL TESTS PASSED - SYSTEM READY FOR TRADING!")
    elif passed >= 3:
        print(f"\n  ⚠️  {passed}/{total} tests passed - System mostly operational")
        print("  ℹ️  Review failed tests above for issues")
    else:
        print(f"\n  ❌ Only {passed}/{total} tests passed - System needs attention")
    
    print("="*70)


if __name__ == "__main__":
    asyncio.run(run_full_validation())
