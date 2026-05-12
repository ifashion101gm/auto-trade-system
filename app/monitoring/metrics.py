"""
Monitoring module - Metrics and observability.
Extracted from main.py for centralized monitoring.
"""
from prometheus_client import Counter, Histogram, Gauge

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

# === Trading Performance Metrics ===

TRADE_EXECUTION_LATENCY = Histogram(
    'trade_execution_latency_ms',
    'Trade execution latency in milliseconds',
    ['exchange', 'symbol', 'side'],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
)

TRADE_SLIPPAGE = Histogram(
    'trade_slippage_percentage',
    'Trade slippage as percentage',
    ['exchange', 'symbol', 'side'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

FILL_RATE = Gauge(
    'fill_rate_percentage',
    'Order fill rate percentage',
    ['exchange', 'symbol']
)

PNL_PER_TRADE = Histogram(
    'pnl_per_trade_usd',
    'Profit/Loss per trade in USD',
    ['strategy', 'symbol', 'side'],
    buckets=[-100, -50, -25, -10, -5, 0, 5, 10, 25, 50, 100, 250, 500]
)

WIN_RATE = Gauge(
    'win_rate_percentage',
    'Win rate percentage (rolling)',
    ['strategy']
)

TOTAL_TRADES = Counter(
    'total_trades_count',
    'Total number of trades executed',
    ['exchange', 'symbol', 'side', 'result']  # result: win/loss
)

# === Reliability Metrics ===

WEBSOCKET_RECONNECT_COUNT = Counter(
    'websocket_reconnect_total',
    'Total WebSocket reconnection attempts',
    ['exchange']
)

API_FAILURE_COUNT = Counter(
    'api_failure_total',
    'Total API call failures',
    ['exchange', 'endpoint', 'error_type']
)

WEBSOCKET_UPTIME_SECONDS = Gauge(
    'websocket_uptime_seconds',
    'WebSocket connection uptime in seconds',
    ['exchange']
)

ORDER_REJECTION_COUNT = Counter(
    'order_rejection_total',
    'Total order rejections',
    ['exchange', 'symbol', 'reason']
)

# === Data Integrity Metrics ===

DESYNC_COUNT = Counter(
    'desync_events_total',
    'Total synchronization mismatch events',
    ['exchange', 'symbol', 'mismatch_type']
)

RECONCILIATION_ACTIONS = Counter(
    'reconciliation_actions_total',
    'Total reconciliation actions taken',
    ['exchange', 'action_type', 'requires_review']
)

POSITION_SYNC_LATENCY = Histogram(
    'position_sync_latency_ms',
    'Position synchronization latency',
    ['exchange'],
    buckets=[10, 25, 50, 100, 250, 500, 1000]
)

# === Risk Management Metrics ===

RISK_VIOLATIONS = Counter(
    'risk_violations_total',
    'Total risk limit violations',
    ['violation_type', 'risk_level']
)

DAILY_DRAWDOWN_PCT = Gauge(
    'daily_drawdown_percentage',
    'Current daily drawdown percentage',
    ['user_id']
)

CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=half-open, 2=open)',
    ['component']
)
