#!/usr/bin/env python3
"""
Cleanup Binance Futures Demo Orders
Cancels all open orders on the Futures Demo account
"""
import asyncio
import aiohttp
import hmac
import hashlib
import time
from urllib.parse import urlencode


class BinanceFuturesDemoClient:
    """Direct HTTP client for Binance Futures Demo API"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = 'https://demo-fapi.binance.com'
    
    def _generate_signature(self, params: dict) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def fetch_open_orders(self, symbol: str = None):
        """Fetch all open orders"""
        timestamp = int(time.time() * 1000)
        params = {'timestamp': timestamp}
        if symbol:
            params['symbol'] = symbol
        
        signature = self._generate_signature(params)
        url = f'{self.base_url}/fapi/v1/openOrders'
        
        headers = {'X-MBX-APIKEY': self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={**params, 'signature': signature}, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise Exception(f"Failed to fetch orders: {resp.status} - {error_text}")
    
    async def cancel_order(self, symbol: str, order_id: int):
        """Cancel a specific order"""
        timestamp = int(time.time() * 1000)
        params = {
            'symbol': symbol,
            'orderId': order_id,
            'timestamp': timestamp
        }
        
        signature = self._generate_signature(params)
        url = f'{self.base_url}/fapi/v1/order'
        
        headers = {'X-MBX-APIKEY': self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, params={**params, 'signature': signature}, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise Exception(f"Failed to cancel order {order_id}: {resp.status} - {error_text}")
    
    async def cancel_all_orders(self, symbol: str):
        """Cancel all open orders for a symbol"""
        timestamp = int(time.time() * 1000)
        params = {
            'symbol': symbol,
            'timestamp': timestamp
        }
        
        signature = self._generate_signature(params)
        url = f'{self.base_url}/fapi/v1/allOpenOrders'
        
        headers = {'X-MBX-APIKEY': self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, params={**params, 'signature': signature}, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get('code') == 200 or 'msg' in result
                else:
                    error_text = await resp.text()
                    raise Exception(f"Failed to cancel all orders: {resp.status} - {error_text}")


async def main():
    """Main cleanup function"""
    import sys
    from pathlib import Path
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from app.config import settings
    
    # Use paper trading keys for demo
    api_key = settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY
    api_secret = settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET
    
    if not api_key or not api_secret:
        print("❌ Error: No API credentials configured")
        return
    
    client = BinanceFuturesDemoClient(api_key, api_secret)
    
    print("=" * 70)
    print("🧹 BINANCE FUTURES DEMO - ORDER CLEANUP")
    print("=" * 70)
    print(f"\nEndpoint: {client.base_url}\n")
    
    try:
        # Step 1: Fetch all open orders
        print("📋 Step 1: Fetching open orders...")
        orders = await client.fetch_open_orders()
        print(f"   Found {len(orders)} open orders\n")
        
        if not orders:
            print("✅ No open orders to cancel. Clean state confirmed!")
            return
        
        # Group orders by symbol
        symbols = {}
        for order in orders:
            symbol = order['symbol']
            if symbol not in symbols:
                symbols[symbol] = []
            symbols[symbol].append(order)
        
        print("📊 Orders by symbol:")
        for symbol, symbol_orders in symbols.items():
            print(f"   • {symbol}: {len(symbol_orders)} orders")
            for order in symbol_orders[:2]:  # Show first 2
                side = order['side']
                qty = order['origQty']
                price = order['price']
                print(f"     - {side} {qty} @ {price}")
            if len(symbol_orders) > 2:
                print(f"     ... and {len(symbol_orders) - 2} more")
        
        # Step 2: Cancel orders by symbol
        print(f"\n🗑️  Step 2: Cancelling orders...")
        cancelled_count = 0
        failed_count = 0
        
        for symbol, symbol_orders in symbols.items():
            print(f"\n   Cancelling {len(symbol_orders)} {symbol} orders...")
            try:
                success = await client.cancel_all_orders(symbol)
                if success:
                    print(f"   ✅ Successfully cancelled all {symbol} orders")
                    cancelled_count += len(symbol_orders)
                else:
                    print(f"   ❌ Failed to cancel {symbol} orders")
                    failed_count += len(symbol_orders)
            except Exception as e:
                print(f"   ❌ Error cancelling {symbol}: {e}")
                failed_count += len(symbol_orders)
        
        # Step 3: Verify cleanup
        print(f"\n🔍 Step 3: Verifying cleanup...")
        remaining_orders = await client.fetch_open_orders()
        
        print(f"\n{'=' * 70}")
        print("📊 CLEANUP SUMMARY")
        print(f"{'=' * 70}")
        print(f"Total orders found:    {len(orders)}")
        print(f"Successfully cancelled: {cancelled_count}")
        print(f"Failed to cancel:      {failed_count}")
        print(f"Remaining orders:      {len(remaining_orders)}")
        
        if len(remaining_orders) == 0:
            print(f"\n✅ SUCCESS! All orders cancelled. Account is clean.")
        else:
            print(f"\n⚠️  WARNING: {len(remaining_orders)} orders still remain:")
            for order in remaining_orders:
                print(f"   - {order['symbol']} {order['side']} {order['origQty']} @ {order['price']}")
        
    except Exception as e:
        print(f"\n❌ Cleanup failed: {type(e).__name__}: {str(e)[:200]}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
