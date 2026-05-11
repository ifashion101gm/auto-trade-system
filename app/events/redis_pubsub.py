"""
Redis Pub/Sub for distributed event handling.
Enables multiple consumers (Telegram, Dashboard, Analytics).
"""
import redis.asyncio as redis
import json
from typing import Callable
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class RedisEventBus:
    """Redis-based event bus for distributed systems."""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.channel_prefix = settings.REDIS_EVENT_CHANNEL_PREFIX
    
    async def publish(self, event_type: str, payload: dict):
        """Publish event to Redis channel."""
        channel = f"{self.channel_prefix}{event_type}"
        message = json.dumps({
            'type': event_type,
            'payload': payload
        })
        await self.redis_client.publish(channel, message)
        logger.debug(f"Published to Redis: {event_type}")
    
    async def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to Redis channel."""
        channel = f"{self.channel_prefix}{event_type}"
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel)
        
        # Start listening in background
        import asyncio
        asyncio.create_task(self._listen(pubsub, handler))
    
    async def _listen(self, pubsub, handler: Callable):
        """Listen for messages on subscribed channel."""
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    await handler(data)
        except Exception as e:
            logger.error(f"Redis subscription error: {e}")
