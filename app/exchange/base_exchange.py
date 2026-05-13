"""
Abstract base class for all exchange implementations.
Ensures consistent interface across LIVE and DEMO modes.
Follows CCXT unified API standards for exchange abstraction.

ERROR HANDLING CONTRACT:
All subclasses MUST implement:
- handle_api_error(): Standardized error processing
- is_retryable_error(): Retry decision logic  
- classify_error(): Error categorization

Common error patterns to handle:
- Network timeouts (httpx.TimeoutException, asyncio.TimeoutError)
- Rate limits (HTTP 429, exchange-specific rate limit errors)
- Authentication failures (HTTP 401/403, invalid signature)
- Validation errors (HTTP 400/422, invalid parameters)
- Server errors (HTTP 5xx, exchange maintenance)
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseExchange(ABC):
    """
    Abstract base class for all exchange implementations.
    Ensures consistent interface across LIVE and DEMO modes.
    
    This follows CCXT's unified API pattern to enable:
    - Multi-exchange support without code duplication
    - Consistent order lifecycle management
    - Standardized error handling and retries
    """
    
    # =========================================================================
    # Connection & State Management Methods
    # =========================================================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """Initialize connection and verify exchange health."""
        pass
    
    @abstractmethod
    async def sync_state(self) -> Dict[str, Any]:
        """Synchronize full exchange state (positions, orders, balance)."""
        pass
    
    # =========================================================================
    # Market Data Methods
    # =========================================================================
    
    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get real-time ticker data."""
        pass
    
    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List]:
        """Fetch OHLCV candlestick data."""
        pass
    
    @abstractmethod
    async def fetch_markets(self) -> List[Dict[str, Any]]:
        """Fetch available trading pairs/markets."""
        pass
    
    # =========================================================================
    # Account & Balance Methods
    # =========================================================================
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        pass
    
    # =========================================================================
    # Order Management Methods
    # =========================================================================
    
    @abstractmethod
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a market order."""
        pass
    
    @abstractmethod
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a limit order."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancel an open order."""
        pass
    
    @abstractmethod
    async def fetch_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Fetch current order status."""
        pass
    
    @abstractmethod
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all open orders, optionally filtered by symbol."""
        pass
    
    @abstractmethod
    async def fetch_order_history(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch historical orders."""
        pass
    
    # =========================================================================
    # Position Management Methods
    # =========================================================================
    
    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        pass
    
    @abstractmethod
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close an existing position."""
        pass
    
    @abstractmethod
    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a specific trading pair."""
        pass
    
    # =========================================================================
    # Feature Flags (CCXT Pattern)
    # =========================================================================
    
    @property
    @abstractmethod
    def has_watch_ohlcv(self) -> bool:
        """Indicates if exchange supports real-time OHLCV streaming."""
        pass
    
    @property
    @abstractmethod
    def has_create_stop_loss_limit(self) -> bool:
        """Indicates if exchange supports stop-loss limit orders."""
        pass
    
    @property
    @abstractmethod
    def mode(self) -> str:
        """Return exchange mode: 'LIVE' or 'DEMO'."""
        pass
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is available on this exchange."""
        pass
    
    @abstractmethod
    async def close(self):
        """Close exchange connection gracefully."""
        pass
    
    # =========================================================================
    # Error Handling Methods (Required by all subclasses)
    # =========================================================================
    
    @abstractmethod
    def handle_api_error(self, error: Exception) -> Dict[str, Any]:
        """
        Handle API errors consistently across exchanges.
        
        Args:
            error: The exception raised during API call
            
        Returns:
            Dictionary with error classification:
            - 'type': 'network' | 'auth' | 'rate_limit' | 'validation' | 'server'
            - 'retryable': bool
            - 'message': str (user-friendly message)
            - 'original_error': Exception
        """
        pass
    
    @abstractmethod
    def is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error should trigger automatic retry.
        
        Retryable errors:
        - Network timeouts and connection errors
        - Temporary server errors (5xx)
        - Rate limit exceeded (429) with backoff
        
        Non-retryable errors:
        - Authentication failures (401, 403)
        - Invalid parameters (400, 422)
        - Insufficient balance/funds
        - Symbol/order not found (404)
        
        Args:
            error: The exception to evaluate
            
        Returns:
            True if error is transient and should be retried
        """
        pass
    
    @abstractmethod
    def classify_error(self, error: Exception) -> str:
        """
        Classify error type for appropriate handling strategy.
        
        Returns one of:
        - 'NETWORK_TIMEOUT': Connection or timeout issues
        - 'AUTH_FAILURE': Invalid credentials or permissions
        - 'RATE_LIMIT': API rate limit exceeded
        - 'VALIDATION_ERROR': Invalid request parameters
        - 'SERVER_ERROR': Exchange internal error (5xx)
        - 'NOT_FOUND': Resource doesn't exist
        - 'UNKNOWN': Unclassified error
        
        Args:
            error: The exception to classify
            
        Returns:
            Error classification string
        """
        pass
