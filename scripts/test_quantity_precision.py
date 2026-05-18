#!/usr/bin/env python3
"""
Test quantity precision fix for XAUUSDT on Bybit Demo.
Fetches actual instrument info and validates quantity rounding.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.database.connection import async_session_maker
from app.execution.trading_service import LiveTradingService
from app.logging_config import get_logger

logger = get_logger(__name__)


async def test_quantity_precision():
    """Test that quantities are properly rounded for Bybit."""
    
    print("\n" + "="*80)
    print("QUANTITY PRECISION TEST - XAUUSDT")
    print("="*80)
    print(f"Started: {settings.ACTIVE_EXCHANGE} Demo")
    print(f"Symbol: XAUUSDT")
    print("="*80 + "\n")
    
    # Initialize trading service
    service = LiveTradingService()
    
    try:
        # Fetch market data using the same method as trading service
        print("📊 Step 1: Fetching market data...")
        ticker = await service.exchange_manager.fetch_ticker("XAUUSDT")
        ohlcv = await service.exchange_manager.fetch_ohlcv("XAUUSDT", timeframe='1h', limit=100)
        
        current_price = ticker['last_price']
        print(f"   Current price: ${current_price:.2f}\n")
        
        # Fetch instrument info to get qty_step
        print("🔍 Step 2: Fetching instrument info from Bybit...")
        try:
            # Access the underlying pybit client (stored as pybit_session)
            bybit_client = service.exchange_manager.client
            
            if hasattr(bybit_client, 'pybit_session'):
                instrument_response = bybit_client.pybit_session.get_instruments_info(
                    category="linear",
                    symbol="XAUUSDT"
                )
                
                if instrument_response.get('retCode') == 0:
                    result = instrument_response.get('result', {})
                    instrument_list = result.get('list', [])
                    
                    if instrument_list:
                        instrument = instrument_list[0]
                        qty_step = float(instrument.get('lotSizeFilter', {}).get('qtyStep', '0.01'))
                        min_qty = float(instrument.get('lotSizeFilter', {}).get('minTradingQty', '0.001'))
                        max_qty = float(instrument.get('lotSizeFilter', {}).get('maxTradingQty', '1000'))
                        
                        print(f"   ✅ Instrument info retrieved:")
                        print(f"      qty_step (lot size): {qty_step}")
                        print(f"      min_qty: {min_qty}")
                        print(f"      max_qty: {max_qty}")
                        print(f"      price_scale: {instrument.get('priceScale', 'N/A')}")
                        print()
                    else:
                        print(f"   ⚠️  No instrument info found\n")
                        qty_step = 0.01  # Default fallback
                else:
                    print(f"   ⚠️  Failed to get instrument info: {instrument_response.get('retMsg')}\n")
                    qty_step = 0.01
            else:
                print(f"   ⚠️  Pybit session not available, using default qty_step=0.01\n")
                qty_step = 0.01
        except Exception as e:
            print(f"   ⚠️  Error fetching instrument info: {e}\n")
            import traceback
            traceback.print_exc()
            qty_step = 0.01
        
        # Test various raw quantities
        print("🧪 Step 3: Testing quantity rounding...")
        test_quantities = [
            0.02204589,  # Example from previous failure
            0.12345678,
            1.98765432,
            0.00123456,
        ]
        
        for raw_qty in test_quantities:
            # Apply rounding logic (same as in pybit_demo_client.py)
            rounded_qty = round(raw_qty / qty_step) * qty_step
            rounded_qty = round(rounded_qty, 8)  # Avoid floating point issues
            
            print(f"   Raw: {raw_qty:.8f} → Rounded: {rounded_qty:.8f} (step: {qty_step})")
        
        print()
        
        # Now run a trading cycle with proper database session
        print("🚀 Step 4: Running trading cycle...")
        print("="*80 + "\n")
        
        async with async_session_maker() as db_session:
            results = await service.execute_trading_cycle(
                user_id="test_user",
                symbol="XAUUSDT",
                db_session=db_session
            )
        
        print("\n" + "="*80)
        print("CYCLE RESULTS")
        print("="*80)
        print(f"Status: {results.get('status', 'unknown')}")
        print(f"Message: {results.get('message', 'N/A')}")
        
        if results.get('trade_proposal'):
            proposal = results['trade_proposal']
            print(f"\nTrade Proposal:")
            print(f"  Symbol: {proposal.get('symbol')}")
            print(f"  Side: {proposal.get('side')}")
            print(f"  Entry: ${proposal.get('entry_price', 0):.2f}")
            print(f"  Quantity: {proposal.get('quantity', 0):.8f}")
            print(f"  Leverage: {proposal.get('leverage', 0)}x")
            print(f"  Stop Loss: ${proposal.get('stop_loss', 0):.2f}")
            print(f"  Take Profit: ${proposal.get('take_profit', 0):.2f}")
            print(f"  Confidence: {proposal.get('confidence', 0):.2%}")
            
            # Calculate position value
            qty = proposal.get('quantity', 0)
            price = proposal.get('entry_price', 0)
            lev = proposal.get('leverage', 1)
            pos_value = qty * price * lev
            print(f"  Position Value: ${pos_value:.2f}")
        
        if results.get('order_result'):
            order = results['order_result']
            print(f"\nOrder Result:")
            print(f"  Status: {order.get('status', 'unknown')}")
            print(f"  Order ID: {order.get('order_id', 'N/A')}")
            if order.get('error'):
                print(f"  Error: {order.get('error')}")
        
        print("="*80 + "\n")
        
        return results
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'error': str(e)}


if __name__ == "__main__":
    result = asyncio.run(test_quantity_precision())
    
    # Exit with appropriate code
    if result.get('status') == 'success' or result.get('order_result', {}).get('status') == 'filled':
        print("\n✅ TEST PASSED")
        sys.exit(0)
    else:
        print(f"\n⚠️  TEST COMPLETED WITH STATUS: {result.get('status', 'unknown')}")
        sys.exit(1)
