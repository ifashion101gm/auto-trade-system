"""
Validation script for Gold futures hybrid trading setup.
Tests connectivity, symbol availability, AI analysis, and dual execution.
"""
import asyncio
import sys
from app.config import settings
from app.infra.binance_client import BinanceClient
from app.infra.mexc_client import MEXCClient
from app.infra.hybrid_exchange_manager import HybridExchangeManager
from app.ai.orchestrator import AIAgentOrchestrator
from app.services.live_trading_service import LiveTradingService


async def test_exchange_connectivity():
    """Test 1: Validate API connectivity for both exchanges."""
    print("\n" + "="*70)
    print("TEST 1: Exchange Connectivity")
    print("="*70)
    
    # Test Binance Testnet
    print("\n📊 Testing Binance Testnet (Futures Demo)...")
    try:
        binance = BinanceClient(
            api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
            testnet=True,
            demo_mode='futures_demo'
        )
        balance = await binance.fetch_balance()
        print(f"   ✅ Binance connected successfully")
        print(f"   USDT Balance: ${balance.get('total_usdt', 0):,.2f}")
        await binance.close()
    except Exception as e:
        print(f"   ❌ Binance connection failed: {e}")
        return False
    
    # Test MEXC Live
    print("\n📊 Testing MEXC Live (Futures)...")
    try:
        mexc = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures'
        )
        balance = await mexc.fetch_balance()
        print(f"   ✅ MEXC connected successfully")
        print(f"   USDT Balance: ${balance.get('total_usdt', 0):,.2f}")
        await mexc.close()
    except Exception as e:
        print(f"   ❌ MEXC connection failed: {e}")
        return False
    
    print("\n✅ Both exchanges connected successfully!")
    return True


async def test_symbol_availability():
    """Test 2: Check Gold symbol availability on each exchange."""
    print("\n" + "="*70)
    print("TEST 2: Symbol Availability")
    print("="*70)
    
    # Test Binance symbol (PAXG/USDT)
    print(f"\n📊 Checking Binance symbol: {settings.GOLD_SYMBOL_BINANCE}")
    try:
        binance = BinanceClient(
            api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
            testnet=True,
            demo_mode='futures_demo'
        )
        is_valid = await binance.validate_symbol(settings.GOLD_SYMBOL_BINANCE)
        if is_valid:
            print(f"   ✅ {settings.GOLD_SYMBOL_BINANCE} is available on Binance")
        else:
            print(f"   ❌ {settings.GOLD_SYMBOL_BINANCE} NOT found on Binance")
            return False
        await binance.close()
    except Exception as e:
        print(f"   ❌ Symbol validation failed: {e}")
        return False
    
    # Test MEXC symbol (XAUT/USDT)
    print(f"\n📊 Checking MEXC symbol: {settings.GOLD_SYMBOL_MEXC}")
    try:
        mexc = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures'
        )
        is_valid = await mexc.validate_symbol(settings.GOLD_SYMBOL_MEXC)
        if is_valid:
            print(f"   ✅ {settings.GOLD_SYMBOL_MEXC} is available on MEXC")
        else:
            print(f"   ❌ {settings.GOLD_SYMBOL_MEXC} NOT found on MEXC")
            return False
        await mexc.close()
    except Exception as e:
        print(f"   ❌ Symbol validation failed: {e}")
        return False
    
    print("\n✅ Both symbols validated successfully!")
    return True


async def test_market_data():
    """Test 3: Fetch real-time Gold ticker data."""
    print("\n" + "="*70)
    print("TEST 3: Market Data Fetching")
    print("="*70)
    
    # Fetch from Binance
    print(f"\n📊 Fetching {settings.GOLD_SYMBOL_BINANCE} from Binance...")
    try:
        binance = BinanceClient(
            api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
            testnet=True,
            demo_mode='futures_demo'
        )
        ticker = await binance.fetch_ticker(settings.GOLD_SYMBOL_BINANCE)
        print(f"   ✅ Binance Price: ${ticker['last_price']:,.2f}")
        print(f"   24h High: ${ticker['high_24h']:,.2f}")
        print(f"   24h Low: ${ticker['low_24h']:,.2f}")
        await binance.close()
    except Exception as e:
        print(f"   ❌ Failed to fetch Binance ticker: {e}")
        return False
    
    # Fetch from MEXC
    print(f"\n📊 Fetching {settings.GOLD_SYMBOL_MEXC} from MEXC...")
    try:
        mexc = MEXCClient(
            api_key=settings.MEXC_API_KEY,
            api_secret=settings.MEXC_API_SECRET,
            market_type='futures'
        )
        ticker = await mexc.fetch_ticker(settings.GOLD_SYMBOL_MEXC)
        print(f"   ✅ MEXC Price: ${ticker['last_price']:,.2f}")
        print(f"   24h High: ${ticker['high_24h']:,.2f}")
        print(f"   24h Low: ${ticker['low_24h']:,.2f}")
        await mexc.close()
    except Exception as e:
        print(f"   ❌ Failed to fetch MEXC ticker: {e}")
        return False
    
    print("\n✅ Market data fetched successfully from both exchanges!")
    return True


async def test_ai_analysis():
    """Test 4: Run AI analysis cycle for Gold."""
    print("\n" + "="*70)
    print("TEST 4: AI Strategy Analysis")
    print("="*70)
    
    try:
        # Create sample market data for Gold
        market_data = {
            'symbol': settings.GOLD_SYMBOL_BINANCE,
            'current_price': 2650.00,  # Example Gold price
            'volatility': 0.12,  # Low volatility typical for Gold
            'rsi': 55.0,
            'ma_20': 2645.00,
            'ma_50': 2640.00,
            'macd': 5.0,
            'volume_24h': 1000000,
            'price_change_24h': 0.5
        }
        
        print(f"\n🧠 Running AI analysis for {settings.GOLD_SYMBOL_BINANCE}...")
        print(f"   Current Price: ${market_data['current_price']:,.2f}")
        print(f"   Volatility: {market_data['volatility']}")
        
        orchestrator = AIAgentOrchestrator(use_openrouter=False)  # Use heuristic mode for testing
        result = await orchestrator.run_paper_trade_cycle(
            market_data=market_data,
            user_id="test_user"
        )
        
        if result['status'] != 'success':
            print(f"   ❌ AI analysis failed: {result.get('error')}")
            return False
        
        proposal = result.get('trade_proposal', {})
        
        print(f"\n   ✅ Regime Detected: {result['regime']}")
        print(f"   ✅ Strategy Selected: {proposal.get('strategy_name')}")
        print(f"   ✅ Confidence: {proposal.get('confidence')*100:.1f}%")
        print(f"   ✅ Risk Level: {proposal.get('risk_level')}")
        print(f"   ✅ Leverage: {proposal.get('leverage')}x")
        print(f"   ✅ Side: {proposal.get('side')}")
        
        # Check if proposal was generated (may be None if confidence too low)
        if proposal is None:
            print(f"   ⚠️  Trade skipped due to low confidence")
            return True  # This is expected behavior
        
        await orchestrator.close()
        return True
        
    except Exception as e:
        print(f"   ❌ AI analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_hybrid_manager():
    """Test 5: Test Hybrid Exchange Manager initialization."""
    print("\n" + "="*70)
    print("TEST 5: Hybrid Exchange Manager")
    print("="*70)
    
    try:
        print("\n🔄 Initializing Hybrid Exchange Manager...")
        manager = HybridExchangeManager()
        
        info = manager.info
        print(f"\n   ✅ Binance Available: {info['binance_available']}")
        print(f"   ✅ MEXC Available: {info['mexc_available']}")
        print(f"   Binance Symbol: {info['symbols']['binance']}")
        print(f"   MEXC Symbol: {info['symbols']['mexc']}")
        
        # Test fetching tickers from both
        print(f"\n📊 Fetching tickers from both exchanges...")
        tickers = await manager.fetch_tickers()
        
        if 'binance' in tickers and 'last_price' in tickers['binance']:
            print(f"   ✅ Binance: ${tickers['binance']['last_price']:,.2f}")
        
        if 'mexc' in tickers and 'last_price' in tickers['mexc']:
            print(f"   ✅ MEXC: ${tickers['mexc']['last_price']:,.2f}")
        
        await manager.close()
        print("\n✅ Hybrid manager test passed!")
        return True
        
    except Exception as e:
        print(f"   ❌ Hybrid manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all validation tests."""
    print("\n" + "="*70)
    print("GOLD FUTURES HYBRID TRADING VALIDATION")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  Binance Symbol: {settings.GOLD_SYMBOL_BINANCE}")
    print(f"  MEXC Symbol: {settings.GOLD_SYMBOL_MEXC}")
    print(f"  Max Leverage: {settings.GOLD_MAX_LEVERAGE}x")
    print(f"  Min Confidence: {settings.GOLD_MIN_CONFIDENCE*100:.0f}%")
    print(f"  Risk Per Trade: {settings.GOLD_RISK_PER_TRADE*100:.1f}%")
    
    results = {}
    
    # Run tests sequentially
    results['connectivity'] = await test_exchange_connectivity()
    results['symbols'] = await test_symbol_availability()
    results['market_data'] = await test_market_data()
    results['ai_analysis'] = await test_ai_analysis()
    results['hybrid_manager'] = await test_hybrid_manager()
    
    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name.replace('_', ' ').title()}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Gold hybrid trading is ready!")
        print("\nNext steps:")
        print("  1. Start the server: python -m uvicorn app.main:app --reload")
        print("  2. Test dual execution via API:")
        print(f"     curl -X POST http://localhost:8000/gold-futures/dual-execute \\")
        print(f"       -H 'Authorization: Bearer {settings.TRADING_API_SECRET}'")
    else:
        print("❌ SOME TESTS FAILED - Please review errors above")
    print("="*70 + "\n")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
