"""
Unified Exchange Manager supporting multiple exchanges (Binance, MEXC, Bybit).
Provides consistent interface for order execution across different platforms.
Controls testnet vs live trading via configuration flags.
"""
import logging
from typing import Dict, Any, Optional, List
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class UnifiedExchangeManager:
    """
    Manages multiple exchange connections with unified API.
    
    Features:
    - Supports Binance, MEXC, and Bybit
    - Testnet/live mode switching via config
    - Automatic exchange selection based on ACTIVE_EXCHANGE
    - Consistent order placement and tracking interface
    """
    
    def __init__(self, exchange_name: Optional[str] = None, use_testnet: Optional[bool] = None):
        """
        Initialize exchange manager.
        
        Args:
            exchange_name: Exchange to use ('binance', 'mexc', 'bybit'). Defaults to ACTIVE_EXCHANGE.
            use_testnet: Use testnet mode. Defaults to BINANCE_TESTNET setting.
        """
        self.exchange_name = exchange_name or settings.ACTIVE_EXCHANGE
        self.use_testnet = use_testnet if use_testnet is not None else settings.BINANCE_TESTNET
        
        # Initialize appropriate exchange client
        self.client = self._create_client()
        logger.info(f"✅ Exchange Manager initialized: {self.exchange_name.upper()} ({'TESTNET' if self.use_testnet else 'LIVE'})")
    
    def _create_client(self):
        """Create appropriate exchange client based on configuration."""
        if self.exchange_name.lower() == 'binance':
            return self._create_binance_client()
        elif self.exchange_name.lower() == 'mexc':
            return self._create_mexc_client()
        elif self.exchange_name.lower() == 'bybit':
            return self._create_bybit_client()
        else:
            raise ValueError(f"Unsupported exchange: {self.exchange_name}. Supported: binance, mexc, bybit")
    
    def _create_binance_client(self):
        """Create Binance client with appropriate credentials."""
        from app.infra.binance_client import BinanceClient
        
        # Use paper trading keys if in testnet mode
        if self.use_testnet:
            api_key = settings.BINANCE_PAPER_API_KEY or settings.BINANCE_API_KEY
            api_secret = settings.BINANCE_PAPER_API_SECRET or settings.BINANCE_API_SECRET
        else:
            api_key = settings.BINANCE_API_KEY
            api_secret = settings.BINANCE_API_SECRET
        
        return BinanceClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=self.use_testnet
        )
    
    def _create_mexc_client(self):
        """Create MEXC client with appropriate credentials."""
        from app.infra.mexc_client import MEXCClient
        
        # Use paper trading keys if in testnet mode
        if self.use_testnet:
            api_key = settings.MEXC_PAPER_API_KEY or settings.MEXC_API_KEY
            api_secret = settings.MEXC_PAPER_API_SECRET or settings.MEXC_API_SECRET
        else:
            api_key = settings.MEXC_API_KEY
            api_secret = settings.MEXC_API_SECRET
        
        market_type = settings.MEXC_DEFAULT_MARKET_TYPE
        
        return MEXCClient(
            api_key=api_key,
            api_secret=api_secret,
            market_type=market_type
        )
    
    def _create_bybit_client(self):
        """Create Bybit client."""
        from app.infra.bybit_client import BybitClient
        
        # Use demo keys when BYBIT_USE_DEMO_DOMAIN is true
        if settings.BYBIT_USE_DEMO_DOMAIN:
            api_key = settings.BYBIT_DEMO_API_KEY or settings.BYBIT_API_KEY
            api_secret = settings.BYBIT_DEMO_API_SECRET or settings.BYBIT_API_SECRET
            demo_trading = True
            logger.info("✅ Using Bybit DEMO trading keys (api-demo.bybit.com)")
        else:
            api_key = settings.BYBIT_API_KEY
            api_secret = settings.BYBIT_API_SECRET
            demo_trading = False
            logger.info("✅ Using Bybit LIVE trading keys (api.bybit.com)")
        
        return BybitClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=self.use_testnet,
            demo_trading=demo_trading
        )
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """Fetch account balance."""
        return await self.client.fetch_balance()
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch real-time ticker data."""
        return await self.client.fetch_ticker(symbol)
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List]:
        """Fetch OHLCV candlestick data."""
        return await self.client.fetch_ohlcv(symbol, timeframe, limit)
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """Place a market order."""
        return await self.client.create_market_order(symbol, side, amount, leverage)
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        leverage: int = 1
    ) -> Dict[str, Any]:
        """Place a limit order."""
        return await self.client.create_limit_order(symbol, side, amount, price, leverage)
    
    async def fetch_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Fetch current order status."""
        return await self.client.fetch_order_status(order_id, symbol)
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an open order."""
        return await self.client.cancel_order(order_id, symbol)
    
    async def fetch_open_positions(self) -> List[Dict[str, Any]]:
        """Fetch all open positions."""
        return await self.client.fetch_open_positions()
    
    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """Fetch positions from active exchange."""
        return await self.client.fetch_positions()
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get positions from active exchange."""
        return await self.client.get_positions()
    
    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get open positions from active exchange."""
        return await self.client.get_open_positions()
    
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close an open position."""
        return await self.client.close_position(symbol)
    
    def calculate_total_cost(
        self,
        price: float,
        amount: float,
        leverage: int = 1,
        include_fee: bool = True
    ) -> float:
        """Calculate total cost including fees."""
        return self.client.calculate_total_cost(price, amount, leverage, include_fee)
    
    async def close(self):
        """Close exchange connection."""
        await self.client.close()
    
    @property
    def info(self) -> Dict[str, Any]:
        """Get exchange manager information."""
        return {
            'exchange': self.exchange_name,
            'testnet': self.use_testnet,
            'mode': 'TESTNET' if self.use_testnet else 'LIVE'
        }
