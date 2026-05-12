"""
Exchange Adapter with Circuit Breaker and Rate Limiting.
Wraps BaseExchange implementations to provide:
- Automatic retry logic with exponential backoff
- Circuit breaker pattern (fail fast after consecutive errors)
- Rate limit tracking and enforcement
- Request/response logging for debugging

Inspired by Freqtrade's exchange wrapper and Hummingbot's reliability patterns.
"""
import asyncio
import time
import logging
import random
import uuid
from typing import Dict, Any, Optional, Callable, List
from functools import wraps
from collections import deque

from app.exchange.base_exchange import BaseExchange
from app.logging_config import get_logger

logger = get_logger(__name__)


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open (too many failures)."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: Testing if service recovered, one request allowed
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def can_execute(self) -> bool:
        """Check if request can be executed based on circuit state."""
        if self.state == 'CLOSED':
            return True
        
        if self.state == 'OPEN':
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = 'HALF_OPEN'
                logger.info("🔧 Circuit breaker: OPEN -> HALF_OPEN (testing recovery)")
                return True
            return False
        
        # HALF_OPEN: allow one test request
        return True
    
    def record_success(self):
        """Record successful execution."""
        self.failure_count = 0
        self.state = 'CLOSED'
        logger.debug("✅ Circuit breaker: Success recorded, state=CLOSED")
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            old_state = self.state
            self.state = 'OPEN'
            logger.warning(
                f"🚨 Circuit breaker: {old_state} -> OPEN "
                f"(failures={self.failure_count}/{self.failure_threshold})"
            )
        else:
            logger.warning(
                f"⚠️  Circuit breaker: Failure {self.failure_count}/{self.failure_threshold}"
            )


class RateLimiter:
    """
    Simple rate limiter using token bucket algorithm.
    Prevents exceeding exchange API rate limits.
    """
    
    def __init__(self, max_calls: int = 10, time_window: float = 1.0):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: deque = deque(maxlen=max_calls)
    
    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove old calls outside time window
        while self.calls and self.calls[0] < (now - self.time_window):
            self.calls.popleft()
        
        # Check if we've hit the limit
        if len(self.calls) >= self.max_calls:
            wait_time = self.time_window - (now - self.calls[0])
            if wait_time > 0:
                logger.debug(f"⏳ Rate limiter: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
        
        # Record this call
        self.calls.append(time.time())


class ExchangeAdapter:
    """
    Adapter that wraps BaseExchange with reliability features.
    
    Provides:
    - Circuit breaker for fault tolerance
    - Rate limiting to respect API limits
    - Automatic retries with exponential backoff
    - Request/response logging
    - Latency tracking
    """
    
    def __init__(
        self,
        exchange: BaseExchange,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60,
        rate_limit_calls: int = 10,
        rate_limit_window: float = 1.0
    ):
        self.exchange = exchange
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        # Initialize reliability components
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            recovery_timeout=circuit_breaker_timeout
        )
        self.rate_limiter = RateLimiter(
            max_calls=rate_limit_calls,
            time_window=rate_limit_window
        )
        
        # Metrics tracking
        self.request_count = 0
        self.error_count = 0
        self.latencies: deque = deque(maxlen=100)
        
        logger.info(f"✅ ExchangeAdapter initialized for {exchange.mode}")
    
    async def execute_with_retry(
        self,
        operation_name: str,
        func: Callable,
        *args,
        idempotency_key: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Execute operation with circuit breaker, rate limiting, and retries.
        
        Args:
            operation_name: Name of operation for logging
            func: Async function to execute
            *args: Arguments to pass to func
            idempotency_key: Optional key for idempotent operations (prevents duplicates)
            **kwargs: Keyword arguments to pass to func
            
        Returns:
            Result from successful execution
            
        Raises:
            CircuitBreakerError: If circuit breaker is open
            Exception: If all retries exhausted
        """
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerError(
                f"Circuit breaker is OPEN. Cannot execute {operation_name}"
            )
        
        # Wait for rate limit
        await self.rate_limiter.wait_if_needed()
        
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            start_time = time.time()
            
            try:
                # Idempotency check: verify order doesn't already exist before retry
                if idempotency_key and attempt > 1:
                    try:
                        # Check if order was actually created despite previous error
                        existing_order = await self.exchange.fetch_order_by_client_id(idempotency_key)
                        if existing_order:
                            logger.info(f"✅ Idempotency check: Order already exists: {idempotency_key}")
                            return existing_order
                    except Exception:
                        pass  # Order doesn't exist, proceed with retry
                
                # Execute the operation
                result = await func(*args, **kwargs)
                
                # Record success
                elapsed = time.time() - start_time
                self.latencies.append(elapsed * 1000)  # ms
                self.request_count += 1
                self.circuit_breaker.record_success()
                
                logger.debug(
                    f"✅ {operation_name} succeeded "
                    f"(attempt={attempt}, latency={elapsed*1000:.0f}ms)"
                )
                
                return result
                
            except Exception as e:
                last_exception = e
                elapsed = time.time() - start_time
                self.error_count += 1
                
                # Record failure in circuit breaker
                self.circuit_breaker.record_failure()
                
                # Check if error is retryable
                if not self._is_retryable_error(e):
                    logger.error(f"❌ {operation_name} failed with non-retryable error: {e}")
                    raise
                
                # Check if we should retry
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff + jitter
                    base_delay = self.base_delay * (2 ** (attempt - 1))
                    jitter = base_delay * 0.1 * random.random()  # 10% jitter
                    delay = min(base_delay + jitter, self.max_delay)
                    
                    logger.warning(
                        f"⚠️  {operation_name} failed (attempt {attempt}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"❌ {operation_name} failed after {self.max_retries} attempts. "
                        f"Last error: {e}"
                    )
                    raise Exception(
                        f"{operation_name} failed after {self.max_retries} retries. "
                        f"Last error: {last_exception}"
                    )
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if error is retryable.
        
        Retryable errors:
        - Network timeouts
        - Connection errors
        - Temporary server errors (5xx)
        
        Non-retryable errors:
        - Authentication failures
        - Invalid parameters
        - Insufficient balance
        """
        error_msg = str(error).lower()
        error_code = getattr(error, 'code', None)
        
        # Non-retryable: Client errors (4xx)
        non_retryable_codes = [400, 401, 403, 404, 422]
        if error_code in non_retryable_codes:
            return False
        
        # Non-retryable keywords
        non_retryable_keywords = [
            'invalid api key',
            'authentication',
            'insufficient balance',
            'invalid parameter',
            'symbol not found',
            'order not found',
            'insufficient funds',
            'minimum order size'
        ]
        
        for keyword in non_retryable_keywords:
            if keyword in error_msg:
                return False
        
        # Default: assume retryable (network issues, 5xx errors, timeouts)
        return True
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get adapter performance metrics."""
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        error_rate = (
            (self.error_count / self.request_count * 100)
            if self.request_count > 0 else 0
        )
        
        return {
            'request_count': self.request_count,
            'error_count': self.error_count,
            'error_rate_pct': round(error_rate, 2),
            'avg_latency_ms': round(avg_latency, 2),
            'circuit_breaker_state': self.circuit_breaker.state,
            'mode': self.exchange.mode
        }
    
    # =========================================================================
    # Delegate all BaseExchange methods with retry logic
    # =========================================================================
    
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        return await self.execute_with_retry(
            f"fetch_ticker({symbol})",
            self.exchange.fetch_ticker,
            symbol
        )
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> List[List]:
        return await self.execute_with_retry(
            f"fetch_ohlcv({symbol}, {timeframe})",
            self.exchange.fetch_ohlcv,
            symbol, timeframe, limit
        )
    
    async def fetch_markets(self) -> List[Dict[str, Any]]:
        return await self.execute_with_retry(
            "fetch_markets",
            self.exchange.fetch_markets
        )
    
    async def get_balance(self) -> Dict[str, Any]:
        return await self.execute_with_retry(
            "get_balance",
            self.exchange.get_balance
        )
    
    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # Generate idempotency key if not provided
        client_order_id = params.get('clientOrderId') if params else None
        if not client_order_id:
            client_order_id = f"ord_{uuid.uuid4().hex[:16]}"
            if params is None:
                params = {}
            params['clientOrderId'] = client_order_id
        
        return await self.execute_with_retry(
            f"create_market_order({symbol}, {side}, {amount})",
            self.exchange.create_market_order,
            symbol, side, amount, params,
            idempotency_key=client_order_id
        )
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # Generate idempotency key if not provided
        client_order_id = params.get('clientOrderId') if params else None
        if not client_order_id:
            client_order_id = f"ord_{uuid.uuid4().hex[:16]}"
            if params is None:
                params = {}
            params['clientOrderId'] = client_order_id
        
        return await self.execute_with_retry(
            f"create_limit_order({symbol}, {side}, {amount}@{price})",
            self.exchange.create_limit_order,
            symbol, side, amount, price, params,
            idempotency_key=client_order_id
        )
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        return await self.execute_with_retry(
            f"cancel_order({order_id})",
            self.exchange.cancel_order,
            order_id, symbol
        )
    
    async def fetch_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        return await self.execute_with_retry(
            f"fetch_order_status({order_id})",
            self.exchange.fetch_order_status,
            order_id, symbol
        )
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        return await self.execute_with_retry(
            f"fetch_open_orders({symbol or 'all'})",
            self.exchange.fetch_open_orders,
            symbol
        )
    
    async def fetch_order_history(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        return await self.execute_with_retry(
            f"fetch_order_history({symbol})",
            self.exchange.fetch_order_history,
            symbol, since, limit
        )
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        return await self.execute_with_retry(
            "get_positions",
            self.exchange.get_positions
        )
    
    async def close_position(self, symbol: str) -> Dict[str, Any]:
        return await self.execute_with_retry(
            f"close_position({symbol})",
            self.exchange.close_position,
            symbol
        )
    
    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        return await self.execute_with_retry(
            f"set_leverage({symbol}, {leverage}x)",
            self.exchange.set_leverage,
            symbol, leverage
        )
    
    def calculate_fee(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float,
        taker_or_maker: str = 'taker'
    ) -> float:
        return self.exchange.calculate_fee(symbol, order_type, side, amount, price, taker_or_maker)
    
    async def validate_symbol(self, symbol: str) -> bool:
        return await self.execute_with_retry(
            f"validate_symbol({symbol})",
            self.exchange.validate_symbol,
            symbol
        )
    
    async def close(self):
        await self.exchange.close()
    
    @property
    def has_watch_ohlcv(self) -> bool:
        return self.exchange.has_watch_ohlcv
    
    @property
    def has_create_stop_loss_limit(self) -> bool:
        return self.exchange.has_create_stop_loss_limit
    
    @property
    def mode(self) -> str:
        return self.exchange.mode
