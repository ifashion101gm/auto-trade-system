"""
MEXC WebSocket Manager for real-time market data and position updates.
Handles connection management, reconnection logic, and event publishing.
"""
import websockets
import json
import asyncio
from typing import List, Dict
from app.events.event_bus import event_bus
from app.events.event_types import (
    SYNC_RECEIVED, POSITION_UPDATED, ORDER_FILLED, 
    WEBSOCKET_DISCONNECTED, WEBSOCKET_RECONNECTED
)
import logging

logger = logging.getLogger(__name__)


class MEXCWebSocketManager:
    """
    Manages MEXC WebSocket connections for real-time updates.
    Handles reconnection, subscription management, and event publishing.
    
    Supports:
    - Position updates
    - Order fills
    - Balance changes
    - Automatic reconnection with exponential backoff
    """
    
    def __init__(self, market_type='futures'):
        self.market_type = market_type
        self.ws_url = self._get_ws_url()
        self.websocket = None
        self.subscriptions: List[Dict] = []
        self.running = False
        self.reconnect_delay = 2
        self.max_reconnect_delay = 60
    
    def _get_ws_url(self) -> str:
        """Get WebSocket URL based on market type."""
        if self.market_type == 'futures':
            return "wss://contract.mexc.com/ws"
        return "wss://wbs.mexc.com/ws"
    
    async def connect(self):
        """Establish WebSocket connection with auto-reconnect."""
        self.running = True
        logger.info(f"🔌 Connecting to MEXC WebSocket: {self.ws_url}")
        
        while self.running:
            try:
                self.websocket = await websockets.connect(self.ws_url)
                logger.info("✅ MEXC WebSocket connected")
                
                # Resubscribe to all channels
                await self._resubscribe()
                
                # Publish reconnection event
                await event_bus.publish(WEBSOCKET_RECONNECTED, {
                    'message': 'WebSocket reconnected successfully'
                })
                
                # Start listening
                await self._listen()
                
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                await self._handle_reconnect()
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
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
        """Process incoming WebSocket message."""
        try:
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
        """Handle reconnection with exponential backoff."""
        await event_bus.publish(WEBSOCKET_DISCONNECTED, {
            'message': 'WebSocket disconnected, attempting reconnect'
        })
        
        delay = min(self.reconnect_delay, self.max_reconnect_delay)
        logger.info(f"🔄 Reconnecting in {delay}s...")
        await asyncio.sleep(delay)
        
        # Exponential backoff
        self.reconnect_delay *= 2
    
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
    
    async def disconnect(self):
        """Close WebSocket connection gracefully."""
        logger.info("🛑 Disconnecting WebSocket...")
        self.running = False
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        logger.info("✅ WebSocket disconnected")
