"""
News Guard - Protects trading around high-impact economic events.

Disables trading during:
- CPI (Consumer Price Index) releases
- NFP (Non-Farm Payrolls)
- FOMC (Federal Open Market Committee) decisions
- Powell speeches
- Other high-volatility news events

This prevents slippage and unpredictable price action during news.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from app.logging_config import get_logger

logger = get_logger(__name__)


class NewsEventType(Enum):
    """High-impact news event types."""
    CPI = "cpi"
    NFP = "nfp"
    FOMC = "fomc"
    POWELL_SPEECH = "powell_speech"
    INTEREST_RATE = "interest_rate"
    GDP = "gdp"


class NewsEvent:
    """Represents a scheduled news event."""
    
    def __init__(
        self,
        event_type: NewsEventType,
        scheduled_time: datetime,
        impact: str = "high",
        description: str = ""
    ):
        self.event_type = event_type
        self.scheduled_time = scheduled_time
        self.impact = impact
        self.description = description
    
    def is_active(self, buffer_minutes: int = 30) -> bool:
        """
        Check if this event is currently active (within buffer window).
        
        Args:
            buffer_minutes: Minutes before/after event to consider active
        
        Returns:
            True if current time is within buffer window
        """
        now = datetime.now(timezone.utc)
        window_start = self.scheduled_time - timedelta(minutes=buffer_minutes)
        window_end = self.scheduled_time + timedelta(minutes=buffer_minutes)
        
        return window_start <= now <= window_end
    
    def time_until_event(self) -> Optional[timedelta]:
        """Get time until this event."""
        now = datetime.now(timezone.utc)
        if self.scheduled_time > now:
            return self.scheduled_time - now
        return None


class NewsGuard:
    """
    Guards against trading during high-impact news events.
    
    Features:
    - Maintains calendar of scheduled news events
    - Blocks trading X minutes before/after events
    - Provides countdown to next event
    - Logs news-related trading blocks
    
    Usage:
        guard = NewsGuard()
        
        # Before executing trade
        if not guard.is_trading_safe():
            logger.warning("Trading blocked due to upcoming news event")
            return
        
        # Execute trade...
    """
    
    def __init__(self, default_buffer_minutes: int = 30):
        """
        Initialize news guard.
        
        Args:
            default_buffer_minutes: Default minutes to block before/after events
        """
        self.buffer_minutes = default_buffer_minutes
        self.events: List[NewsEvent] = []
        self.blocked_by_event: Optional[NewsEvent] = None
        
        logger.info(f"✅ NewsGuard initialized (buffer: {self.buffer_minutes}min)")
    
    def add_event(
        self,
        event_type: NewsEventType,
        scheduled_time: datetime,
        impact: str = "high",
        description: str = ""
    ):
        """
        Add a news event to the calendar.
        
        Args:
            event_type: Type of news event
            scheduled_time: When the event occurs (UTC)
            impact: Impact level (high/medium/low)
            description: Event description
        """
        event = NewsEvent(event_type, scheduled_time, impact, description)
        self.events.append(event)
        
        logger.info(
            f"📅 News event added: {event_type.value} at {scheduled_time.isoformat()}"
        )
    
    def is_trading_safe(self) -> bool:
        """
        Check if it's safe to trade (no active news events).
        
        Returns:
            True if no news events are currently active
        """
        for event in self.events:
            if event.is_active(self.buffer_minutes):
                self.blocked_by_event = event
                
                logger.warning(
                    f"🚫 Trading BLOCKED by news event: {event.event_type.value} "
                    f"({event.description})"
                )
                
                return False
        
        self.blocked_by_event = None
        return True
    
    def get_next_event(self) -> Optional[NewsEvent]:
        """
        Get the next upcoming news event.
        
        Returns:
            Next NewsEvent or None if no future events
        """
        now = datetime.now(timezone.utc)
        future_events = [e for e in self.events if e.scheduled_time > now]
        
        if not future_events:
            return None
        
        return min(future_events, key=lambda e: e.scheduled_time)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get news guard status.
        
        Returns:
            Dict with guard status information
        """
        next_event = self.get_next_event()
        
        return {
            "trading_safe": self.is_trading_safe(),
            "blocked_by": self.blocked_by_event.event_type.value if self.blocked_by_event else None,
            "buffer_minutes": self.buffer_minutes,
            "total_events": len(self.events),
            "next_event": {
                "type": next_event.event_type.value if next_event else None,
                "scheduled_time": next_event.scheduled_time.isoformat() if next_event else None,
                "time_until_minutes": int(next_event.time_until_event().total_seconds() / 60) if next_event and next_event.time_until_event() else None
            }
        }
    
    def clear_past_events(self):
        """Remove events that have already passed."""
        now = datetime.now(timezone.utc)
        self.events = [e for e in self.events if e.scheduled_time > now]
        
        logger.debug(f"Cleared past events, {len(self.events)} remaining")
    
    def load_upcoming_events(self):
        """
        Load upcoming high-impact events from external source.
        
        TODO: Integrate with economic calendar API (e.g., ForexFactory, Investing.com)
        For now, this is a stub that should be implemented with real data source.
        """
        logger.info("Loading upcoming news events...")
        
        # Placeholder - would fetch from API
        # Example integration:
        # response = await forex_factory_api.get_high_impact_events()
        # for event_data in response['events']:
        #     self.add_event(
        #         event_type=NewsEventType(event_data['type']),
        #         scheduled_time=datetime.fromisoformat(event_data['time']),
        #         description=event_data['description']
        #     )
        
        logger.info("News events loaded (stub - implement API integration)")
