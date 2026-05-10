"""
Binance Testnet/Mainnet client for live order execution.
Uses ccxt library for unified exchange API access.
"""
import ccxt.async_support as ccxt
from typing import Dict, Any, Optional, List
from app.config import settings


class BinanceClient:
    """
    Binance exchange client for testnet and mainnet trading.
    
    Features:
    - Real order placement (market/limit orders)
    - Order status tracking
    - Position management
    - Market data fetching
    - Fee calculation
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: Optional[bool] = None,
        demo_mode: Optional[str] = None
    ):
        """
        Initialize Binance client.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet/demo mode (True) or mainnet (False)
            demo_mode: Type of demo mode - 'spot_demo', 'futures_demo', or 'testnet'
        """
        self.api_key = api_key or settings.BINANCE_API_KEY
        self.api_secret = api_secret or settings.BINANCE_API_SECRET
        self.testnet = testnet if testnet is not None else settings.BINANCE_TESTNET
        self.demo_mode = demo_mode or getattr(settings, 'BINANCE_DEMO_MODE', 'spot_demo')
        
        # Use paper keys for testnet if main keys are missing
        if self.testnet and (not self.api_key or not self.api_secret):
            self.api_key = settings.BINANCE_PAPER_API_KEY
            self.api_secret = settings.BINANCE_PAPER_API_SECRET
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Binance API credentials not configured")
        
        # Configure exchange based on demo mode
        exchange_config = {
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'warnOnFetchOpenOrdersWithoutSymbol': False  # Suppress warning
            }
        }
        
        # Set default type and URLs based on demo mode
        if self.testnet:
            if self.demo_mode == 'futures_demo':
                # Futures Demo Trading - Use demo-fapi.binance.com
                exchange_config['options']['defaultType'] = 'future'
                self.exchange = ccxt.binance(exchange_config)
                
                # Override API endpoints for Futures Demo
                base_url = 'https://demo-fapi.binance.com'
                self.exchange.urls['api'] = {
                    'public': f'{base_url}/fapi/v1',
                    'private': f'{base_url}/fapi/v1',
                    'v2Public': f'{base_url}/fapi/v2',
                    'v2Private': f'{base_url}/fapi/v2',
                }
                print(f"✅ Binance Client initialized (FUTURES DEMO MODE)")
                print(f"   Endpoint: {base_url}")
                
            elif self.demo_mode == 'spot_demo':
                # Spot Demo Trading
                exchange_config['options']['defaultType'] = 'spot'
                self.exchange = ccxt.binance(exchange_config)
                # Enable sandbox mode for spot demo
                self.exchange.set_sandbox_mode(True)
                print(f"✅ Binance Client initialized (SPOT DEMO MODE)")
                print(f"   Note: Ensure your account has Demo Trading enabled")
                
            else:  # testnet (legacy)
                exchange_config['options']['defaultType'] = 'spot'
                self.exchange = ccxt.binance(exchange_config)
                print(f"✅ Binance Client initialized (TESTNET - SPOT)")
        else:
            exchange_config['options']['defaultType'] = 'spot'
            self.exchange = ccxt.binance(exchange_config)
            print(f"⚠️  Binance Client initialized (MAINNET - LIVE TRADING!)")
        
        # Enable sandbox mode for spot demo/testnet
        if self.testnet and self.demo_mode in ['spot_demo', 'testnet']:
            try:
                self.exchange.set_sandbox_mode(True)
                print(f"   Sandbox mode: Enabled")
            except Exception as e:
                print(f"   ⚠️  Sandbox mode warning: {e}")
    
    async def close(self):
        """Close exchange connection."""
        await self.exchange.close()
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance.
        
        Returns:
            Dictionary with balance information
        """
        try:
            balance = await self.exchange.fetch_balance()
            return {
                'total_usdt': balance.get('USDT', {}).get('total', 0),
                'free_usdt': balance.get('USDT', {}).get('free', 0),
                'used_usdt': balance.get('USDT', {}).get('used', 0),
                'balances': {k: v['total'] for k, v in balance.items() 
                           if isinstance(v, dict) and 'total' in v and v['total'] > 0}
            }
        except Exception as e:
            raise Exception(f"Failed to fetch balance: {str(e)}")
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time ticker data.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            
        Returns:
            Ticker data with price, volume, etc.
        """
        try:
            # For Futures Demo mode, use direct HTTP request to avoid ccxt issues
            if self.testnet and self.demo_mode == 'futures_demo':
                return await self._fetch_ticker_futures_demo(symbol)
            
            # Use ccxt for other modes
            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last_price': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'high_24h': ticker['high'],
                'low_24h': ticker['low'],
                'volume_24h': ticker['quoteVolume'],
                'timestamp': ticker['timestamp']
            }
        except Exception as e:
            raise Exception(f"Failed to fetch ticker for {symbol}: {str(e)}")
    
    async def _fetch_ticker_futures_demo(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch ticker data using direct HTTP request for Futures Demo mode.
        Bypasses ccxt's market loading which fails with demo endpoints.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            
        Returns:
            Ticker data dictionary
        """
        import aiohttp
        
        # Convert symbol format (BTC/USDT -> BTCUSDT)
        symbol_clean = symbol.replace('/', '')
        base_url = 'https://demo-fapi.binance.com'
        
        try:
            async with aiohttp.ClientSession() as session:
                # Fetch 24hr ticker
                url = f'{base_url}/fapi/v1/ticker/24hr?symbol={symbol_clean}'
                async with session.get(url) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"HTTP {resp.status}: {error_text}")
                    
                    data = await resp.json()
                    
                    # Note: Futures Demo ticker doesn't include bid/ask prices
                    return {
                        'symbol': symbol,
                        'last_price': float(data['lastPrice']),
                        'bid': float(data.get('bidPrice', data['lastPrice'])),  # Fallback to last price
                        'ask': float(data.get('askPrice', data['lastPrice'])),  # Fallback to last price
                        'high_24h': float(data['highPrice']),
                        'low_24h': float(data['lowPrice']),
                        'volume_24h': float(data.get('quoteVolume', data.get('volume', 0))),
                        'timestamp': int(data['closeTime'])
                    }
        except Exception as e:
            raise Exception(f"Failed to fetch ticker via HTTP: {str(e)}")
    
    async def _fetch_ohlcv_futures_demo(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List]:
        """
        Fetch OHLCV data using direct HTTP request for Futures Demo mode.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle interval
            limit: Number of candles
            
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        import aiohttp
        
        # Convert symbol format and timeframe
        symbol_clean = symbol.replace('/', '')
        base_url = 'https://demo-fapi.binance.com'
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f'{base_url}/fapi/v1/klines'
                params = {
                    'symbol': symbol_clean,
                    'interval': timeframe,
                    'limit': limit
                }
                
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"HTTP {resp.status}: {error_text}")
                    
                    data = await resp.json()
                    
                    # Binance returns: [timestamp, open, high, low, close, volume, ...]
                    # Format to match ccxt: [timestamp, open, high, low, close, volume]
                    ohlcv = []
                    for candle in data:
                        ohlcv.append([
                            int(candle[0]),      # timestamp
                            float(candle[1]),    # open
                            float(candle[2]),    # high
                            float(candle[3]),    # low
                            float(candle[4]),    # close
                            float(candle[5])     # volume
                        ])
                    
                    return ohlcv
        except Exception as e:
            raise Exception(f"Failed to fetch OHLCV via HTTP: {str(e)}")
    
    async def _create_market_order_futures_demo(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """
        Create market order using direct HTTP request for Futures Demo mode.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Quantity to trade
            leverage: Leverage multiplier
            
        Returns:
            Order details dictionary
        """
        import aiohttp
        import hmac
        import hashlib
        import time
        from urllib.parse import urlencode
        
        # Convert symbol format
        symbol_clean = symbol.replace('/', '')
        base_url = 'https://demo-fapi.binance.com'
        
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Set leverage (if > 1)
                if leverage > 1:
                    timestamp = int(time.time() * 1000)
                    params = {
                        'symbol': symbol_clean,
                        'leverage': leverage,
                        'timestamp': timestamp
                    }
                    query_string = urlencode(params)
                    signature = hmac.new(
                        self.api_secret.encode('utf-8'),
                        query_string.encode('utf-8'),
                        hashlib.sha256
                    ).hexdigest()
                    
                    headers = {'X-MBX-APIKEY': self.api_key}
                    url = f'{base_url}/fapi/v1/leverage?{query_string}&signature={signature}'
                    
                    async with session.post(url, headers=headers) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            print(f"⚠️  Warning: Failed to set leverage: {resp.status} - {error_text}")
                        else:
                            print(f"✅ Leverage set to {leverage}x for {symbol_clean}")
                
                # Step 2: Place market order
                timestamp = int(time.time() * 1000)
                
                # Round quantity to appropriate precision based on symbol
                # BTC futures: 3 decimal places, most others: varies
                if 'BTC' in symbol_clean:
                    quantity_rounded = round(amount, 3)
                elif 'ETH' in symbol_clean:
                    quantity_rounded = round(amount, 2)
                else:
                    quantity_rounded = round(amount, 8)  # Default high precision
                
                params = {
                    'symbol': symbol_clean,
                    'side': side.upper(),
                    'type': 'MARKET',
                    'quantity': quantity_rounded,
                    'timestamp': timestamp
                }
                query_string = urlencode(params)
                signature = hmac.new(
                    self.api_secret.encode('utf-8'),
                    query_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                headers = {'X-MBX-APIKEY': self.api_key}
                url = f'{base_url}/fapi/v1/order?{query_string}&signature={signature}'
                
                async with session.post(url, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"HTTP {resp.status}: {error_text}")
                    
                    data = await resp.json()
                    
                    return {
                        'order_id': str(data['orderId']),
                        'symbol': symbol,
                        'side': side,
                        'type': 'market',
                        'amount': float(data['origQty']),
                        'price': float(data.get('avgPrice', 0)),
                        'status': data['status'],
                        'filled': float(data.get('executedQty', 0)),
                        'remaining': float(data['origQty']) - float(data.get('executedQty', 0)),
                        'cost': float(data.get('cumQuote', 0)),
                        'fee': {},
                        'timestamp': data['updateTime'],
                        'leverage': leverage
                    }
        except Exception as e:
            raise Exception(f"Failed to create order via HTTP: {str(e)}")
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List]:
        """
        Fetch OHLCV candlestick data.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles
            
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        try:
            # For Futures Demo mode, use direct HTTP request
            if self.testnet and self.demo_mode == 'futures_demo':
                return await self._fetch_ohlcv_futures_demo(symbol, timeframe, limit)
            
            # Use ccxt for other modes
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            raise Exception(f"Failed to fetch OHLCV for {symbol}: {str(e)}")
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """
        Place a market order.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Quantity to trade
            leverage: Leverage multiplier (for futures)
            
        Returns:
            Order details including ID, status, filled price
        """
        try:
            # For Futures Demo mode, use direct HTTP requests
            if self.testnet and self.demo_mode == 'futures_demo':
                return await self._create_market_order_futures_demo(symbol, side, amount, leverage)
            
            # Use ccxt for other modes
            # Set leverage for futures
            if leverage > 1:
                await self.exchange.set_leverage(leverage, symbol)
            
            # Place market order
            order = await self.exchange.create_market_order(symbol, side, amount)
            
            return {
                'order_id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'type': order['type'],
                'amount': order['amount'],
                'price': order.get('average') or order.get('price'),
                'status': order['status'],
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'cost': order.get('cost', 0),
                'fee': order.get('fee', {}),
                'timestamp': order['timestamp'],
                'leverage': leverage
            }
        except Exception as e:
            raise Exception(f"Failed to create market order: {str(e)}")
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """
        Place a limit order.
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            amount: Quantity
            price: Limit price
            leverage: Leverage multiplier
            
        Returns:
            Order details
        """
        try:
            # Set leverage for futures
            if leverage > 1:
                await self.exchange.set_leverage(leverage, symbol)
            
            # Place limit order
            order = await self.exchange.create_limit_order(symbol, side, amount, price)
            
            return {
                'order_id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'type': order['type'],
                'amount': order['amount'],
                'price': order['price'],
                'status': order['status'],
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'cost': order.get('cost', 0),
                'fee': order.get('fee', {}),
                'timestamp': order['timestamp'],
                'leverage': leverage
            }
        except Exception as e:
            raise Exception(f"Failed to create limit order: {str(e)}")
    
    async def fetch_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Fetch current order status.
        
        Args:
            order_id: Order ID
            symbol: Trading pair
            
        Returns:
            Order status details
        """
        try:
            order = await self.exchange.fetch_order(order_id, symbol)
            
            return {
                'order_id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'type': order['type'],
                'status': order['status'],  # 'open', 'closed', 'canceled'
                'price': order['price'],
                'average': order.get('average'),
                'amount': order['amount'],
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'cost': order.get('cost', 0),
                'fee': order.get('fee', {}),
                'timestamp': order['timestamp'],
                'last_update': order.get('lastTradeTimestamp')
            }
        except Exception as e:
            raise Exception(f"Failed to fetch order status: {str(e)}")
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair
            
        Returns:
            Cancellation result
        """
        try:
            result = await self.exchange.cancel_order(order_id, symbol)
            
            return {
                'order_id': result['id'],
                'status': result['status'],
                'symbol': result['symbol'],
                'canceled_at': result.get('timestamp')
            }
        except Exception as e:
            raise Exception(f"Failed to cancel order: {str(e)}")
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all open orders.
        
        Args:
            symbol: Optional trading pair filter. If None, fetches all open orders.
            
        Returns:
            List of open orders
        """
        try:
            if symbol:
                orders = await self.exchange.fetch_open_orders(symbol)
            else:
                # Fetch all open orders (requires warning suppression in options)
                orders = await self.exchange.fetch_open_orders()
            
            # Format orders for consistency
            formatted_orders = []
            for order in orders:
                formatted_orders.append({
                    'order_id': order['id'],
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'type': order['type'],
                    'status': order['status'],
                    'price': order.get('price'),
                    'amount': order['amount'],
                    'filled': order.get('filled', 0),
                    'remaining': order.get('remaining', 0),
                    'cost': order.get('cost', 0),
                    'fee': order.get('fee', {}),
                    'timestamp': order['timestamp']
                })
            
            return formatted_orders
        except Exception as e:
            raise Exception(f"Failed to fetch open orders: {str(e)}")
    
    async def fetch_open_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch all open positions.
        
        Returns:
            List of open positions
        """
        try:
            positions = await self.exchange.fetch_positions()
            
            # Filter to only open positions
            open_positions = []
            for pos in positions:
                if pos['contracts'] and pos['contracts'] > 0:
                    open_positions.append({
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': pos['contracts'],
                        'entry_price': pos['entryPrice'],
                        'mark_price': pos['markPrice'],
                        'unrealized_pnl': pos['unrealizedPnl'],
                        'leverage': pos['leverage'],
                        'liquidation_price': pos.get('liquidationPrice')
                    })
            
            return open_positions
        except Exception as e:
            raise Exception(f"Failed to fetch positions: {str(e)}")
    
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Close an open position with a market order.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Closure order details
        """
        try:
            # Get current position
            positions = await self.exchange.fetch_positions([symbol])
            
            for pos in positions:
                if pos['contracts'] and pos['contracts'] > 0:
                    # Opposite side to close
                    side = 'sell' if pos['side'] == 'long' else 'buy'
                    amount = pos['contracts']
                    
                    # Close with market order
                    return await self.create_market_order(symbol, side, amount)
            
            raise Exception(f"No open position for {symbol}")
        except Exception as e:
            raise Exception(f"Failed to close position: {str(e)}")
    
    def get_trading_fee_rate(self) -> float:
        """
        Get estimated trading fee rate.
        
        Returns:
            Fee rate (e.g., 0.0004 for 0.04%)
        """
        # Binance futures maker/taker fees
        return 0.0004  # 0.04% default
    
    def calculate_total_cost(
        self,
        price: float,
        amount: float,
        leverage: int = 1,
        include_fee: bool = True
    ) -> float:
        """
        Calculate total cost including fees.
        
        Args:
            price: Entry price
            amount: Quantity
            leverage: Leverage multiplier
            include_fee: Whether to include trading fees
            
        Returns:
            Total cost in quote currency
        """
        base_cost = (price * amount) / leverage
        
        if include_fee:
            fee = base_cost * self.get_trading_fee_rate()
            return base_cost + fee
        
        return base_cost
    
    async def validate_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is available on this exchange.
        
        Args:
            symbol: Trading pair to validate (e.g., 'PAXG/USDT')
            
        Returns:
            True if symbol is available, False otherwise
        """
        try:
            markets = await self.exchange.load_markets()
            return symbol in markets
        except Exception as e:
            print(f"⚠️  Symbol validation failed: {e}")
            return False
