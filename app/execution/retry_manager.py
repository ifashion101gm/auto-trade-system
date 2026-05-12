"""
Smart Retry System with exponential backoff and idempotency.
Prevents duplicate orders and handles transient failures gracefully.
"""
import asyncio
import time
import uuid
import random
from typing import Callable, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class IdempotencyManager:
    """Ensures idempotent order submission using client_order_id."""
    
    def __init__(self):
        self.submitted_orders: Dict[str, Dict] = {}  # client_order_id -> result
    
    def generate_client_order_id(self, prefix: str = "ORD") -> str:
        """Generate unique client order ID for idempotency."""
        timestamp = int(time.time() * 1000)
        unique_id = uuid.uuid4().hex[:8]
        return f"{prefix}_{timestamp}_{unique_id}"
    
    def check_duplicate(self, client_order_id: str) -> Optional[Dict]:
        """Check if order was already submitted."""
        return self.submitted_orders.get(client_order_id)
    
    def record_submission(self, client_order_id: str, result: Dict):
        """Record successful submission."""
        self.submitted_orders[client_order_id] = result


class SmartRetryManager:
    """
    Handles retries with exponential backoff and idempotency checks.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.idempotency_mgr = IdempotencyManager()
    
    async def execute_with_retry(
        self,
        operation: Callable,
        client_order_id: Optional[str] = None,
        operation_name: str = "order_execution",
        **kwargs
    ) -> Any:
        """
        Execute operation with smart retry logic.
        
        Args:
            operation: Async callable to execute
            client_order_id: Idempotency key
            operation_name: Name for logging
            **kwargs: Arguments to pass to operation
        
        Returns:
            Result from successful operation
        
        Raises:
            Exception: After all retries exhausted
        """
        # Check idempotency
        if client_order_id:
            previous_result = self.idempotency_mgr.check_duplicate(client_order_id)
            if previous_result:
                logger.info(f"🔄 Idempotency check: Reusing previous result for {client_order_id}")
                return previous_result
        
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.info(f"⚡ {operation_name}: Attempt {attempt + 1}/{self.config.max_retries + 1}")
                
                result = await operation(**kwargs)
                
                # Record successful submission for idempotency
                if client_order_id:
                    self.idempotency_mgr.record_submission(client_order_id, result)
                
                logger.info(f"✅ {operation_name}: Success on attempt {attempt + 1}")
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"⚠️ {operation_name}: Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"⏳ Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ {operation_name}: All retries exhausted")
        
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter."""
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay
        )
        
        if self.config.jitter:
            delay = delay * (0.5 + random.random() * 0.5)  # 50-100% of calculated delay
        
        return delay
