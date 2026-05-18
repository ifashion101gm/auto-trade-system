"""
Event Store for persisting trading events to database.
Implements event sourcing pattern for audit trail and state reconstruction.

Inspired by Hummingbot's event persistence and Freqtrade's trade history tracking.
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.models import OrderEvents
from app.logging_config import get_logger

logger = get_logger(__name__)


class EventStore:
    """
    Persists critical trading events to database for:
    - Audit trail and compliance
    - Debugging and post-mortem analysis
    - State reconstruction after crashes
    - Performance analytics
    
    Events persisted:
    - ORDER_SUBMITTED, ORDER_FILLED, ORDER_CANCELLED
    - POSITION_UPDATED, POSITION_CLOSED
    - SYNC_MISMATCH, SYNC_REPAIRED
    - STATE_CHANGED (from state machine)
    """
    
    # Critical events that MUST be persisted
    CRITICAL_EVENTS = {
        'ORDER_SUBMITTED',
        'ORDER_FILLED',
        'ORDER_PARTIALLY_FILLED',
        'ORDER_CANCELLED',
        'ORDER_REJECTED',
        'POSITION_UPDATED',
        'POSITION_CLOSED',
        'SYNC_MISMATCH',
        'SYNC_REPAIRED',
        'STATE_CHANGED'
    }
    
    def __init__(self):
        logger.info("✅ EventStore initialized")
    
    async def persist_event(
        self,
        event: Dict[str, Any],
        db_session: AsyncSession,
        correlation_id: Optional[str] = None
    ):
        """
        Persist event to database if it's a critical event type.
        
        Args:
            event: Event dict with type, payload, timestamp
            db_session: Database session
            correlation_id: Optional ID to link related events (e.g., trade_id)
        """
        event_type = event.get('type', '')
        
        # Only persist critical events
        if event_type not in self.CRITICAL_EVENTS:
            return
        
        try:
            # Extract trade_id from payload if available
            trade_id = correlation_id or event.get('payload', {}).get('trade_id')
            
            # Create order event record
            # FIXED: Pass dict directly to SQLAlchemy JSON column (not json.dumps string)
            order_event = OrderEvents(
                id=self._generate_id(),
                trade_id=trade_id,
                event_type=event_type,
                payload=event,  # Pass dict - SQLAlchemy handles JSON serialization
                created_at=datetime.utcnow().isoformat()
            )
            
            db_session.add(order_event)
            await db_session.flush()
            
            logger.debug(f"💾 Persisted event: {event_type} (trade_id={trade_id})")
            
        except Exception as e:
            logger.error(f"Failed to persist event {event_type}: {e}")
            # Don't raise - event persistence shouldn't break main flow
    
    async def get_events_for_trade(
        self,
        trade_id: str,
        db_session: AsyncSession,
        event_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all events for a specific trade.
        
        Useful for:
        - Debugging trade execution issues
        - Reconstructing trade timeline
        - Auditing
        
        Args:
            trade_id: Trade ID to query
            db_session: Database session
            event_type: Filter by event type (optional)
            limit: Maximum events to return (optional)
        
        Returns:
            List of event dicts sorted by creation time
        """
        try:
            query = select(OrderEvents).where(OrderEvents.trade_id == trade_id)
            
            if event_type:
                query = query.where(OrderEvents.event_type == event_type)
            
            query = query.order_by(OrderEvents.created_at.asc())
            
            if limit:
                query = query.limit(limit)
            
            result = await db_session.execute(query)
            events = result.scalars().all()
            
            # Parse JSON payloads
            parsed_events = []
            for event in events:
                parsed_events.append({
                    'id': event.id,
                    'trade_id': event.trade_id,
                    'event_type': event.event_type,
                    'payload': json.loads(event.payload),
                    'created_at': event.created_at
                })
            
            logger.debug(f"Retrieved {len(parsed_events)} events for trade {trade_id}")
            return parsed_events
            
        except Exception as e:
            logger.error(f"Failed to retrieve events for trade {trade_id}: {e}")
            return []
    
    async def get_recent_events(
        self,
        db_session: AsyncSession,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get most recent events across all trades.
        
        Args:
            db_session: Database session
            event_type: Filter by event type (optional)
            limit: Maximum events to return
        
        Returns:
            List of recent event dicts
        """
        try:
            query = select(OrderEvents).order_by(OrderEvents.created_at.desc()).limit(limit)
            
            if event_type:
                query = query.where(OrderEvents.event_type == event_type)
            
            result = await db_session.execute(query)
            events = result.scalars().all()
            
            # Parse JSON payloads
            parsed_events = []
            for event in events:
                parsed_events.append({
                    'id': event.id,
                    'trade_id': event.trade_id,
                    'event_type': event.event_type,
                    'payload': json.loads(event.payload),
                    'created_at': event.created_at
                })
            
            return parsed_events
            
        except Exception as e:
            logger.error(f"Failed to retrieve recent events: {e}")
            return []
    
    async def replay_events_for_trade(
        self,
        trade_id: str,
        db_session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Replay all events for a trade to reconstruct its state.
        
        This is useful for:
        - Recovering from crashes
        - Debugging complex trade scenarios
        - Verifying state consistency
        
        Args:
            trade_id: Trade ID to replay
            db_session: Database session
        
        Returns:
            List of events in chronological order
        """
        events = await self.get_events_for_trade(trade_id, db_session)
        
        logger.info(f"🔄 Replaying {len(events)} events for trade {trade_id}")
        
        # Events are already sorted by created_at
        for event in events:
            logger.debug(
                f"  [{event['created_at']}] {event['event_type']}"
            )
        
        return events
    
    def _generate_id(self) -> str:
        """Generate unique ID for event."""
        import uuid
        return str(uuid.uuid4())


# Global event store instance
event_store = EventStore()
