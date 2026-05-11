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
        testnet: bool = True
    ):
        """
        Initialize Bybit client.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            testnet: Use testnet (True) or mainnet (False)
        """
        self.api_key = api_key or settings.BYBIT_API_KEY
        self.api_secret = api_secret or settings.BYBIT_API_SECRET
        self.testnet = testnet
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Bybit API credentials not configured")
        
        # Initialize ccxt exchange
        self.exchange = ccxt.bybit({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # Use perpetual swaps
                'test': self.testnet
            }
        })
        
        if self.testnet:
            logger.info("✅ Bybit Client initialized (TESTNET)")
        else:
            logger.warning("⚠️  Bybit Client initialized (MAINNET - LIVE TRADING!)")
    
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
        """
        try:
            # Set leverage
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
