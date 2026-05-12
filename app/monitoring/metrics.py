"""
Monitoring module - Metrics and observability.
Extracted from main.py for centralized monitoring.
"""
from prometheus_client import Counter, Histogram

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency'
)

WEBSOCKET_CONNECTED = Counter(
    'websocket_connected',
    'WebSocket connection status (1=connected, 0=disconnected)'
)

EVENT_BUS_QUEUE_SIZE = Histogram(
    'event_bus_queue_size',
    'Event bus queue size'
)
