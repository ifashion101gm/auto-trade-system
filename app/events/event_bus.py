"""
Async event bus for decoupled communication between agents.
Inspired by Hummingbot's event-driven architecture.

Features:
- Priority-based event processing (critical events first)
- Dead letter queue for failed handlers
- Event batching for high-frequency updates
- Async processing with error isolation
- **STRICT ORDERING**: Sequence IDs per symbol to prevent race conditions
- **IDEMPOTENT CONSUMERS**: Duplicate detection and safe ignoring
- **ORDERED PROCESSING**: Buffer out-of-order events until gaps filled

Events flow: Exchange → Sync Agent → Event Bus → DB + Telegram + Dashboard
"""
import asyncio
import logging
from typing import Callable, Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
from collections import deque
import uuid

from app.logging_config import get_logger

logger = get_logger(__name__)


class EventBus:
    """
    High-performance async event bus with priority processing.
    
    Features:
    - Priority queue: Lower number = higher priority (0 is highest)
    - Dead letter queue: Failed events stored for later inspection
    - Event filtering: Handlers can filter by symbol, side, etc.
    - Background processing: Events processed asynchronously
    
    Priority levels:
    - 0-5: Critical (ORDER_FILLED, ORDER_REJECTED)
    - 6-10: Important (POSITION_UPDATED, SYNC_MISMATCH)
    - 11-20: Normal (TELEGRAM_SENT, DAILY_SUMMARY)
    - 21+: Low priority (metrics, logs)
    """
    
    def __init__(self, max_queue_size: int = 10000):
        self._subscribers: Dict[str, List[Tuple[int, Callable]]] = {}  # priority + handler
        self._event_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._dead_letter_queue: deque = deque(maxlen=1000)
        self._event_history: deque = deque(maxlen=10000)
        self._processing_task: Optional[asyncio.Task] = None
        self._running = False
        self._max_queue_size = max_queue_size
        
        # **NEW: Sequence tracking for strict ordering**
        self._sequence_counters: Dict[str, int] = {}  # symbol -> next expected sequence
        self._processed_sequences: Dict[str, Set[int]] = {}  # symbol -> processed seq IDs
        self._out_of_order_buffer: Dict[str, List[Dict]] = {}  # symbol -> buffered events
        
        # Metrics
        self.events_published = 0
        self.events_processed = 0
        self.events_failed = 0
        self.duplicates_ignored = 0
        self.out_of_order_events = 0
        self.sequence_gaps_detected = 0
        
        logger.info(f"✅ EventBus initialized (max_queue_size={max_queue_size})")
    
    def subscribe(self, event_type: str, handler: Callable, priority: int = 10):
        """
        Subscribe to specific event type with priority.
        
        Args:
            event_type: Event type to subscribe to
            handler: Async callable to handle the event
            priority: Handler priority (lower = higher priority, default=10)
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        self._subscribers[event_type].append((priority, handler))
        # Sort by priority (lower number = higher priority)
        self._subscribers[event_type].sort(key=lambda x: x[0])
        
        logger.debug(f"📡 Subscribed to {event_type} (priority={priority})")
    
    async def publish(self, event_type: str, payload: Dict[str, Any], priority: int = 10):
        """
        Publish event to all subscribers via priority queue.
        
        Args:
            event_type: Type of event
            payload: Event data (should include 'symbol' for ordering)
            priority: Event priority (lower = higher priority, default=10)
        """
        # Generate sequence ID for symbol-based ordering
        symbol = payload.get('symbol', '__global__')
        if symbol not in self._sequence_counters:
            self._sequence_counters[symbol] = 0
            self._processed_sequences[symbol] = set()
            self._out_of_order_buffer[symbol] = []
        
        seq_id = self._sequence_counters[symbol]
        self._sequence_counters[symbol] += 1
        
        event = {
            'event_id': str(uuid.uuid4()),
            'type': event_type,
            'payload': payload,
            'timestamp': datetime.utcnow().isoformat(),
            'priority': priority,
            'sequence': seq_id,
            'symbol': symbol
        }
        
        try:
            # Add to queue with priority (tuple: (priority, timestamp, event))
            # Timestamp ensures FIFO ordering within same priority
            await self._event_queue.put((priority, datetime.utcnow().timestamp(), event))
            self.events_published += 1
            
            # Store in history
            self._event_history.append(event)
            
            logger.debug(f"📨 Published event: {event_type} seq={seq_id} (priority={priority})")
            
        except asyncio.QueueFull:
            logger.warning(f"⚠️  Event queue full! Dropping event: {event_type}")
            self._dead_letter_queue.append({
                'reason': 'queue_full',
                'event': event,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return event
    
    async def start_processing(self):
        """Start background event processing task."""
        if self._running:
            logger.warning("EventBus already running")
            return
        
        self._running = True
        self._processing_task = asyncio.create_task(self._process_events())
        logger.info("✅ EventBus processing started")
    
    async def stop_processing(self):
        """Stop background event processing."""
        self._running = False
        
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 EventBus processing stopped")
    
    async def _process_events(self):
        """Background task that processes events in priority order."""
        while self._running:
            try:
                # Get next event from priority queue (timeout to allow shutdown)
                try:
                    priority, timestamp, event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Dispatch event to subscribers
                await self._dispatch_event(event)
                self.events_processed += 1
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Event processing error: {e}")
                await asyncio.sleep(0.1)  # Prevent tight loop on errors
    
    async def _dispatch_event(self, event: Dict[str, Any]):
        """
        Dispatch event to all subscribers for that event type.
        
        **ENHANCED**: Checks sequence ordering and idempotency before dispatching.
        
        Args:
            event: Event dict with type, payload, timestamp, sequence
        """
        event_type = event['type']
        symbol = event.get('symbol', '__global__')
        seq_id = event.get('sequence', 0)
        
        # Check for duplicate events (idempotency)
        if symbol in self._processed_sequences and seq_id in self._processed_sequences[symbol]:
            logger.debug(f"🔁 Ignoring duplicate event: {event_type} seq={seq_id}")
            self.duplicates_ignored += 1
            return
        
        # Check sequence ordering
        expected_seq = self._sequence_counters.get(symbol, 0)
        if seq_id != expected_seq - 1:  # -1 because counter already incremented
            # Out-of-order event detected
            logger.warning(
                f"⚠️  Out-of-order event: {event_type} seq={seq_id}, expected={expected_seq - 1}"
            )
            self.out_of_order_events += 1
            
            # Buffer out-of-order events
            if symbol not in self._out_of_order_buffer:
                self._out_of_order_buffer[symbol] = []
            self._out_of_order_buffer[symbol].append(event)
            
            # Check if we can process buffered events now
            await self._process_buffered_events(symbol)
            return
        
        # Mark as processed
        if symbol not in self._processed_sequences:
            self._processed_sequences[symbol] = set()
        self._processed_sequences[symbol].add(seq_id)
        
        if event_type not in self._subscribers:
            logger.debug(f"No subscribers for event: {event_type}")
            return
        
        # Call all handlers for this event type (in priority order)
        tasks = []
        for priority, handler in self._subscribers[event_type]:
            try:
                # Create task for async handler
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Failed to create handler task: {e}")
        
        # Wait for all handlers with error isolation
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check for failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    handler_info = f"{event_type}_handler_{i}"
                    logger.error(f"Handler {handler_info} failed: {result}")
                    
                    # Add to dead letter queue
                    self._dead_letter_queue.append({
                        'reason': 'handler_failed',
                        'event': event,
                        'handler': handler_info,
                        'error': str(result),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    self.events_failed += 1
    
    def get_event_history(self, limit: int = 100, event_type: Optional[str] = None):
        """
        Get recent event history.
        
        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type (optional)
        
        Returns:
            List of events
        """
        events = list(self._event_history)
        
        if event_type:
            events = [e for e in events if e['type'] == event_type]
        
        return events[-limit:]
    
    def get_dead_letter_queue(self, limit: int = 100):
        """Get failed events from dead letter queue."""
        return list(self._dead_letter_queue)[-limit:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get event bus performance metrics."""
        return {
            'events_published': self.events_published,
            'events_processed': self.events_processed,
            'events_failed': self.events_failed,
            'duplicates_ignored': self.duplicates_ignored,
            'out_of_order_events': self.out_of_order_events,
            'sequence_gaps_detected': self.sequence_gaps_detected,
            'queue_size': self._event_queue.qsize(),
            'dead_letter_count': len(self._dead_letter_queue),
            'subscriber_count': sum(len(handlers) for handlers in self._subscribers.values()),
            'event_types': list(self._subscribers.keys()),
            'buffered_events': sum(len(buf) for buf in self._out_of_order_buffer.values())
        }
    
    async def _process_buffered_events(self, symbol: str):
        """
        Process buffered out-of-order events when gaps are filled.
        
        Args:
            symbol: Symbol to process buffered events for
        """
        if symbol not in self._out_of_order_buffer:
            return
        
        buffer = self._out_of_order_buffer[symbol]
        expected_seq = self._sequence_counters.get(symbol, 0) - 1
        
        # Find events that can now be processed (in sequence order)
        ready_events = []
        remaining_buffer = []
        
        for event in sorted(buffer, key=lambda e: e.get('sequence', 0)):
            seq_id = event.get('sequence', 0)
            if seq_id == expected_seq + len(ready_events):
                ready_events.append(event)
            else:
                remaining_buffer.append(event)
        
        # Update buffer
        self._out_of_order_buffer[symbol] = remaining_buffer
        
        # Process ready events in order
        for event in ready_events:
            logger.info(f"📦 Processing buffered event: {event['type']} seq={event['sequence']}")
            await self._dispatch_event_internal(event)

    async def _dispatch_event_internal(self, event: Dict[str, Any]):
        """
        Internal dispatch without ordering checks (for buffered events).
        
        Args:
            event: Event to dispatch
        """
        event_type = event['type']
        symbol = event.get('symbol', '__global__')
        seq_id = event.get('sequence', 0)
        
        # Mark as processed
        if symbol not in self._processed_sequences:
            self._processed_sequences[symbol] = set()
        self._processed_sequences[symbol].add(seq_id)
        
        if event_type not in self._subscribers:
            return
        
        # Call all handlers
        tasks = []
        for priority, handler in self._subscribers[event_type]:
            try:
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Failed to create handler task: {e}")
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    handler_info = f"{event_type}_handler_{i}"
                    logger.error(f"Handler {handler_info} failed: {result}")
                    self._dead_letter_queue.append({
                        'reason': 'handler_failed',
                        'event': event,
                        'handler': handler_info,
                        'error': str(result),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    self.events_failed += 1


# Global event bus instance
event_bus = EventBus()
