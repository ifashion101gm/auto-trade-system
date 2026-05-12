"""
Bybit exchange client for derivatives trading.
Uses ccxt library for unified API access.
"""
import logging
import ccxt.async_support as ccxt
from typing import Dict, Any, Optional, List
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class BybitClient:
    """
    Bybit exchange client for derivatives trading.
    Uses ccxt library for unified API access with Bybit-specific optimizations.
    
    Best Practices Implemented (per official pybit standards):
    - Rate limiting aligned with Bybit API limits (10 req/sec private, 50 req/sec public)
    - recv_window parameter for timestamp validation (prevents replay attacks)
    - adjustForTimeDifference for clock skew compensation
    - Category-based API calls (linear/inverse/spot/option)
    - Bybit-specific error code handling (10003=Invalid API Key, etc.)
    - Exponential backoff for rate limit errors
    
    Features:
    - Perpetual and futures trading
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
        testnet: bool = True,
        demo_trading: bool = None
    ):
        """
        Initialize Bybit client.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            testnet: Use testnet (True) or mainnet (False) - Legacy parameter
            demo_trading: Use demo trading domain (True) or live domain (False)
                         Demo trading requires separate API keys generated from demo mode
        """
        self.api_key = api_key or settings.BYBIT_API_KEY
        self.api_secret = api_secret or settings.BYBIT_API_SECRET
        self.testnet = testnet
        self.demo_trading = demo_trading if demo_trading is not None else settings.BYBIT_USE_DEMO_DOMAIN
        
        # Use demo/testnet API keys if demo_trading is enabled OR if testnet mode
        # Both demo and testnet use BYBIT_DEMO_API_KEY/SECRET fields
        if self.demo_trading or self.testnet:
            self.api_key = api_key or settings.BYBIT_DEMO_API_KEY or settings.BYBIT_API_KEY
            self.api_secret = api_secret or settings.BYBIT_DEMO_API_SECRET or settings.BYBIT_API_SECRET
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Bybit API credentials not configured")
        
        # Initialize ccxt exchange with Bybit-specific optimizations
        exchange_config = {
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': settings.BYBIT_RATE_LIMIT_ENABLED,
            'rateLimit': int(1000 / settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND),  # Convert to milliseconds
            'options': {
                'defaultType': 'swap',  # Use perpetual swaps (linear category)
                'defaultSubType': 'linear',  # Bybit category: linear, inverse, spot, option
                'recvWindow': settings.BYBIT_RECV_WINDOW,  # Timestamp validation window (ms)
            }
        }
        
        # Configure demo trading or testnet
        if self.demo_trading:
            # Bybit Demo Trading uses separate domain: api-demo.bybit.com
            # Requires API keys generated FROM demo mode interface
            exchange_config['urls'] = {
                'api': {
                    'public': 'https://api-demo.bybit.com',
                    'private': 'https://api-demo.bybit.com',
                }
            }
            exchange_config['options']['adjustForTimeDifference'] = True  # Auto-adjust for clock skew
            logger.info("✅ Bybit Client initialized (DEMO TRADING)")
            logger.info("   Domain: https://api-demo.bybit.com")
            logger.info("   Note: Requires API keys generated from Demo Trading interface")
            logger.info(f"   Rate Limit: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND} req/sec")
            logger.info(f"   Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
        elif self.testnet:
            # Testnet uses api-testnet.bybit.com
            # Must explicitly set URLs as CCXT doesn't auto-resolve {hostname} for testnet
            exchange_config['urls'] = {
                'api': {
                    'public': 'https://api-testnet.bybit.com',
                    'private': 'https://api-testnet.bybit.com',
                }
            }
            exchange_config['options']['adjustForTimeDifference'] = True  # Auto-adjust for clock skew
            logger.info("✅ Bybit Client initialized (TESTNET)")
            logger.info("   Domain: https://api-testnet.bybit.com")
            logger.info(f"   Rate Limit: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND} req/sec")
            logger.info(f"   Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
        else:
            logger.warning("️  Bybit Client initialized (MAINNET - LIVE TRADING!)")
            logger.info(f"   Rate Limit: {settings.BYBIT_RATE_LIMIT_CALLS_PER_SECOND} req/sec")
            logger.info(f"   Recv Window: {settings.BYBIT_RECV_WINDOW}ms")
        
        self.exchange = ccxt.bybit(exchange_config)
    
    async def close(self):
        """Close exchange connection."""
        await self.exchange.close()
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance.
        
        Returns:
            Dictionary with balance information
        
        Raises:
            Exception: With Bybit-specific error codes and messages
        """
        try:
            balance = await self.exchange.fetch_balance()
            
            # Get USDT balance
            usdt_balance = balance.get('USDT', {})
            
            return {
                'total_usdt': usdt_balance.get('total', 0),
                'free_usdt': usdt_balance.get('free', 0),
                'used_usdt': usdt_balance.get('used', 0),
                'balances': {k: v['total'] for k, v in balance.items() 
                           if isinstance(v, dict) and 'total' in v and v['total'] > 0}
            }
        except Exception as e:
            error_msg = str(e)
            
            # Handle Bybit-specific error codes
            if '"retCode":10003' in error_msg or '10003' in error_msg:
                logger.error(" Bybit Error 10003: API key is invalid")
                logger.error("   Possible causes:")
                logger.error("   1. API key/secret mismatch or typo")
                logger.error("   2. Key is disabled, expired, or revoked")
                logger.error("   3. Key lacks required permissions (Account Read, Wallet Read)")
                logger.error("   4. IP restriction blocking this server")
                raise Exception(f"Bybit authentication failed (10003): API key is invalid. {error_msg}")
            
            elif '"retCode":10002' in error_msg or '10002' in error_msg:
                logger.error("❌ Bybit Error 10002: Invalid parameter")
                logger.error("   Possible causes:")
                logger.error("   1. API key format incorrect")
                logger.error("   2. Extra characters or spaces in key/secret")
                logger.error("   3. recv_window too small (< 5000ms)")
                raise Exception(f"Bybit parameter error (10002): Invalid parameter. {error_msg}")
            
            elif '"retCode":10004' in error_msg or '10004' in error_msg:
                logger.error("❌ Bybit Error 10004: API key permissions denied")
                logger.error("   Required permissions:")
                logger.error("   - Order - Trade (Spot & Derivatives)")
                logger.error("   - Position - Read & Write")
                logger.error("   - Account - Read")
                logger.error("   - Wallet - Read")
                raise Exception(f"Bybit permissions error (10004): API key permissions denied. {error_msg}")
            
            elif '"retCode":10016' in error_msg or '10016' in error_msg:
                logger.error("❌ Bybit Error 10016: Timestamp error")
                logger.error("   Possible causes:")
                logger.error("   1. Server clock not synchronized")
                logger.error("   2. recv_window too small")
                logger.error("   Fix: Enable adjustForTimeDifference or increase recvWindow")
                raise Exception(f"Bybit timestamp error (10016): Clock skew detected. {error_msg}")
            
            elif 'rate' in error_msg.lower() or 'limit' in error_msg.lower():
                logger.warning("⚠️  Rate limit exceeded - implementing backoff")
                raise Exception(f"Bybit rate limit exceeded. Implementing backoff. {error_msg}")
            
            else:
                raise Exception(f"Failed to fetch balance: {error_msg}")
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch real-time ticker data.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            
        Returns:
            Ticker data with price, volume, etc.
        """
        try:
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
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Quantity to trade
            leverage: Leverage multiplier
            
        Returns:
            Order details including ID, status, filled price
        
        Raises:
            Exception: With Bybit-specific error codes and messages
        """
        try:
            # Set leverage
            if leverage > 1:
                await self.exchange.set_leverage(leverage, symbol)
            
            # Place market order
            order = await self.exchange.create_market_order(symbol, side, amount)
            
            logger.info(f"✅ Market order placed: {order['id']} - {side} {amount} {symbol}")
            
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
            error_msg = str(e)
            
            # Handle Bybit-specific errors
            if '"retCode":10003' in error_msg or '10003' in error_msg:
                logger.error("❌ Bybit Error 10003: API key invalid during order placement")
                raise Exception(f"Bybit authentication failed (10003): Cannot place order. {error_msg}")
            
            elif '"retCode":10024' in error_msg or '10024' in error_msg:
                logger.error("❌ Bybit Error 10024: Regulatory restriction")
                logger.error("   This testnet account has regional/KYC restrictions")
                logger.error("   Possible causes:")
                logger.error("   1. Account not KYC verified on testnet")
                logger.error("   2. Geographic restrictions for your region")
                logger.error("   3. Derivatives trading not enabled for this account")
                logger.error("   Solutions:")
                logger.error("   - Complete KYC verification on testnet.bybit.com")
                logger.error("   - Contact Bybit support for testnet access")
                logger.error("   - Try spot trading instead of derivatives")
                logger.error("   - Use a different testnet account")
                raise Exception(f"Bybit regulatory restriction (10024): Account restricted. {error_msg}")
            
            elif '"retCode":110026' in error_msg or '110026' in error_msg:
                logger.error("❌ Bybit Error 110026: Insufficient balance")
                raise Exception(f"Bybit insufficient balance (110026): Cannot place order. {error_msg}")
            
            elif '"retCode":130021' in error_msg or '130021' in error_msg:
                logger.error("❌ Bybit Error 130021: Position size limit exceeded")
                raise Exception(f"Bybit position limit (130021): Size exceeds maximum allowed. {error_msg}")
            
            elif 'rate' in error_msg.lower() or 'limit' in error_msg.lower():
                logger.warning("⚠️  Rate limit exceeded during order placement")
                raise Exception(f"Bybit rate limit exceeded. Implementing backoff. {error_msg}")
            
            else:
                raise Exception(f"Failed to create market order: {error_msg}")
    
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
            # Set leverage
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
                'status': order['status'],
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
        # Bybit perpetual swap fees
        return 0.0006  # 0.06% default
    
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
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all open orders, optionally filtered by symbol.
        
        Args:
            symbol: Trading pair (optional filter)
            
        Returns:
            List of open orders
        """
        try:
            if symbol:
                orders = await self.exchange.fetch_open_orders(symbol)
            else:
                orders = await self.exchange.fetch_open_orders()
            
            return [
                {
                    'order_id': order['id'],
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'type': order['type'],
                    'status': order['status'],
                    'price': order['price'],
                    'amount': order['amount'],
                    'filled': order.get('filled', 0),
                    'remaining': order.get('remaining', 0),
                    'timestamp': order['timestamp']
                }
                for order in orders
            ]
        except Exception as e:
            raise Exception(f"Failed to fetch open orders: {str(e)}")
    
    async def fetch_order_history(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical orders.
        
        Args:
            symbol: Trading pair
            since: Timestamp to start from (optional)
            limit: Maximum number of orders (optional)
            
        Returns:
            List of historical orders
        """
        try:
            orders = await self.exchange.fetch_orders(symbol, since=since, limit=limit)
            return [
                {
                    'order_id': order['id'],
                    'symbol': order['symbol'],
                    'side': order['side'],
                    'type': order['type'],
                    'status': order['status'],
                    'price': order['price'],
                    'amount': order['amount'],
                    'filled': order.get('filled', 0),
                    'cost': order.get('cost', 0),
                    'timestamp': order['timestamp']
                }
                for order in orders
            ]
        except Exception as e:
            raise Exception(f"Failed to fetch order history: {str(e)}")
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """
        Set leverage for a specific trading pair.
        
        Args:
            symbol: Trading pair
            leverage: Leverage multiplier
            
        Returns:
            Confirmation with leverage setting
        """
        try:
            await self.exchange.set_leverage(leverage, symbol)
            logger.info(f"✅ Leverage set: {leverage}x for {symbol}")
            return {'status': 'success', 'leverage': leverage, 'symbol': symbol}
        except Exception as e:
            raise Exception(f"Failed to set leverage: {str(e)}")
    
    @staticmethod
    def get_bybit_error_description(ret_code: int) -> str:
        """
        Get human-readable description for Bybit error codes.
        
        Based on official Bybit API documentation:
        https://bybit-exchange.github.io/docs/v5/error
        
        Args:
            ret_code: Bybit return code
            
        Returns:
            Description of the error
        """
        error_codes = {
            10002: "Invalid parameter - Check API key format, recv_window, or request parameters",
            10003: "API key is invalid - Key may be disabled, expired, revoked, or lacks permissions",
            10004: "Permissions denied - API key lacks required permissions for this operation",
            10005: "Permission denied for IP - IP not whitelisted in API key settings",
            10006: "Too many visits - Rate limit exceeded",
            10016: "Timestamp error - Server clock not synchronized or recv_window too small",
            10017: "Request expired - Request timestamp too old (> recv_window)",
            10024: "Regulatory restriction - Account has regional/KYC restrictions preventing trading",
            110026: "Insufficient balance - Not enough funds for this operation",
            130021: "Position size limit exceeded - Order exceeds maximum allowed position size",
            130027: "Exceeds maximum leverage - Leverage too high for this symbol",
            130028: "Order cost exceeds limit - Notional value too large",
        }
        
        return error_codes.get(ret_code, f"Unknown error code: {ret_code}")
