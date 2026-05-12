"""
MEXC WebSocket Manager for real-time market data and position updates.
Handles connection management, reconnection logic, and event publishing.
Enhanced with heartbeat monitoring, stale stream detection, and graceful degradation.

Inspired by Hummingbot's WebSocket reliability patterns:
- Rigorous heartbeat ping/pong mechanism
- Stale stream detection (data flow monitoring)
- Exponential backoff with jitter
- State recovery on reconnect
- Circuit breaker integration
"""
import websockets
import json
import asyncio
import time
import random
from typing import List, Dict, Optional, Any
from collections import deque
from app.events.event_bus import event_bus
from app.events.event_types import (
    SYNC_RECEIVED, POSITION_UPDATED, ORDER_FILLED, 
    WEBSOCKET_DISCONNECTED, WEBSOCKET_RECONNECTED
)
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class MEXCWebSocketManager:
    """
    Manages MEXC WebSocket connections for real-time updates.
    Handles reconnection, subscription management, and event publishing.
    
    Hummingbot-inspired reliability features:
    - Rigorous heartbeat ping/pong mechanism
    - Stale stream detection (monitors data flow)
    - Exponential backoff with jitter
    - State recovery on reconnect
    - Circuit breaker integration
    
    Supports:
    - Position updates
    - Order fills
    - Balance changes
    - Automatic reconnection with exponential backoff + jitter
    """
    
    def __init__(self, market_type='futures'):
        self.market_type = market_type
        self.ws_url = self._get_ws_url()
        self.websocket = None
        self.subscriptions: List[Dict] = []
        self.running = False
        
        # Reconnection configuration (from settings)
        self.base_reconnect_delay = settings.WEBSOCKET_RECONNECT_DELAY
        self.max_reconnect_delay = settings.WEBSOCKET_MAX_RECONNECT_DELAY
        self.max_reconnect_attempts = settings.WEBSOCKET_MAX_RECONNECT_ATTEMPTS  # 0 = unlimited
        self.jitter_factor = settings.WEBSOCKET_JITTER_FACTOR
        
        # Current reconnection state
        self.reconnect_delay = self.base_reconnect_delay
        self.reconnect_attempts = 0
        
        # Heartbeat monitoring (Hummingbot pattern)
        self.last_heartbeat: Optional[float] = None
        self.heartbeat_interval = settings.WEBSOCKET_HEARTBEAT_INTERVAL
        self.heartbeat_timeout = settings.WEBSOCKET_HEARTBEAT_TIMEOUT
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._stale_stream_task: Optional[asyncio.Task] = None
        
        # Stale stream detection (Hummingbot pattern)
        self.last_message_time: Optional[float] = None
        self.stale_stream_threshold = settings.WEBSOCKET_STALE_STREAM_THRESHOLD
        
        # Message latency tracking
        self.message_latency_samples: deque = deque(maxlen=100)
        
        # Fallback REST polling
        self.use_rest_fallback = False
        self._rest_polling_task: Optional[asyncio.Task] = None
        
        # Connection state tracking
        self._connected_since: Optional[float] = None
        self._total_downtime_seconds = 0
        self._disconnect_count = 0
        
        # Circuit breaker for persistent failures
        self.circuit_breaker_threshold = 50  # Alert after 50 consecutive failures
        self.circuit_breaker_active = False
        self.last_alert_time: Optional[float] = None
        self.alert_cooldown = 3600  # Don't spam alerts (1 hour cooldown)
    
    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on market type."""
        if self.market_type == 'futures':
            return "wss://contract.mexc.com/ws"
        return "wss://wbs.mexc.com/ws"
    
    async def connect(self):
        """Establish WebSocket connection with auto-reconnect (Hummingbot pattern)."""
        self.running = True
        logger.info(f"🔌 Connecting to MEXC WebSocket: {self.ws_url}")
        
        while self.running:
            # Check max reconnect attempts (0 = unlimited)
            if self.max_reconnect_attempts > 0 and self.reconnect_attempts >= self.max_reconnect_attempts:
                logger.error(
                    f"❌ Max reconnection attempts reached ({self.max_reconnect_attempts}). "
                    f"Giving up."
                )
                await event_bus.publish(WEBSOCKET_DISCONNECTED, {
                    'message': 'Max reconnection attempts reached',
                    'attempt_count': self.reconnect_attempts,
                    'permanent_failure': True
                })
                break
            
            try:
                disconnect_start = time.time()
                self.websocket = await websockets.connect(self.ws_url)
                self._connected_since = time.time()
                self._disconnect_count += 1
                
                # Calculate downtime
                if self._disconnect_count > 1:
                    downtime = time.time() - disconnect_start
                    self._total_downtime_seconds += downtime
                
                logger.info("✅ MEXC WebSocket connected")
                
                # Resubscribe to all channels
                await self._resubscribe()
                
                # Reset reconnect delay and track attempt on successful connection
                old_attempts = self.reconnect_attempts
                self.reconnect_delay = self.base_reconnect_delay
                self.reconnect_attempts = 0
                
                # Reset circuit breaker on successful reconnect
                if self.circuit_breaker_active:
                    logger.info("✅ Circuit breaker RESET - WebSocket reconnected successfully")
                    self.circuit_breaker_active = False
                
                # Start heartbeat monitoring (Hummingbot pattern)
                self._heartbeat_task = asyncio.create_task(self._monitor_heartbeat())
                
                # Start stale stream detection (Hummingbot pattern)
                self._stale_stream_task = asyncio.create_task(self._detect_stale_streams())
                
                # Publish reconnection event (triggers PositionSyncService)
                await event_bus.publish(WEBSOCKET_RECONNECTED, {
                    'message': 'WebSocket reconnected successfully',
                    'attempt_count': old_attempts,
                    'downtime_seconds': round(self._total_downtime_seconds, 2),
                    'uptime_seconds': round(time.time() - self._connected_since, 2)
                })
                
                # Start listening for messages
                await self._listen()
                
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                logger.warning(f"   Code: {e.code if hasattr(e, 'code') else 'N/A'}")
                logger.warning(f"   Reason: {e.reason if hasattr(e, 'reason') else 'N/A'}")
                logger.warning(f"   Reconnect attempt #{self.reconnect_attempts + 1}")
                await self._handle_reconnect()
            except websockets.exceptions.InvalidStatusCode as e:
                logger.error(f"❌ WebSocket connection REJECTED with HTTP {e.status_code}")
                logger.error(f"   This usually indicates:")
                logger.error(f"   - Invalid WebSocket URL")
                logger.error(f"   - Firewall/proxy blocking WSS connections")
                logger.error(f"   - IP address banned by MEXC")
                logger.error(f"   - MEXC service temporarily unavailable")
                logger.error(f"   Attempting reconnect anyway...")
                await self._handle_reconnect()
            except ConnectionRefusedError as e:
                logger.error(f"❌ Connection REFUSED: {e}")
                logger.error(f"   Check firewall settings and network connectivity")
                await self._handle_reconnect()
            except Exception as e:
                logger.error(f"❌ WebSocket error: {type(e).__name__}: {e}")
                logger.error(f"   Full traceback:", exc_info=True)
                await self._handle_reconnect()
    
    async def subscribe(self, channel: str, symbol: str):
        """Subscribe to specific channel for a symbol."""
        # Normalize symbol format for MEXC
        normalized_symbol = symbol.lower().replace('/', '').replace('_', '')
        
        subscription = {
            'method': 'SUBSCRIPTION',
            'params': [f"{channel}@{normalized_symbol}"]
        }
        
        self.subscriptions.append(subscription)
        
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(subscription))
                logger.info(f"📡 Subscribed to {channel}@{normalized_symbol}")
            except Exception as e:
                logger.error(f"Failed to subscribe: {e}")
    
    async def _listen(self):
        """Listen for incoming WebSocket messages."""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self._handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed during listen")
            raise
        except Exception as e:
            logger.error(f"Error during WebSocket listen: {e}")
            raise
    
    async def _handle_message(self, data: dict):
        """Process incoming WebSocket message (Hummingbot pattern)."""
        try:
            # Update heartbeat and message timestamps
            current_time = time.time()
            self.last_heartbeat = current_time
            self.last_message_time = current_time  # Track for stale stream detection
            
            channel = data.get('c', '')
            
            if 'position' in channel or 'pos' in channel:
                await self._handle_position_update(data)
            elif 'order' in channel or 'deal' in channel:
                await self._handle_order_update(data)
            elif 'balance' in channel or 'asset' in channel:
                await self._handle_balance_update(data)
            else:
                logger.debug(f"Unhandled channel: {channel}")
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def _handle_position_update(self, data: dict):
        """Handle position update from WebSocket."""
        position_data = data.get('d', {})
        
        if not position_data:
            return
        
        # Publish sync received event
        await event_bus.publish(SYNC_RECEIVED, {
            'source': 'websocket',
            'type': 'position',
            'data': position_data
        })
        
        # Extract position fields (adapt to MEXC's actual field names)
        symbol = position_data.get('symbol', position_data.get('s', ''))
        size = float(position_data.get('size', position_data.get('positionAmt', 0)))
        entry_price = float(position_data.get('openPrice', position_data.get('entryPrice', 0)))
        mark_price = float(position_data.get('markPrice', position_data.get('p', 0)))
        unrealized_pnl = float(position_data.get('unrealizedPnl', position_data.get('up', 0)))
        liquidation_price = float(position_data.get('liqPrice', position_data.get('liquidationPrice', 0)))
        
        # Publish position updated event
        await event_bus.publish(POSITION_UPDATED, {
            'symbol': symbol,
            'size': size,
            'entry_price': entry_price,
            'current_price': mark_price,
            'unrealized_pnl': unrealized_pnl,
            'liquidation_price': liquidation_price
        })
        
        logger.debug(f"📊 Position update: {symbol} size={size} pnl={unrealized_pnl}")
    
    async def _handle_order_update(self, data: dict):
        """Handle order fill/update from WebSocket."""
        order_data = data.get('d', {})
        
        if not order_data:
            return
        
        order_status = order_data.get('status', order_data.get('s', ''))
        
        if order_status in ['FILLED', 'filled', '2']:  # MEXC uses '2' for filled
            # Publish order filled event
            await event_bus.publish(ORDER_FILLED, {
                'order_id': order_data.get('orderId', order_data.get('i', '')),
                'symbol': order_data.get('symbol', order_data.get('s', '')),
                'side': order_data.get('side', order_data.get('S', '')),
                'price': float(order_data.get('price', order_data.get('p', 0))),
                'quantity': float(order_data.get('executedQty', order_data.get('v', 0)))
            })
            
            logger.info(f"✅ Order filled: {order_data.get('orderId')}")
    
    async def _handle_balance_update(self, data: dict):
        """Handle balance update from WebSocket."""
        balance_data = data.get('d', {})
        
        if not balance_data:
            return
        
        # Publish balance update (can be used for risk management)
        await event_bus.publish(SYNC_RECEIVED, {
            'source': 'websocket',
            'type': 'balance',
            'data': balance_data
        })
        
        logger.debug(f"💰 Balance update received")
    
    async def _handle_reconnect(self):
        """Handle reconnection with exponential backoff + jitter (Hummingbot pattern)."""
        # Increment attempt counter
        self.reconnect_attempts = getattr(self, 'reconnect_attempts', 0) + 1
        
        # Circuit breaker: Check if we've exceeded threshold
        if self.reconnect_attempts >= self.circuit_breaker_threshold and not self.circuit_breaker_active:
            self.circuit_breaker_active = True
            logger.error(
                f"\n{'🚨'*30}\n"
                f"CIRCUIT BREAKER ACTIVATED!\n"
                f"WebSocket has failed {self.reconnect_attempts} consecutive times.\n"
                f"This indicates a PERSISTENT connectivity issue.\n"
                f"{'🚨'*30}\n"
            )
            
            # Send Telegram alert (with cooldown)
            current_time = time.time()
            if not self.last_alert_time or (current_time - self.last_alert_time) > self.alert_cooldown:
                try:
                    from app.notifications.notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    await notifier.send_message(
                        f"🚨 WEBSOCKET CIRCUIT BREAKER ACTIVATED\n\n"
                        f"MEXC WebSocket has failed {self.reconnect_attempts} consecutive reconnection attempts.\n\n"
                        f"This indicates a persistent issue:\n"
                        f"• Invalid API credentials\n"
                        f"• Firewall blocking WSS connections\n"
                        f"• MEXC service outage\n"
                        f"• IP address banned\n\n"
                        f"Action required: Run diagnostic script\n"
                        f"`python scripts/diagnose_websocket.py`\n\n"
                        f"System will continue retrying but you should investigate."
                    )
                    self.last_alert_time = current_time
                    logger.info("✅ Telegram alert sent")
                except Exception as e:
                    logger.error(f"Failed to send Telegram alert: {e}")
        
        # Calculate delay with exponential backoff
        delay = min(
            self.base_reconnect_delay * (2 ** (self.reconnect_attempts - 1)),
            self.max_reconnect_delay
        )
        
        # Add jitter to prevent thundering herd (Hummingbot pattern)
        jitter = delay * self.jitter_factor * random.random()
        delay_with_jitter = delay + jitter
        
        # Enhanced logging for debugging
        logger.warning(
            f"\n{'='*60}\n"
            f"⚠️  WEBSOCKET DISCONNECTED\n"
            f"{'='*60}\n"
            f"Reconnect attempt #{self.reconnect_attempts}\n"
            f"Base delay: {self.base_reconnect_delay}s\n"
            f"Calculated delay: {delay:.1f}s (capped at {self.max_reconnect_delay}s)\n"
            f"Jitter: {jitter:.1f}s ({self.jitter_factor*100:.0f}%)\n"
            f"Next retry in: {delay_with_jitter:.1f}s\n"
            f"Total disconnects so far: {self._disconnect_count}\n"
            f"Circuit breaker: {'ACTIVE 🚨' if self.circuit_breaker_active else 'inactive'}\n"
            f"{'='*60}"
        )
        
        await event_bus.publish(WEBSOCKET_DISCONNECTED, {
            'message': 'WebSocket disconnected, attempting reconnect',
            'reconnect_delay': round(delay_with_jitter, 2),
            'attempt_count': self.reconnect_attempts,
            'max_attempts': self.max_reconnect_attempts if self.max_reconnect_attempts > 0 else 'unlimited',
            'total_disconnects': self._disconnect_count,
            'circuit_breaker_active': self.circuit_breaker_active
        })
        
        await asyncio.sleep(delay_with_jitter)
    
    async def _resubscribe(self):
        """Resubscribe to all channels after reconnect."""
        if not self.websocket:
            return
        
        for subscription in self.subscriptions:
            try:
                await self.websocket.send(json.dumps(subscription))
                logger.debug(f"Resubscribed to {subscription['params']}")
            except Exception as e:
                logger.error(f"Failed to resubscribe: {e}")
    
    async def _monitor_heartbeat(self):
        """Monitor WebSocket connection health via heartbeat (Hummingbot pattern)."""
        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                # Check if we've received a message recently
                if self.last_heartbeat and (time.time() - self.last_heartbeat) > self.heartbeat_timeout:
                    logger.warning(
                        f"⚠️  Heartbeat timeout! Last heartbeat: {time.time() - self.last_heartbeat:.1f}s ago "
                        f"(threshold: {self.heartbeat_timeout}s). Forcing reconnect."
                    )
                    await self._handle_reconnect()
                    break
                
                # Send ping to keep connection alive
                if self.websocket:
                    try:
                        await self.websocket.ping()
                        logger.debug("💓 Heartbeat ping sent")
                    except Exception as e:
                        logger.warning(f"Heartbeat ping failed: {e}")
                        await self._handle_reconnect()
                        break
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")
    
    async def _detect_stale_streams(self):
        """
        Detect stale data streams (Hummingbot pattern).
        
        Monitors for lack of data updates even when WebSocket connection is open.
        This catches cases where the exchange stops sending data but keeps the connection alive.
        """
        while self.running:
            try:
                await asyncio.sleep(self.stale_stream_threshold / 2)  # Check at half the threshold
                
                # Check if we've received any messages recently
                if self.last_message_time:
                    time_since_last_message = time.time() - self.last_message_time
                    
                    if time_since_last_message > self.stale_stream_threshold:
                        logger.warning(
                            f"⚠️  Stale stream detected! No messages for {time_since_last_message:.1f}s "
                            f"(threshold: {self.stale_stream_threshold}s). "
                            f"Forcing reconnect to refresh data streams."
                        )
                        
                        # Publish stale stream event
                        await event_bus.publish(WEBSOCKET_DISCONNECTED, {
                            'message': 'Stale stream detected - no data updates',
                            'seconds_without_data': round(time_since_last_message, 2),
                            'threshold': self.stale_stream_threshold,
                            'stale_stream': True
                        })
                        
                        # Force reconnection
                        await self._handle_reconnect()
                        break
                    else:
                        logger.debug(
                            f"📊 Stream healthy: last message {time_since_last_message:.1f}s ago"
                        )
                else:
                    logger.debug("📊 Waiting for first message...")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stale stream detector error: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get WebSocket manager metrics (Hummingbot pattern)."""
        avg_latency = (
            sum(self.message_latency_samples) / len(self.message_latency_samples)
            if self.message_latency_samples else 0
        )
        
        uptime = None
        if self._connected_since:
            uptime = time.time() - self._connected_since
        
        return {
            'connected': self.websocket is not None,
            'subscriptions_count': len(self.subscriptions),
            'avg_message_latency_ms': round(avg_latency, 2),
            'last_heartbeat_age_s': (
                round(time.time() - self.last_heartbeat, 2)
                if self.last_heartbeat else None
            ),
            'last_message_age_s': (
                round(time.time() - self.last_message_time, 2)
                if self.last_message_time else None
            ),
            'use_rest_fallback': self.use_rest_fallback,
            'reconnect_attempts': self.reconnect_attempts,
            'disconnect_count': self._disconnect_count,
            'total_downtime_seconds': round(self._total_downtime_seconds, 2),
            'uptime_seconds': round(uptime, 2) if uptime else None,
            'stale_stream_threshold_s': self.stale_stream_threshold
        }
    
    async def disconnect(self):
        """Close WebSocket connection gracefully (Hummingbot pattern)."""
        logger.info("🛑 Disconnecting WebSocket...")
        self.running = False
        
        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._stale_stream_task:
            self._stale_stream_task.cancel()
            try:
                await self._stale_stream_task
            except asyncio.CancelledError:
                pass
        
        # Close WebSocket connection
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        logger.info(
            f"✅ WebSocket disconnected "
            f"(total_disconnects={self._disconnect_count}, "
            f"total_downtime={self._total_downtime_seconds:.1f}s)"
        )
