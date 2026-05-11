"""
Async event bus for decoupled communication between agents.

Events flow: Exchange → Sync Agent → Event Bus → DB + Telegram + Dashboard
"""
import asyncio
from typing import Callable, Dict, List, Any
from datetime import datetime
import json


class EventBus:
    """
    Async event bus for decoupled communication between agents.
    
    Events flow: Exchange → Sync Agent → Event Bus → DB + Telegram + Dashboard
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Dict] = []
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    async def publish(self, event_type: str, payload: Dict[str, Any]):
        """Publish event to all subscribers."""
        event = {
            'type': event_type,
            'payload': payload,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Store in history
        self._event_history.append(event)
        
        # Notify subscribers
        if event_type in self._subscribers:
            tasks = [handler(event) for handler in self._subscribers[event_type]]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        return event
    
    def get_event_history(self, limit: int = 100):
        """Get recent event history."""
        return self._event_history[-limit:]


# Global event bus instance
event_bus = EventBus()
