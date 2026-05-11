"""
MEXC exchange client for spot and futures trading.
Uses ccxt library for unified API access.
"""
import logging
import ccxt.async_support as ccxt
from typing import Dict, Any, Optional, List
import hashlib
import hmac
import time
import aiohttp
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class MEXCClient:
    """
    MEXC exchange client supporting both spot and futures markets.
    
    Features:
    - Spot and futures trading
    - Real order placement (market/limit orders)
    - Order status tracking
    - Position management (futures)
    - Market data fetching
    - Fee calculation
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        market_type: str = "futures",
        testnet: bool = False
    ):
        """
        Initialize MEXC client.
        
        Args:
            api_key: MEXC API key
            api_secret: MEXC API secret
            market_type: 'spot' or 'futures'
            testnet: Use testnet endpoints (default: False)
        """
        import ccxt.async_support as ccxt
        
        self.api_key = api_key or settings.MEXC_API_KEY
        self.api_secret = api_secret or settings.MEXC_API_SECRET
        self.market_type = market_type or settings.MEXC_DEFAULT_MARKET_TYPE
        self.testnet = testnet
        
        if not self.api_key or not self.api_secret:
            raise ValueError("MEXC API credentials not configured")
        
        # Initialize ccxt exchange
        # MEXC uses 'swap' for perpetual futures, 'spot' for spot markets
        exchange_config = {
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap' if self.market_type == 'futures' else 'spot'
            }
        }
        
        # Use testnet endpoints if enabled
        if self.testnet:
            exchange_config['urls'] = {
                'api': {
                    'public': 'https://contract.testnet.mexc.com/api/v1/public',
                    'private': 'https://contract.testnet.mexc.com/api/v1/private',
                }
            }
            logger.info("🧪 MEXC Testnet mode enabled")
        
        self.exchange = ccxt.mexc(exchange_config)
        
        mode = "TESTNET" if self.testnet else "LIVE"
        logger.info(f"✅ MEXC Client initialized ({self.market_type.upper()} - {mode})")
    
    async def close(self):
        """Close exchange connection."""
        await self.exchange.close()
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance using MEXC Futures API v1.
        
        Returns:
            Dictionary with balance information
        """
        try:
            # Try ccxt first
            try:
                balance = await self.exchange.fetch_balance()
                usdt_balance = balance.get('USDT', {})
                
                return {
                    'total_usdt': usdt_balance.get('total', 0),
                    'free_usdt': usdt_balance.get('free', 0),
                    'used_usdt': usdt_balance.get('used', 0),
                    'balances': {k: v['total'] for k, v in balance.items() 
                               if isinstance(v, dict) and 'total' in v and v['total'] > 0}
                }
            except Exception:
                # Fallback to direct MEXC API v1
                return await self._fetch_balance_direct()
        except Exception as e:
            raise Exception(f"Failed to fetch balance: {str(e)}")
    
    async def _fetch_balance_direct(self) -> Dict[str, Any]:
        """Fetch balance directly from MEXC Futures API v1
        
        According to official MEXC API documentation:
        - POST requests: signature = HMAC_SHA256(secret, accessKey + timestamp + JSON_body)
        - Signature goes in header, NOT in request body
        - Headers: ApiKey, Request-Time, Signature, Content-Type: application/json
        """
        import json
        
        timestamp = str(int(time.time() * 1000))
        
        # Build request body WITHOUT signature (signature goes in header)
        body_dict = {
            'api_key': self.api_key,
            'req_time': timestamp
        }
        
        # Create JSON string for signing (sorted keys for consistency)
        json_body_for_sign = json.dumps(body_dict, sort_keys=True, separators=(',', ':'))
        
        # Signature: HMAC_SHA256(secret, accessKey + timestamp + jsonBody)
        signature_string = f"{self.api_key}{timestamp}{json_body_for_sign}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Headers according to official docs
        headers = {
            'ApiKey': self.api_key,
            'Request-Time': timestamp,
            'Signature': signature,
            'Content-Type': 'application/json'
        }
        
        # Determine API base URL
        base_url = 'https://contract.testnet.mexc.com' if self.testnet else 'https://contract.mexc.com'
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{base_url}/api/v1/private/account/assets',
                headers=headers,
                json=body_dict,  # Send body without 'sign' field
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                
                if data.get('success') and data.get('data'):
                    account_data = data['data']
                    return {
                        'total_usdt': float(account_data.get('walletBalance', 0)),
                        'free_usdt': float(account_data.get('availableBalance', 0)),
                        'used_usdt': float(account_data.get('walletBalance', 0)) - float(account_data.get('availableBalance', 0)),
                        'balances': {'USDT': float(account_data.get('walletBalance', 0))}
                    }
                else:
                    raise Exception(f"MEXC API error: {data.get('message', 'Unknown error')}")
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time ticker data.
        
        Args:
            symbol: Trading pair (e.g., 'XAUT_USDT' or 'XAUT/USDT:USDT')
            
        Returns:
            Ticker data with price, volume, etc.
        """
        try:
            # Normalize symbol format for MEXC futures
            normalized_symbol = self._normalize_symbol(symbol)
            
            ticker = await self.exchange.fetch_ticker(normalized_symbol)
            return {
                'symbol': normalized_symbol,
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
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format for MEXC with CCXT.
        
        CCXT expects standard slash format for MEXC futures:
        - 'BTC/USDT:USDT' for standard futures
        - 'GOLD(XAUT)/USDT' for gold futures (no settlement suffix)
        
        Args:
            symbol: Input symbol (e.g., 'XAUT_USDT', 'XAUT/USDT', 'GOLD(XAUT)/USDT')
            
        Returns:
            Normalized symbol in CCXT-compatible format
        """
        # Convert underscore format to slash format for CCXT
        if '_' in symbol and '/' not in symbol:
            # Only convert if there's no slash already
            parts = symbol.split('_')
            if len(parts) == 2:
                symbol = f"{parts[0]}/{parts[1]}"
        
        # For CCXT, most futures use BASE/QUOTE:SETTLEMENT format
        # But GOLD futures are special: GOLD(XAUT)/USDT (no :USDT suffix)
        # Check if this is a GOLD symbol
        if symbol.upper().startswith('GOLD('):
            # GOLD futures don't need :USDT suffix
            # Ensure format is GOLD(XAUT)/USDT
            if ':' in symbol:
                symbol = symbol.split(':')[0]  # Remove any :USDT suffix
            return symbol
        
        # For non-GOLD futures, add :USDT suffix if missing
        if self.market_type == 'futures':
            if '/' in symbol and ':' not in symbol:
                # Add settlement currency for standard futures
                base_quote = symbol.split('/')
                if len(base_quote) == 2:
                    quote = base_quote[1]
                    symbol = f"{base_quote[0]}/{quote}:{quote}"
        
        return symbol
    
    def _sign_mexc_request(
        self,
        api_key: str,
        api_secret: str,
        timestamp: str,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Sign MEXC API request using HMAC SHA256 according to official documentation.
        
        Signature formula: HMAC_SHA256(secret, accessKey + timestamp + paramString)
        
        For POST requests:
        - paramString = JSON string of request body (sorted keys)
        
        For GET/DELETE requests:
        - paramString = URL-encoded query parameters (dictionary order, & separated)
        
        Args:
            api_key: MEXC API key
            api_secret: MEXC API secret
            timestamp: Request timestamp in milliseconds (string)
            params: Request parameters (optional, None for no params)
            
        Returns:
            HMAC SHA256 signature (hex string, NOT base64 encoded)
            
        Example:
            >>> timestamp = str(int(time.time() * 1000))
            >>> params = {'api_key': 'YOUR_KEY', 'req_time': timestamp}
            >>> signature = client._sign_mexc_request(api_key, api_secret, timestamp, params)
        """
        import json
        
        # Build parameter string based on request type
        if params is None or len(params) == 0:
            param_string = ""
        else:
            # For POST: JSON string with sorted keys
            # For GET: would use URL encoding (not implemented here as we use CCXT)
            param_string = json.dumps(params, sort_keys=True, separators=(',', ':'))
        
        # Signature string: accessKey + timestamp + paramString
        signature_string = f"{api_key}{timestamp}{param_string}"
        
        # Generate HMAC SHA256 signature
        signature = hmac.new(
            api_secret.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
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
            symbol: Trading pair (e.g., 'XAUT_USDT' or 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Quantity to trade
            leverage: Leverage multiplier (for futures)
            
        Returns:
            Order details including ID, status, filled price
        """
        try:
            # Normalize symbol format
            normalized_symbol = self._normalize_symbol(symbol)
            
            # Set leverage for futures
            if self.market_type == 'futures' and leverage > 1:
                await self.exchange.set_leverage(leverage, normalized_symbol)
            
            # Place market order
            order = await self.exchange.create_market_order(normalized_symbol, side, amount)
            
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
            symbol: Trading pair (e.g., 'XAUT_USDT' or 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Quantity
            price: Limit price
            leverage: Leverage multiplier
            
        Returns:
            Order details
        """
        try:
            # Normalize symbol format
            normalized_symbol = self._normalize_symbol(symbol)
            
            # Set leverage for futures
            if self.market_type == 'futures' and leverage > 1:
                await self.exchange.set_leverage(leverage, normalized_symbol)
            
            # Place limit order
            order = await self.exchange.create_limit_order(normalized_symbol, side, amount, price)
            
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
            normalized_symbol = self._normalize_symbol(symbol)
            order = await self.exchange.fetch_order(order_id, normalized_symbol)
            
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
            normalized_symbol = self._normalize_symbol(symbol)
            result = await self.exchange.cancel_order(order_id, normalized_symbol)
            
            return {
                'order_id': result['id'],
                'status': result['status'],
                'symbol': result['symbol'],
                'canceled_at': result.get('timestamp')
            }
        except Exception as e:
            raise Exception(f"Failed to cancel order: {str(e)}")
    
    async def fetch_open_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch all open positions (futures only).
        
        Returns:
            List of open positions
        """
        if self.market_type != 'futures':
            return []
        
        try:
            positions = await self.exchange.fetch_positions()
            
            # Filter to only open positions
            open_positions = []
            for pos in positions:
                if pos.get('contracts') and pos['contracts'] > 0:
                    open_positions.append({
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': pos['contracts'],
                        'entry_price': pos.get('entryPrice'),
                        'mark_price': pos.get('markPrice'),
                        'unrealized_pnl': pos.get('unrealizedPnl'),
                        'leverage': pos.get('leverage'),
                        'liquidation_price': pos.get('liquidationPrice')
                    })
            
            return open_positions
        except Exception as e:
            raise Exception(f"Failed to fetch positions: {str(e)}")
    
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """
        Close an open position with a market order (futures only).
        
        Args:
            symbol: Trading pair
            
        Returns:
            Closure order details
        """
        if self.market_type != 'futures':
            raise Exception("Position closing only available for futures")
        
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            # Get current position
            positions = await self.exchange.fetch_positions([normalized_symbol])
            
            for pos in positions:
                if pos.get('contracts') and pos['contracts'] > 0:
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
            Fee rate (e.g., 0.0006 for 0.06%)
        """
        # MEXC fees vary by VIP level, using standard rate
        if self.market_type == 'futures':
            return 0.0006  # 0.06% for futures
        else:
            return 0.002  # 0.2% for spot
    
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
            symbol: Trading pair to validate (e.g., 'XAUT/USDT')
            
        Returns:
            True if symbol is available, False otherwise
        """
        try:
            markets = await self.exchange.load_markets()
            return symbol in markets
        except Exception as e:
            logger.warning(f"⚠️  Symbol validation failed: {e}")
            return False
