#!/usr/bin/env python3
"""
Clean up existing BTC paper trade and start new Gold futures trading cycle.
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.infra.binance_client import BinanceClient
from app.infra.hybrid_exchange_manager import HybridExchangeManager
from app.ai.orchestrator import AIAgentOrchestrator


async def cleanup_btc_orders():
    """Cancel all open BTC orders on Binance Testnet"""
    print("\n" + "="*70)
    print("  CLEANUP: Canceling Existing BTC Orders")
    print("="*70)
    
    try:
        binance = BinanceClient(
            api_key=settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET,
            testnet=True,
            demo_mode='futures_demo'
        )
        
        # Fetch all open orders for BTC/USDT
        print("\n1. Checking for open BTC orders...")
        try:
            open_orders = await binance.fetch_open_orders('BTC/USDT')
            
            if open_orders:
                print(f"   Found {len(open_orders)} open order(s)")
                
                for order in open_orders:
                    order_id = order.get('id', 'N/A')
                    symbol = order.get('symbol', 'N/A')
                    side = order.get('side', 'N/A')
                    amount = order.get('amount', 0)
                    
                    print(f"\n   Canceling Order:")
                    print(f"   • ID: {order_id}")
                    print(f"   • Symbol: {symbol}")
                    print(f"   • Side: {side}")
                    print(f"   • Amount: {amount}")
                    
                    try:
                        result = await binance.cancel_order(order_id, symbol)
                        print(f"   ✅ Order {order_id} canceled successfully")
                    except Exception as e:
                        print(f"   ❌ Failed to cancel order {order_id}: {str(e)[:80]}")
            else:
                print("   ✅ No open BTC orders found")
        except Exception as e:
            print(f"   ⚠️  Could not fetch open orders (demo mode limitation): {str(e)[:60]}")
            print(f"   ℹ️  Proceeding with position check only")
        
        # Check for open positions
        print("\n2. Checking for open BTC positions...")
        try:
            positions = await binance.fetch_positions(['BTC/USDT'])
            
            if positions:
                active_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
                
                if active_positions:
                    print(f"   Found {len(active_positions)} active position(s)")
                    
                    for pos in active_positions:
                        symbol = pos.get('symbol', 'N/A')
                        side = pos.get('side', 'N/A')
                        contracts = pos.get('contracts', 0)
                        entry_price = pos.get('entryPrice', 0)
                        
                        print(f"\n   Closing Position:")
                        print(f"   • Symbol: {symbol}")
                        print(f"   • Side: {side}")
                        print(f"   • Contracts: {contracts}")
                        print(f"   • Entry Price: ${entry_price:,.2f}")
                        
                        try:
                            result = await binance.close_position(symbol)
                            print(f"   ✅ Position closed successfully")
                            print(f"   • Result: {result.get('status', 'N/A')}")
                        except Exception as e:
                            print(f"   ❌ Failed to close position: {str(e)[:80]}")
                else:
                    print("   ✅ No active BTC positions")
            else:
                print("   ✅ No BTC positions found")
        except Exception as e:
            print(f"   ⚠️  Could not check positions: {str(e)[:80]}")
        
        await binance.close()
        print("\n✅ Cleanup completed")
        return True
        
    except Exception as e:
        print(f"\n❌ Cleanup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def execute_gold_trade_cycle():
    """Execute complete Gold futures trading cycle"""
    print("\n" + "="*70)
    print("  NEW CYCLE: Gold Futures Trading (PAXG/USDT)")
    print("="*70)
    
    try:
        # Initialize components
        hybrid = HybridExchangeManager()
        orchestrator = AIAgentOrchestrator()
        
        print("\n1. Fetching Gold market data...")
        print("-" * 70)
        
        # Get market data from both exchanges
        binance_ticker = await hybrid.binance_client.fetch_ticker(settings.GOLD_SYMBOL_BINANCE)
        mexc_ticker = await hybrid.mexc_client.fetch_ticker('XAUT_USDT')
        
        print(f"   Binance (PAXG): ${binance_ticker['last_price']:,.2f}")
        print(f"   MEXC (XAUT):    ${mexc_ticker['last_price']:,.2f}")
        
        price_diff = abs(binance_ticker['last_price'] - mexc_ticker['last_price'])
        price_diff_pct = (price_diff / binance_ticker['last_price']) * 100
        print(f"   Price Diff:     ${price_diff:,.2f} ({price_diff_pct:.3f}%)")
        
        # Prepare market data for AI analysis
        market_data = {
            'symbol': settings.GOLD_SYMBOL_BINANCE,
            'current_price': binance_ticker['last_price'],
            'price_change_24h': 0,  # Would need historical data
            'volume_24h': binance_ticker.get('volume_24h', 0),
            'high_24h': binance_ticker.get('high_24h', binance_ticker['last_price']),
            'low_24h': binance_ticker.get('low_24h', binance_ticker['last_price']),
            'rsi': 45.0,  # Placeholder - would calculate from OHLCV
            'macd': 0,  # Placeholder
            'volatility': 0.12,  # Low volatility for gold
            'moving_avg_20': binance_ticker['last_price'],  # Placeholder
            'moving_avg_50': binance_ticker['last_price'],  # Placeholder
        }
        
        print("\n2. AI Strategy Selection...")
        print("-" * 70)
        
        # Detect regime
        volatility = market_data['volatility']
        if volatility < 0.15:
            regime = "Low-vol"
        elif volatility > 0.40:
            regime = "High-vol"
        else:
            regime = "Normal"
        
        print(f"   Volatility: {volatility*100:.1f}%")
        print(f"   Regime: {regime}")
        
        # Get strategy from AI
        proposal = await orchestrator.select_strategy(market_data, regime=regime)
        
        print(f"   Strategy: {proposal.get('strategy', 'N/A')}")
        print(f"   Confidence: {proposal.get('confidence', 0)*100:.1f}%")
        
        if not proposal.get('strategy'):
            print("   ❌ No strategy selected by AI")
            await hybrid.close()
            return False
        
        # Generate trade parameters
        print("\n3. Trade Parameters Calculation...")
        print("-" * 70)
        
        side = 'BUY' if proposal.get('side', 'BUY').upper() in ['BUY', 'LONG'] else 'SELL'
        leverage = min(proposal.get('leverage', 3), settings.GOLD_MAX_LEVERAGE)
        
        entry_price = binance_ticker['last_price']
        if side == 'BUY':
            stop_loss = entry_price * 0.98  # 2% below
            take_profit = entry_price * 1.04  # 4% above
        else:
            stop_loss = entry_price * 1.02  # 2% above
            take_profit = entry_price * 0.96  # 4% below
        
        # Calculate position size based on risk management
        account_balance = 1000  # Testnet balance
        risk_amount = account_balance * settings.GOLD_RISK_PER_TRADE
        risk_per_unit = abs(entry_price - stop_loss)
        quantity = (risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0.01
        
        # Round to valid precision
        quantity = round(quantity, 2)
        position_value = quantity * entry_price
        
        print(f"   Symbol: {settings.GOLD_SYMBOL_BINANCE}")
        print(f"   Side: {side}")
        print(f"   Entry: ${entry_price:,.2f}")
        print(f"   Stop Loss: ${stop_loss:,.2f}")
        print(f"   Take Profit: ${take_profit:,.2f}")
        print(f"   Leverage: {leverage}x")
        print(f"   Risk: ${risk_amount:.2f} ({settings.GOLD_RISK_PER_TRADE*100:.1f}%)")
        print(f"   Quantity: {quantity:.2f}")
        print(f"   Position Value: ${position_value:,.2f}")
        
        # Validate against risk limits
        print("\n4. Risk Validation...")
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
            print(f"   ❌ Confidence below minimum threshold")
            checks.append(False)
        
        if not all(checks):
            print("\n   ❌ Trade rejected due to risk violations")
            await hybrid.close()
            return False
        
        print("\n   ✅ All risk checks passed")
        
        # Execute paper trade on Binance Testnet
        print("\n5. Executing Paper Trade (Binance Testnet)...")
        print("-" * 70)
        
        order = await hybrid.binance_client.create_market_order(
            symbol=settings.GOLD_SYMBOL_BINANCE,
            side=side,
            amount=quantity,
            leverage=leverage
        )
        
        print(f"   ✅ Order Executed!")
        print(f"   • Order ID: {order.get('order_id', 'N/A')}")
        print(f"   • Status: {order.get('status', 'N/A')}")
        print(f"   • Filled Price: ${order.get('price', 0):,.2f}")
        print(f"   • Amount: {order.get('amount', 0):,.2f}")
        print(f"   • Cost: ${order.get('cost', 0):,.2f}")
        
        # Validate live readiness on MEXC
        print("\n6. Live Validation (MEXC - Dry Run)...")
        print("-" * 70)
        
        mexc_balance = await hybrid.mexc_client.fetch_balance()
        print(f"   MEXC Balance: ${mexc_balance['total_usdt']:,.2f}")
        
        # Calculate position value for $100 account
        live_risk_amount = mexc_balance['total_usdt'] * settings.GOLD_RISK_PER_TRADE
        live_quantity = (live_risk_amount * leverage) / risk_per_unit if risk_per_unit > 0 else 0.01
        live_quantity = round(live_quantity, 2)
        live_position_value = live_quantity * entry_price
        
        print(f"   Live Trade Parameters:")
        print(f"   • Risk Amount: ${live_risk_amount:.2f}")
        print(f"   • Quantity: {live_quantity:.2f}")
        print(f"   • Position Value: ${live_position_value:,.2f}")
        
        if live_position_value <= mexc_balance['total_usdt'] * leverage:
            print(f"   ✅ Position within margin limits")
            print(f"   ℹ️  Ready for live execution when enabled")
        else:
            print(f"   ⚠️  Position exceeds available margin")
        
        await hybrid.close()
        
        print("\n" + "="*70)
        print("  🎉 GOLD FUTURES TRADE CYCLE COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"\n   Summary:")
        print(f"   • Symbol: {settings.GOLD_SYMBOL_BINANCE}")
        print(f"   • Side: {side}")
        print(f"   • Strategy: {proposal['strategy']}")
        print(f"   • Regime: {regime}")
        print(f"   • Order ID: {order.get('order_id', 'N/A')}")
        print(f"   • Entry: ${entry_price:,.2f}")
        print(f"   • Stop Loss: ${stop_loss:,.2f}")
        print(f"   • Take Profit: ${take_profit:,.2f}")
        print(f"   • Leverage: {leverage}x")
        print(f"   • Confidence: {confidence*100:.1f}%")
        print(f"   • Risk: ${risk_amount:.2f}")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Gold trade cycle failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#  CLEANUP BTC & START GOLD FUTURES TRADING CYCLE" + " "*22 + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    # Step 1: Clean up existing BTC orders
    cleanup_success = await cleanup_btc_orders()
    
    if cleanup_success:
        print("\n⏳ Waiting 2 seconds before starting Gold cycle...")
        await asyncio.sleep(2)
        
        # Step 2: Execute new Gold futures cycle
        gold_success = await execute_gold_trade_cycle()
        
        if gold_success:
            print("\n✅ All operations completed successfully!")
        else:
            print("\n⚠️  Gold trade cycle had issues")
    else:
        print("\n⚠️  Cleanup had issues, but proceeding with Gold cycle anyway...")
        await asyncio.sleep(2)
        await execute_gold_trade_cycle()
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
