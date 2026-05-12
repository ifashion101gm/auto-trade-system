"""
MEXC LIVE exchange implementation.
Uses real API keys and executes actual trades.
Now uses MexcExecutor for proper position-side handling.
Wrapped with ExchangeAdapter for circuit breaker and rate limiting.
"""
import asyncio
from app.exchange.base_exchange import BaseExchange
from app.exchange.mexc_executor import MexcExecutor
from app.exchange.exchange_adapter import ExchangeAdapter
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class MEXCLiveExchange(BaseExchange):
    """
    MEXC LIVE exchange implementation.
    Uses real API keys and executes actual trades.
    Leverages MexcExecutor for proper MEXC-specific order handling.
    Wrapped with ExchangeAdapter for reliability features.
    """
    
    def __init__(self):
        # Create executor and wrap with adapter for circuit breaker + rate limiting
        executor = MexcExecutor(testnet=False)
        self.executor = ExchangeAdapter(executor)
        self._mode = 'LIVE'
        self._connected = False
    
    async def open_position(self, symbol, side, amount, leverage=1, 
                           stop_loss=None, take_profit=None):
        """Execute real market order on MEXC using proper position-side logic."""
        logger.info(f"🔴 LIVE ORDER: {side} {amount} {symbol} @{leverage}x")
        
        # Use executor's position-aware methods
        if side.upper() in ['BUY', 'LONG']:
            order = await self.executor.open_long(
                symbol=symbol,
                amount=amount,
                leverage=leverage
            )
        elif side.upper() in ['SELL', 'SHORT']:
            order = await self.executor.open_short(
                symbol=symbol,
                amount=amount,
                leverage=leverage
            )
        else:
            raise ValueError(f"Invalid side: {side}. Must be BUY/SELL or LONG/SHORT")
        
        return {
            'order_id': order['order_id'],
            'symbol': order['symbol'],
            'side': side.upper(),
            'filled_price': order.get('price') or order.get('average'),
            'filled_amount': order.get('filled', amount),
            'fee': order.get('fee', {}),
            'timestamp': order['timestamp']
        }
    
    async def close_position(self, symbol, trade_id):
        """Close real position on MEXC using reduce-only logic."""
        logger.info(f"🔴 LIVE CLOSE: {symbol} (trade: {trade_id})")
        
        # Get current position to determine side
        positions = await self.executor.get_open_positions()
        mexc_symbol = self.executor._normalize_symbol(symbol)
        
        for pos in positions:
            if pos['symbol'] == mexc_symbol:
                position_side = pos.get('side', '').lower()
                
                # Close based on position side
                if position_side == 'long':
                    result = await self.executor.close_long(
                        symbol=symbol,
                        amount=pos.get('size')
                    )
                elif position_side == 'short':
                    result = await self.executor.close_short(
                        symbol=symbol,
                        amount=pos.get('size')
                    )
                else:
                    raise ValueError(f"Unknown position side: {position_side}")
                
                return {
                    'order_id': result['order_id'],
                    'exit_price': result.get('price') or result.get('average'),
                    'pnl': 0,  # P&L calculated from trade history
                    'timestamp': result['timestamp']
                }
        
        raise ValueError(f"No open position found for {symbol}")
    
    async def get_positions(self):
        """Fetch real open positions from MEXC."""
        return await self.executor.get_open_positions()
    
    async def get_balance(self):
        """Fetch real account balance."""
        return await self.executor.get_balance()
    
    async def get_ticker(self, symbol):
        """Fetch real-time ticker."""
        return await self.executor.get_ticker(symbol)
    
    async def cancel_order(self, order_id, symbol):
        """Cancel real order."""
        return await self.executor.client.cancel_order(order_id, symbol)
    
    @property
    def mode(self):
        return 'LIVE'
    
    # =========================================================================
    # Implement remaining BaseExchange abstract methods
    # =========================================================================
    
    async def fetch_ticker(self, symbol: str):
        """Get real-time ticker data."""
        return await self.executor.get_ticker(symbol)
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100):
        """Fetch OHLCV candlestick data."""
        return await self.executor.client.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    async def fetch_markets(self):
        """Fetch available trading pairs/markets."""
        return await self.executor.client.exchange.load_markets()
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        params=None
    ):
        """Create a market order."""
        if side.upper() in ['BUY', 'LONG']:
            return await self.executor.open_long(symbol=symbol, amount=amount)
        else:
            return await self.executor.open_short(symbol=symbol, amount=amount)
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        params=None
    ):
        """Create a limit order."""
        # Use CCXT directly for limit orders
        normalized_symbol = self.executor._normalize_symbol(symbol)
        order = await self.executor.client.exchange.create_limit_order(
            normalized_symbol, side.lower(), amount, price
        )
        return {
            'order_id': order['id'],
            'symbol': order['symbol'],
            'side': order['side'],
            'price': order['price'],
            'amount': order['amount'],
            'status': order['status'],
            'timestamp': order['timestamp']
        }
    
    async def cancel_order(self, order_id: str, symbol: str):
        """Cancel an open order."""
        return await self.executor.client.cancel_order(order_id, symbol)
    
    async def fetch_order_status(self, order_id: str, symbol: str):
        """Fetch current order status."""
        return await self.executor.client.fetch_order_status(order_id, symbol)
    
    async def fetch_open_orders(self, symbol: str = None):
        """Fetch all open orders, optionally filtered by symbol."""
        return await self.executor.client.fetch_open_orders(symbol)
    
    async def fetch_order_history(
        self,
        symbol: str,
        since: int = None,
        limit: int = None
    ):
        """Fetch historical orders."""
        return await self.executor.client.fetch_order_history(symbol, since, limit)
    
    async def get_positions(self):
        """Get all open positions."""
        return await self.executor.get_open_positions()
    
    async def close_position(self, symbol: str, trade_id: str = None):
        """Close an existing position."""
        positions = await self.executor.get_open_positions()
        mexc_symbol = self.executor._normalize_symbol(symbol)
        
        for pos in positions:
            if pos['symbol'] == mexc_symbol:
                position_side = pos.get('side', '').lower()
                
                if position_side == 'long':
                    result = await self.executor.close_long(
                        symbol=symbol,
                        amount=pos.get('size')
                    )
                elif position_side == 'short':
                    result = await self.executor.close_short(
                        symbol=symbol,
                        amount=pos.get('size')
                    )
                else:
                    raise ValueError(f"Unknown position side: {position_side}")
                
                return {
                    'order_id': result['order_id'],
                    'exit_price': result.get('price') or result.get('average'),
                    'pnl': 0,
                    'timestamp': result['timestamp']
                }
        
        raise ValueError(f"No open position found for {symbol}")
    
    async def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for a specific trading pair."""
        return await self.executor.client.set_leverage(symbol, leverage)
    
    @property
    def has_watch_ohlcv(self) -> bool:
        """Indicates if exchange supports real-time OHLCV streaming."""
        return False  # MEXC doesn't support watch_ohlcv via CCXT
    
    @property
    def has_create_stop_loss_limit(self) -> bool:
        """Indicates if exchange supports stop-loss limit orders."""
        return True  # MEXC supports stop orders
    
    def calculate_fee(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float,
        taker_or_maker: str = 'taker'
    ) -> float:
        """Calculate trading fee for an order."""
        # MEXC futures typical fees: 0.02% maker, 0.06% taker
        fee_rate = 0.0006 if taker_or_maker == 'taker' else 0.0002
        notional_value = amount * price
        return notional_value * fee_rate
    
    async def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is available on this exchange."""
        try:
            markets = await self.fetch_markets()
            normalized_symbol = self.executor._normalize_symbol(symbol)
            return normalized_symbol in markets
        except Exception:
            return False
    
    async def close(self):
        """Close exchange connection gracefully."""
        await self.executor.close()
    
    # =========================================================================
    # Implement new BaseExchange abstract methods
    # =========================================================================
    
    async def connect(self) -> bool:
        """Initialize connection and verify exchange health."""
        try:
            logger.info("🔌 Connecting to MEXC LIVE exchange...")
            
            # Test connectivity with health check
            health = await self.executor.execute_with_retry(
                "health_check",
                self.executor.exchange.health_check
            )
            
            # Verify API credentials by fetching balance
            balance = await self.get_balance()
            
            self._connected = True
            logger.info(f"✅ MEXC LIVE connected successfully (balance: ${balance.get('total_usdt', 0):.2f})")
            return True
            
        except Exception as e:
            logger.error(f"❌ MEXC LIVE connection failed: {e}")
            self._connected = False
            return False
    
    async def sync_state(self) -> dict:
        """Synchronize full exchange state (positions, orders, balance)."""
        try:
            logger.debug("🔄 Syncing MEXC exchange state...")
            
            # Fetch all state components concurrently
            positions_task = self.get_positions()
            balance_task = self.get_balance()
            open_orders_task = self.fetch_open_orders()
            
            positions, balance, open_orders = await asyncio.gather(
                positions_task,
                balance_task,
                open_orders_task,
                return_exceptions=True
            )
            
            # Handle exceptions gracefully
            if isinstance(positions, Exception):
                logger.warning(f"⚠️  Failed to fetch positions: {positions}")
                positions = []
            
            if isinstance(balance, Exception):
                logger.warning(f"⚠️  Failed to fetch balance: {balance}")
                balance = {}
            
            if isinstance(open_orders, Exception):
                logger.warning(f"⚠️  Failed to fetch open orders: {open_orders}")
                open_orders = []
            
            state = {
                'positions': positions,
                'balance': balance,
                'open_orders': open_orders,
                'timestamp': __import__('datetime').datetime.utcnow().isoformat(),
                'exchange': 'MEXC',
                'mode': 'LIVE'
            }
            
            logger.info(f"✅ State synced: {len(positions)} positions, {len(open_orders)} open orders")
            return state
            
        except Exception as e:
            logger.error(f"❌ State sync failed: {e}")
            raise
