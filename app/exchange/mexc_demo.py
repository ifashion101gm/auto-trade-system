"""
MEXC DEMO/Paper trading exchange.
Simulates trades without real money.
Tracks virtual balance and positions.
Now uses MexcExecutor for consistent position handling.
Wrapped with ExchangeAdapter for circuit breaker and rate limiting.
"""
import asyncio
from app.exchange.base_exchange import BaseExchange
from app.exchange.mexc_executor import MexcExecutor
from app.exchange.exchange_adapter import ExchangeAdapter
from app.config import settings
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class MEXCDemoExchange(BaseExchange):
    """
    MEXC DEMO/Paper trading exchange.
    Simulates trades without real money.
    Tracks virtual balance and positions.
    Can operate in two modes:
    - Testnet mode: Uses real MEXC testnet API via MexcExecutor
    - Local simulation: Virtual trades with realistic fills
    """
    
    def __init__(self, testnet: bool = False):
        # Use testnet credentials if testnet mode is enabled
        self.testnet = testnet
        
        if testnet:
            # For MEXC testnet, use MexcExecutor with testnet flag wrapped in adapter
            executor = MexcExecutor(testnet=True)
            self.executor = ExchangeAdapter(executor)
            self._use_real_api = True
        else:
            # Local paper trading simulation - wrap with adapter for consistency
            self.executor = None
            self._use_real_api = False
        self._mode = 'DEMO'
        self._virtual_balance = 1000.0  # Starting virtual balance (local sim only)
        self._demo_positions = {}  # {order_id: position_data} (local sim only)
        self._connected = False
    async def open_position(self, symbol, side, amount, leverage=1,
                           stop_loss=None, take_profit=None):
        """Execute order - either on testnet API or local simulation."""
        logger.info(f"🟢 DEMO ORDER: {side} {amount} {symbol} @{leverage}x")
        
        if self._use_real_api:
            # Use real testnet API via executor
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
                raise ValueError(f"Invalid side: {side}")
            
            return {
                'order_id': order['order_id'],
                'symbol': order['symbol'],
                'side': side.upper(),
                'filled_price': order.get('price') or order.get('average'),
                'filled_amount': order.get('filled', amount),
                'fee': order.get('fee', {}),
                'timestamp': order['timestamp'],
                'simulated': False
            }
        else:
            # Local simulation with realistic fills
            return await self._simulate_order(symbol, side, amount, leverage, stop_loss, take_profit)
    async def _simulate_order(self, symbol, side, amount, leverage, stop_loss, take_profit):
        """Local simulation with realistic fills (for non-testnet mode)."""
        # Get real market price for realistic simulation
        from app.infra.mexc_client import MEXCClient
        temp_client = MEXCClient(
            api_key=settings.MEXC_PAPER_API_KEY or settings.MEXC_API_KEY,
            api_secret=settings.MEXC_PAPER_API_SECRET or settings.MEXC_API_SECRET,
            market_type='futures'
        )
        
        try:
            ticker = await temp_client.fetch_ticker(symbol)
            entry_price = ticker['last_price']
        finally:
            await temp_client.close()
        
        # Simulate slippage (0.01-0.05%)
        import random
        slippage = entry_price * random.uniform(0.0001, 0.0005)
        if side.upper() in ['BUY', 'LONG']:
            filled_price = entry_price + slippage
        else:
            filled_price = entry_price - slippage
        
        # Calculate fee
        fee_rate = 0.0006  # 0.06% for futures
        fee_cost = (filled_price * amount) * fee_rate
        
        # Create simulated order
        order_id = f"demo_{uuid.uuid4().hex[:12]}"
        
        # Store position
        self._demo_positions[order_id] = {
            'symbol': symbol,
            'side': side.upper(),
            'size': amount,
            'entry_price': filled_price,
            'leverage': leverage,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'opened_at': datetime.utcnow().isoformat()
        }
        
        # Update virtual balance
        margin_required = (filled_price * amount) / leverage
        self._virtual_balance -= fee_cost
        
        return {
            'order_id': order_id,
            'symbol': symbol,
            'side': side.upper(),
            'filled_price': filled_price,
            'filled_amount': amount,
            'fee': {'cost': fee_cost, 'currency': 'USDT'},
            'timestamp': datetime.utcnow().isoformat(),
            'simulated': True
        }
    
    async def close_position(self, symbol, trade_id):
        """Close position - either on testnet API or local simulation."""
        logger.info(f"🟢 DEMO CLOSE: {symbol} (trade: {trade_id})")
        
        if self._use_real_api:
            # Use real testnet API via executor
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
        else:
            # Local simulation
            return await self._simulate_close(symbol, trade_id)
    async def _simulate_close(self, symbol, trade_id):
        """Local simulation of position closure."""
        if trade_id not in self._demo_positions:
            raise ValueError(f"Demo position {trade_id} not found")
        
        position = self._demo_positions[trade_id]
        
        # Get current market price
        from app.infra.mexc_client import MEXCClient
        temp_client = MEXCClient(
            api_key=settings.MEXC_PAPER_API_KEY or settings.MEXC_API_KEY,
            api_secret=settings.MEXC_PAPER_API_SECRET or settings.MEXC_API_SECRET,
            market_type='futures'
        )
        
        try:
            ticker = await temp_client.fetch_ticker(symbol)
            exit_price = ticker['last_price']
        finally:
            await temp_client.close()
        
        # Calculate P&L
        if position['side'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['size']
        else:
            pnl = (position['entry_price'] - exit_price) * position['size']
        
        # Fee for closing
        fee_cost = (exit_price * position['size']) * 0.0006
        
        # Update virtual balance
        self._virtual_balance += pnl - fee_cost
        
        # Remove position
        del self._demo_positions[trade_id]
        
        return {
            'order_id': f"close_{trade_id}",
            'symbol': symbol,
            'exit_price': exit_price,
            'pnl': pnl,
            'fee': fee_cost,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def get_positions(self):
        """Get positions - from testnet API if testnet mode, otherwise simulated."""
        if self._use_real_api:
            # Fetch real positions from MEXC testnet
            return await self.executor.get_open_positions()
        else:
            # Return simulated positions for local simulation
            positions = []
            for order_id, pos in self._demo_positions.items():
                from app.infra.mexc_client import MEXCClient
                temp_client = MEXCClient(
                    api_key=settings.MEXC_PAPER_API_KEY or settings.MEXC_API_KEY,
                    api_secret=settings.MEXC_PAPER_API_SECRET or settings.MEXC_API_SECRET,
                    market_type='futures'
                )
                
                try:
                    ticker = await temp_client.fetch_ticker(pos['symbol'])
                    current_price = ticker['last_price']
                finally:
                    await temp_client.close()
                
                # Calculate unrealized P&L
                if pos['side'] == 'LONG':
                    unrealized_pnl = (current_price - pos['entry_price']) * pos['size']
                else:
                    unrealized_pnl = (pos['entry_price'] - current_price) * pos['size']
                
                positions.append({
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'size': pos['size'],
                    'entry_price': pos['entry_price'],
                    'current_price': current_price,
                    'unrealized_pnl': unrealized_pnl,
                    'leverage': pos['leverage'],
                    'order_id': order_id
                })
            
            return positions
    
    async def get_balance(self):
        """Get balance - from testnet API if testnet mode, otherwise virtual."""
        if self._use_real_api:
            # Fetch real balance from MEXC testnet
            return await self.executor.get_balance()
        else:
            # Return virtual balance for local simulation
            return {
                'total_usdt': self._virtual_balance,
                'free_usdt': self._virtual_balance,
                'used_usdt': 0,
                'balances': {'USDT': self._virtual_balance},
                'virtual': True
            }
    
    async def get_ticker(self, symbol):
        """Get real market ticker (for realistic simulation)."""
        if self._use_real_api:
            return await self.executor.get_ticker(symbol)
        else:
            from app.infra.mexc_client import MEXCClient
            temp_client = MEXCClient(
                api_key=settings.MEXC_PAPER_API_KEY or settings.MEXC_API_KEY,
                api_secret=settings.MEXC_PAPER_API_SECRET or settings.MEXC_API_SECRET,
                market_type='futures'
            )
            try:
                return await temp_client.fetch_ticker(symbol)
            finally:
                await temp_client.close()
    
    async def cancel_order(self, order_id, symbol):
        """Cancel demo order."""
        if self._use_real_api:
            return await self.executor.client.cancel_order(order_id, symbol)
        else:
            if order_id in self._demo_positions:
                del self._demo_positions[order_id]
            return {'order_id': order_id, 'status': 'cancelled'}
    
    @property
    def mode(self):
        return 'DEMO'
    
    # =========================================================================
    # Implement remaining BaseExchange abstract methods
    # =========================================================================
    
    async def fetch_ticker(self, symbol: str):
        """Get real-time ticker data."""
        return await self.get_ticker(symbol)
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100):
        """Fetch OHLCV candlestick data."""
        if self._use_real_api:
            return await self.executor.client.fetch_ohlcv(symbol, timeframe, limit=limit)
        else:
            # Return mock data for local simulation
            return []
    
    async def fetch_markets(self):
        """Fetch available trading pairs/markets."""
        if self._use_real_api:
            return await self.executor.client.exchange.load_markets()
        else:
            return []
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        params=None
    ):
        """Create a market order."""
        return await self.open_position(symbol, side, amount)
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        params=None
    ):
        """Create a limit order - simulate with market order for demo."""
        # For demo purposes, treat limit orders as market orders
        return await self.open_position(symbol, side, amount)
    
    async def cancel_order(self, order_id: str, symbol: str):
        """Cancel an open order."""
        return await super().cancel_order(order_id, symbol)
    
    async def fetch_order_status(self, order_id: str, symbol: str):
        """Fetch current order status."""
        if self._use_real_api:
            return await self.executor.client.fetch_order_status(order_id, symbol)
        else:
            # Return mock status for local simulation
            return {'order_id': order_id, 'status': 'closed'}
    
    async def fetch_open_orders(self, symbol: str = None):
        """Fetch all open orders, optionally filtered by symbol."""
        if self._use_real_api:
            return await self.executor.client.fetch_open_orders(symbol)
        else:
            return list(self._demo_positions.values())
    
    async def fetch_order_history(
        self,
        symbol: str,
        since: int = None,
        limit: int = None
    ):
        """Fetch historical orders."""
        if self._use_real_api:
            return await self.executor.client.fetch_order_history(symbol, since, limit)
        else:
            return []
    
    async def get_positions(self):
        """Get all open positions."""
        if self._use_real_api:
            return await self.executor.get_open_positions()
        else:
            # Return demo positions for local simulation
            return list(self._demo_positions.values())
    
    async def close_position(self, symbol: str, trade_id: str = None):
        """Close an existing position."""
        # Use the existing close_position logic from parent
        positions = await self.get_positions()
        for pos in positions:
            if pos['symbol'] == symbol:
                order_id = pos.get('order_id')
                if order_id:
                    return await self.cancel_order(order_id, symbol)
        return {'status': 'no_position_found'}
    
    async def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for a specific trading pair."""
        if self._use_real_api:
            return await self.executor.client.set_leverage(symbol, leverage)
        else:
            return {'status': 'simulated', 'leverage': leverage}
    
    @property
    def has_watch_ohlcv(self) -> bool:
        """Indicates if exchange supports real-time OHLCV streaming."""
        return False
    
    @property
    def has_create_stop_loss_limit(self) -> bool:
        """Indicates if exchange supports stop-loss limit orders."""
        return True
    
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
        # Demo fees: same as MEXC live
        fee_rate = 0.0006 if taker_or_maker == 'taker' else 0.0002
        notional_value = amount * price
        return notional_value * fee_rate
    
    async def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is available on this exchange."""
        try:
            if self._use_real_api:
                markets = await self.fetch_markets()
                normalized_symbol = self.executor._normalize_symbol(symbol)
                return normalized_symbol in markets
            else:
                return True  # Accept all symbols in local simulation
        except Exception:
            return False
    
    async def close(self):
        """Close exchange connection gracefully."""
        if self._use_real_api and self.executor:
            await self.executor.close()
    
    # =========================================================================
    # Implement new BaseExchange abstract methods
    # =========================================================================
    
    async def connect(self) -> bool:
        """Initialize connection and verify exchange health."""
        try:
            if self._use_real_api:
                logger.info("🔌 Connecting to MEXC DEMO (testnet)...")
                
                # Test connectivity with health check
                health = await self.executor.execute_with_retry(
                    "health_check",
                    self.executor.exchange.health_check
                )
                
                # Verify API credentials by fetching balance
                balance = await self.get_balance()
                
                self._connected = True
                logger.info(f"✅ MEXC DEMO (testnet) connected successfully")
                return True
            else:
                # Local simulation - always "connected"
                self._connected = True
                logger.info("✅ MEXC DEMO (local simulation) ready")
                return True
            
        except Exception as e:
            logger.error(f"❌ MEXC DEMO connection failed: {e}")
            self._connected = False
            return False
    
    async def sync_state(self) -> dict:
        """Synchronize full exchange state (positions, orders, balance)."""
        try:
            logger.debug("🔄 Syncing MEXC DEMO exchange state...")
            
            if self._use_real_api:
                # Fetch all state components concurrently from testnet
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
            else:
                # Local simulation - use virtual state
                positions = list(self._demo_positions.values())
                balance = {'total_usdt': self._virtual_balance, 'free_usdt': self._virtual_balance}
                open_orders = []
            
            state = {
                'positions': positions,
                'balance': balance,
                'open_orders': open_orders,
                'timestamp': datetime.utcnow().isoformat(),
                'exchange': 'MEXC',
                'mode': 'DEMO',
                'testnet': self.testnet
            }
            
            logger.info(f"✅ State synced: {len(positions)} positions, {len(open_orders)} open orders")
            return state
            
        except Exception as e:
            logger.error(f"❌ State sync failed: {e}")
            raise
