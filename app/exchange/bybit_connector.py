"""
Bybit exchange connector implementing unified BaseExchange interface.
Uses CCXT Pro WebSocket streams as primary data source with REST fallback.
Integrates with WebSocketManager for auto-reconnect and reliability.
"""
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.exchange.base_exchange import BaseExchange
from app.infra.bybit_client import BybitClient
from app.infra.websocket_manager import WebSocketManager
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class BybitConnector(BaseExchange):
    """
    Bybit exchange connector with WebSocket-first architecture.
    
    Features:
    - Unified BaseExchange interface implementation
    - CCXT Pro WebSocket streams (positions, orders, ticker, balance)
    - Auto-reconnect with exponential backoff
    - REST API fallback when WebSocket unavailable
    - Demo/Live mode support via environment configuration
    """
    
    def __init__(self, demo_trading: bool = None):
        """
        Initialize Bybit connector.
        
        Args:
            demo_trading: Use demo trading (True), testnet (False), or live trading (False).
                         If None, reads from BYBIT_USE_DEMO_DOMAIN env var.
                         Note: Testnet uses api-testnet.bybit.com, Demo uses api-demo.bybit.com
        """
        # Determine mode
        self.demo_trading = demo_trading if demo_trading is not None else settings.BYBIT_USE_DEMO_DOMAIN
        
        # Select appropriate API credentials
        # For demo_trading=True: Uses BYBIT_DEMO_API_KEY/SECRET with api-demo.bybit.com
        # For demo_trading=False: Uses BYBIT_DEMO_API_KEY/SECRET with api-testnet.bybit.com (testnet)
        # Note: Both demo and testnet use the same credential fields since they're both test environments
        if self.demo_trading:
            api_key = settings.BYBIT_DEMO_API_KEY or settings.BYBIT_API_KEY
            api_secret = settings.BYBIT_DEMO_API_SECRET or settings.BYBIT_API_SECRET
            logger.info(" BybitConnector initialized in DEMO mode (api-demo.bybit.com)")
        else:
            # Testnet mode: Use DEMO API keys with testnet domain
            # This allows users to store testnet keys in the DEMO fields
            api_key = settings.BYBIT_DEMO_API_KEY or settings.BYBIT_API_KEY
            api_secret = settings.BYBIT_DEMO_API_SECRET or settings.BYBIT_API_SECRET
            logger.info("🔧 BybitConnector initialized in TESTNET mode (api-testnet.bybit.com)")
        
        if not api_key or not api_secret:
            raise ValueError("Bybit API credentials not configured")
        
        # Initialize underlying BybitClient
        self.client = BybitClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=not self.demo_trading,  # testnet=True when demo_trading=False
            demo_trading=self.demo_trading
        )
        
        # Initialize WebSocket manager
        self.ws_manager = WebSocketManager(exchange=self.client.exchange)
        
        # Connection state
        self._connected = False
        self._mode = 'DEMO' if self.demo_trading else 'LIVE'
    
    # =========================================================================
    # Connection & State Management Methods
    # =========================================================================
    
    async def connect(self) -> bool:
        """Initialize connection and verify exchange health."""
        try:
            logger.info(f"🔌 Connecting to Bybit {self._mode}...")
            
            # Test connectivity via health check
            if hasattr(self.client.exchange, 'health_check'):
                await self.client.exchange.health_check()
                logger.debug("✅ Health check passed")
            
            # Verify credentials by fetching balance
            balance = await self.fetch_balance()
            logger.debug(f"✅ Balance verified: ${balance.get('total_usdt', 0):.2f}")
            
            # Start WebSocket manager
            await self.ws_manager.start()
            
            # Subscribe to real-time streams
            await self.ws_manager.subscribe_positions(self._on_position_update)
            await self.ws_manager.subscribe_orders(self._on_order_update)
            await self.ws_manager.subscribe_balance(self._on_balance_update)
            
            # Note: Ticker subscription would happen per-symbol when needed
            # Example: await self.ws_manager.subscribe_ticker('BTC/USDT:USDT', self._on_ticker_update)
            
            self._connected = True
            logger.info(f"✅ Bybit {self._mode} connected with WebSocket streams")
            return True
            
        except Exception as e:
            logger.error(f"❌ Bybit connection failed: {e}")
            self._connected = False
            return False
    
    async def sync_state(self) -> Dict[str, Any]:
        """Synchronize full exchange state (positions, orders, balance)."""
        try:
            logger.debug("🔄 Syncing Bybit exchange state...")
            
            # Fetch all state components concurrently
            positions_task = self.fetch_positions()
            balance_task = self.fetch_balance()
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
                'timestamp': datetime.utcnow().isoformat(),
                'exchange': 'BYBIT',
                'mode': self._mode
            }
            
            logger.info(
                f"✅ State synced: {len(positions)} positions, "
                f"{len(open_orders)} open orders"
            )
            return state
            
        except Exception as e:
            logger.error(f"❌ State sync failed: {e}")
            raise
    
    # =========================================================================
    # Market Data Methods
    # =========================================================================
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get real-time ticker data (WebSocket preferred, REST fallback)."""
        if self.ws_manager.is_connected():
            # Return latest cached ticker from WebSocket stream
            cached = self.ws_manager.get_cached_ticker(symbol)
            if cached:
                return cached
        
        # Fallback to REST API
        return await self.client.fetch_ticker(symbol)
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List]:
        """Fetch OHLCV candlestick data (REST only)."""
        return await self.client.fetch_ohlcv(symbol, timeframe, limit)
    
    async def fetch_markets(self) -> List[Dict[str, Any]]:
        """Fetch available trading pairs/markets."""
        return await self.client.exchange.load_markets()
    
    # =========================================================================
    # Account & Balance Methods
    # =========================================================================
    
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance (WebSocket preferred, REST fallback)."""
        if self.ws_manager.is_connected():
            cached = self.ws_manager.get_cached_balance()
            if cached:
                return cached
        
        # Fallback to REST API
        return await self.client.fetch_balance()
    
    # Alias for consistency with BaseExchange naming
    async def fetch_balance(self) -> Dict[str, Any]:
        """Alias for get_balance()."""
        return await self.get_balance()
    
    # =========================================================================
    # Order Management Methods
    # =========================================================================
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a market order via REST API."""
        return await self.client.create_market_order(symbol, side, amount)
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a limit order via REST API."""
        return await self.client.create_limit_order(symbol, side, amount, price)
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an open order."""
        return await self.client.cancel_order(order_id, symbol)
    
    async def fetch_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Fetch current order status."""
        return await self.client.fetch_order_status(order_id, symbol)
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all open orders (WebSocket preferred, REST fallback)."""
        if self.ws_manager.is_connected():
            cached = self.ws_manager.get_cached_open_orders(symbol)
            if cached:
                return cached
        
        # Fallback to REST API
        return await self.client.fetch_open_orders(symbol)
    
    async def fetch_order_history(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch historical orders."""
        return await self.client.fetch_order_history(symbol, since, limit)
    
    # =========================================================================
    # Position Management Methods
    # =========================================================================
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions (WebSocket preferred, REST fallback)."""
        if self.ws_manager.is_connected():
            cached = self.ws_manager.get_cached_positions()
            if cached:
                return cached
        
        # Fallback to REST API
        return await self.client.fetch_open_positions()
    
    # Alias for consistency with BaseExchange naming
    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """Alias for get_positions()."""
        return await self.get_positions()
    
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close an existing position via market order."""
        return await self.client.close_position(symbol)
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a specific trading pair."""
        return await self.client.set_leverage(symbol, leverage)
    
    # =========================================================================
    # Feature Flags (CCXT Pattern)
    # =========================================================================
    
    @property
    def has_watch_ohlcv(self) -> bool:
        """Bybit supports watch_ohlcv via CCXT Pro."""
        return True
    
    @property
    def has_create_stop_loss_limit(self) -> bool:
        """Bybit supports stop-loss limit orders."""
        return True
    
    @property
    def mode(self) -> str:
        """Return exchange mode: 'LIVE' or 'DEMO'."""
        return self._mode
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
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
        # Bybit perpetual swap fees: 0.06% taker, 0.02% maker
        fee_rate = 0.0006 if taker_or_maker == 'taker' else 0.0002
        notional_value = amount * price
        return notional_value * fee_rate
    
    async def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is available on this exchange."""
        try:
            markets = await self.fetch_markets()
            return symbol in markets
        except Exception:
            return False
    
    async def close(self):
        """Close exchange connection gracefully."""
        await self.ws_manager.stop()
        await self.client.close()
        self._connected = False
        logger.info(f"🛑 Bybit {self._mode} disconnected")
    
    # =========================================================================
    # WebSocket Event Handlers
    # =========================================================================
    
    async def _on_position_update(self, positions: List[Dict]):
        """Handle real-time position updates from WebSocket."""
        logger.debug(f"📊 Position update: {len(positions)} positions")
        # Positions are automatically cached by WebSocketManager
        # Additional processing can be added here (e.g., emit events)
    
    async def _on_order_update(self, order: Dict):
        """Handle real-time order updates from WebSocket."""
        order_id = order.get('order_id', 'unknown')
        status = order.get('status', 'unknown')
        logger.info(f"📝 Order update: {order_id} status={status}")
        # Orders are automatically cached by WebSocketManager
        # Additional processing can be added here (e.g., emit events)
    
    async def _on_balance_update(self, balance: Dict):
        """Handle real-time balance updates from WebSocket."""
        logger.debug(f"💰 Balance update received")
        # Balance is automatically cached by WebSocketManager
        # Additional processing can be added here (e.g., emit events)
    
    async def _on_ticker_update(self, ticker: Dict):
        """Handle real-time ticker updates from WebSocket."""
        symbol = ticker.get('symbol', 'unknown')
        price = ticker.get('last_price', 0)
        logger.debug(f"📈 Ticker update: {symbol} price={price}")
        # Tickers are automatically cached by WebSocketManager
        # Additional processing can be added here (e.g., emit events)
