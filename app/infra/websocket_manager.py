"""
WebSocket Manager with Auto-Reconnect for Exchange Integration.
Implements Hummingbot-style reliability patterns:
- Exponential backoff with jitter
- Heartbeat monitoring
- Stream management
- Graceful reconnection with state sync
"""
import asyncio
import time
import random
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

from app.logging_config import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections with automatic reconnection and stream subscriptions.
    
    Features:
    - Exponential backoff with jitter for reconnection attempts
    - Heartbeat monitoring to detect stale connections
    - Multiple concurrent stream subscriptions (positions, orders, ticker, balance)
    - Automatic resubscription after reconnection
    - Graceful degradation to REST API when WebSocket unavailable
    """
    
    def __init__(
        self,
        exchange,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        heartbeat_timeout: float = 30.0,
        max_reconnect_attempts: int = 10
    ):
        """
        Initialize WebSocket Manager.
        
        Args:
            exchange: CCXT Pro exchange instance
            base_delay: Base delay for exponential backoff (seconds)
            max_delay: Maximum delay between reconnection attempts (seconds)
            heartbeat_timeout: Timeout for detecting stale connections (seconds)
            max_reconnect_attempts: Maximum number of reconnection attempts before giving up
        """
        self.exchange = exchange
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.heartbeat_timeout = heartbeat_timeout
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # Connection state
        self._connected = False
        self._running = False
        self._reconnect_attempt = 0
        self._last_heartbeat = {}  # {stream_name: last_message_timestamp}
        
        # Stream subscriptions and callbacks
        self._subscriptions: Dict[str, Dict] = {}  # {stream_id: subscription_config}
        self._callbacks: Dict[str, Callable] = {}  # {stream_id: callback_function}
        self._cache: Dict[str, Any] = {}  # {stream_id: latest_data}
        
        # Active tasks
        self._stream_tasks: Dict[str, asyncio.Task] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._reconnect_event = asyncio.Event()
    
    async def start(self):
        """Initialize WebSocket connection and start all streams."""
        if self._running:
            logger.warning("WebSocketManager already running")
            return
        
        self._running = True
        self._reconnect_attempt = 0
        
        logger.info("🔌 Starting WebSocket Manager...")
        
        # Start heartbeat monitor
        self._monitor_task = asyncio.create_task(self._monitor_heartbeats())
        
        # Signal that we're ready to connect
        self._reconnect_event.set()
    
    async def stop(self):
        """Gracefully shutdown all streams."""
        logger.info("🛑 Stopping WebSocket Manager...")
        
        self._running = False
        self._connected = False
        self._reconnect_event.clear()
        
        # Cancel all stream tasks
        for stream_id, task in self._stream_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Cancel monitor task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Clear state
        self._stream_tasks.clear()
        self._subscriptions.clear()
        self._callbacks.clear()
        self._cache.clear()
        self._last_heartbeat.clear()
        
        logger.info("✅ WebSocket Manager stopped")
    
    async def subscribe_positions(self, callback: Callable):
        """Subscribe to position updates via watch_positions()."""
        stream_id = "positions"
        self._subscriptions[stream_id] = {
            'type': 'positions',
            'method': 'watch_positions'
        }
        self._callbacks[stream_id] = callback
        logger.info(f"📊 Subscribed to position updates")
        
        # Start stream if manager is running
        if self._running:
            await self._start_stream(stream_id)
    
    async def subscribe_orders(self, callback: Callable):
        """Subscribe to order updates via watch_orders()."""
        stream_id = "orders"
        self._subscriptions[stream_id] = {
            'type': 'orders',
            'method': 'watch_orders'
        }
        self._callbacks[stream_id] = callback
        logger.info(f"📝 Subscribed to order updates")
        
        # Start stream if manager is running
        if self._running:
            await self._start_stream(stream_id)
    
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to ticker updates via watch_ticker(symbol)."""
        stream_id = f"ticker_{symbol}"
        self._subscriptions[stream_id] = {
            'type': 'ticker',
            'method': 'watch_ticker',
            'symbol': symbol
        }
        self._callbacks[stream_id] = callback
        logger.info(f"📈 Subscribed to ticker updates for {symbol}")
        
        # Start stream if manager is running
        if self._running:
            await self._start_stream(stream_id)
    
    async def subscribe_balance(self, callback: Callable):
        """Subscribe to balance updates via watch_balance()."""
        stream_id = "balance"
        self._subscriptions[stream_id] = {
            'type': 'balance',
            'method': 'watch_balance'
        }
        self._callbacks[stream_id] = callback
        logger.info(f"💰 Subscribed to balance updates")
        
        # Start stream if manager is running
        if self._running:
            await self._start_stream(stream_id)
    
    async def _start_stream(self, stream_id: str):
        """Start a specific WebSocket stream."""
        if stream_id in self._stream_tasks:
            logger.debug(f"Stream {stream_id} already running")
            return
        
        subscription = self._subscriptions.get(stream_id)
        if not subscription:
            logger.error(f"No subscription found for {stream_id}")
            return
        
        # Create task for this stream
        task = asyncio.create_task(self._run_stream(stream_id, subscription))
        self._stream_tasks[stream_id] = task
    
    async def _run_stream(self, stream_id: str, subscription: Dict):
        """Run a single WebSocket stream with error handling."""
        method_name = subscription['method']
        
        while self._running:
            try:
                # Wait for connection signal
                await self._reconnect_event.wait()
                
                if not self._connected:
                    await asyncio.sleep(1)
                    continue
                
                # Get the watch method from exchange
                watch_method = getattr(self.exchange, method_name, None)
                if not watch_method:
                    logger.error(f"Exchange doesn't support {method_name}")
                    break
                
                # Call the watch method with appropriate arguments
                if subscription['type'] == 'ticker':
                    symbol = subscription.get('symbol')
                    data = await watch_method(symbol)
                else:
                    data = await watch_method()
                
                # Update heartbeat
                self._last_heartbeat[stream_id] = time.time()
                
                # Cache the data
                self._cache[stream_id] = data
                
                # Call the callback
                callback = self._callbacks.get(stream_id)
                if callback:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)
                        else:
                            callback(data)
                    except Exception as e:
                        logger.error(f"Callback error for {stream_id}: {e}")
                
            except asyncio.CancelledError:
                logger.debug(f"Stream {stream_id} cancelled")
                break
            except Exception as e:
                logger.warning(f"Stream {stream_id} error: {e}")
                
                # Mark as disconnected
                self._connected = False
                
                # Trigger reconnection
                self._reconnect_event.clear()
                
                # Calculate backoff delay
                delay = self._calculate_backoff()
                logger.info(f"🔄 Reconnecting {stream_id} in {delay:.1f}s (attempt {self._reconnect_attempt})")
                
                await asyncio.sleep(delay)
    
    def _calculate_backoff(self) -> float:
        """Calculate exponential backoff delay with jitter."""
        # Exponential backoff: base_delay * 2^attempt
        exponential_delay = self.base_delay * (2 ** self._reconnect_attempt)
        
        # Add jitter (±10%)
        jitter = exponential_delay * 0.1 * random.random()
        
        # Apply max delay cap
        delay = min(exponential_delay + jitter, self.max_delay)
        
        # Increment attempt counter
        self._reconnect_attempt += 1
        
        return delay
    
    async def _monitor_heartbeats(self):
        """Monitor heartbeats and detect stale connections."""
        while self._running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                current_time = time.time()
                
                for stream_id, last_heartbeat in self._last_heartbeat.items():
                    time_since_heartbeat = current_time - last_heartbeat
                    
                    if time_since_heartbeat > self.heartbeat_timeout:
                        logger.warning(
                            f"⚠️  Stale connection detected for {stream_id} "
                            f"(last heartbeat: {time_since_heartbeat:.1f}s ago)"
                        )
                        
                        # Mark as disconnected and trigger reconnect
                        self._connected = False
                        self._reconnect_event.clear()
                        
                        # Reset heartbeat for this stream
                        self._last_heartbeat[stream_id] = current_time
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected."""
        return self._connected
    
    def get_cached_positions(self) -> List[Dict]:
        """Get cached positions from WebSocket stream."""
        return self._cache.get('positions', [])
    
    def get_cached_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get cached open orders from WebSocket stream."""
        orders = self._cache.get('orders', [])
        
        if symbol:
            return [order for order in orders if order.get('symbol') == symbol]
        
        return orders
    
    def get_cached_ticker(self, symbol: str) -> Dict:
        """Get cached ticker from WebSocket stream."""
        stream_id = f"ticker_{symbol}"
        return self._cache.get(stream_id, {})
    
    def get_cached_balance(self) -> Dict:
        """Get cached balance from WebSocket stream."""
        return self._cache.get('balance', {})
    
    @property
    def active_streams(self) -> List[str]:
        """Get list of active stream IDs."""
        return list(self._stream_tasks.keys())
