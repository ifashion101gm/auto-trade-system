"""
Prometheus metrics exporter for trading system observability.

Exposes key trading metrics in Prometheus format for scraping by Prometheus server.
Metrics are then visualized in Grafana dashboards and used for alerting.

Metrics Exposed:
- trading_orders_total: Total orders executed (counter)
- trading_latency_seconds: Order execution latency (histogram)
- trading_positions_open: Currently open positions (gauge)
- trading_pnl_total: Total realized P&L (gauge)
- trading_signals_total: Trading signals generated (counter)
- system_api_calls_total: API calls to exchanges (counter)
- system_errors_total: System errors encountered (counter)
- reconciliation_mismatches: Position sync mismatches (gauge)

Usage:
    from app.monitoring.prometheus_metrics import metrics_registry
    
    # In FastAPI app
    from prometheus_client import make_asgi_app
    app.mount("/metrics", make_asgi_app())
"""
import logging
from typing import Dict, Any, Optional
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)


class TradingMetricsCollector:
    """
    Centralized Prometheus metrics collector for trading system.
    
    All metrics flow through this class for consistent naming and labeling.
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector with custom or default registry.
        
        Args:
            registry: Prometheus CollectorRegistry (uses default if None)
        """
        self.registry = registry or CollectorRegistry()
        
        # ====================================================================
        # Trading Execution Metrics
        # ====================================================================
        
        self.orders_total = Counter(
            'trading_orders_total',
            'Total number of orders executed',
            ['exchange', 'symbol', 'side', 'status'],
            registry=self.registry
        )
        
        self.order_latency = Histogram(
            'trading_order_latency_seconds',
            'Order execution latency in seconds',
            ['exchange', 'symbol'],
            buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry
        )
        
        self.positions_open = Gauge(
            'trading_positions_open',
            'Number of currently open positions',
            ['exchange', 'symbol'],
            registry=self.registry
        )
        
        self.position_size_usd = Gauge(
            'trading_position_size_usd',
            'Current position size in USD',
            ['exchange', 'symbol', 'side'],
            registry=self.registry
        )
        
        # ====================================================================
        # P&L Metrics
        # ====================================================================
        
        self.pnl_realized = Gauge(
            'trading_pnl_realized_usd',
            'Realized P&L in USD',
            ['exchange', 'symbol', 'strategy'],
            registry=self.registry
        )
        
        self.pnl_unrealized = Gauge(
            'trading_pnl_unrealized_usd',
            'Unrealized P&L in USD',
            ['exchange', 'symbol'],
            registry=self.registry
        )
        
        self.win_rate = Gauge(
            'trading_win_rate',
            'Win rate percentage (0-100)',
            ['exchange', 'strategy'],
            registry=self.registry
        )
        
        # ====================================================================
        # Signal Metrics
        # ====================================================================
        
        self.signals_total = Counter(
            'trading_signals_total',
            'Total trading signals generated',
            ['strategy', 'symbol', 'side', 'action'],  # action: executed/rejected
            registry=self.registry
        )
        
        self.signal_rejection_reasons = Counter(
            'trading_signal_rejections_total',
            'Total signal rejections by reason',
            ['reason', 'strategy'],
            registry=self.registry
        )
        
        # ====================================================================
        # System Health Metrics
        # ====================================================================
        
        self.api_calls_total = Counter(
            'system_api_calls_total',
            'Total API calls to exchanges',
            ['exchange', 'endpoint', 'status'],  # status: success/failure
            registry=self.registry
        )
        
        self.api_latency = Histogram(
            'system_api_latency_seconds',
            'API call latency in seconds',
            ['exchange', 'endpoint'],
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self.registry
        )
        
        self.errors_total = Counter(
            'system_errors_total',
            'Total system errors encountered',
            ['error_type', 'component'],
            registry=self.registry
        )
        
        self.circuit_breaker_state = Gauge(
            'system_circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=open)',
            ['exchange'],
            registry=self.registry
        )
        
        # ====================================================================
        # Reconciliation Metrics
        # ====================================================================
        
        self.reconciliation_mismatches = Gauge(
            'reconciliation_mismatches_total',
            'Number of position mismatches detected',
            ['type'],  # type: ghost/orphaned/status_diff
            registry=self.registry
        )
        
        self.reconciliation_repairs = Counter(
            'reconciliation_repairs_total',
            'Total position repairs performed',
            ['type'],
            registry=self.registry
        )
        
        # ====================================================================
        # Watchdog Metrics
        # ====================================================================
        
        self.watchdog_alerts = Counter(
            'watchdog_alerts_total',
            'Total watchdog alerts triggered',
            ['watchdog_type', 'severity'],
            registry=self.registry
        )
        
        self.watchdog_state = Gauge(
            'watchdog_system_health',
            'Watchdog system health score (0-1)',
            ['watchdog_type'],
            registry=self.registry
        )
        
        logger.info("✅ Prometheus metrics collector initialized")
    
    # ========================================================================
    # Trading Execution Methods
    # ========================================================================
    
    def record_order_executed(
        self,
        exchange: str,
        symbol: str,
        side: str,
        latency_seconds: float,
        status: str = 'success',
    ):
        """Record successful order execution."""
        self.orders_total.labels(
            exchange=exchange,
            symbol=symbol,
            side=side,
            status=status
        ).inc()
        
        self.order_latency.labels(
            exchange=exchange,
            symbol=symbol
        ).observe(latency_seconds)
    
    def record_order_failed(
        self,
        exchange: str,
        symbol: str,
        side: str,
    ):
        """Record failed order execution."""
        self.orders_total.labels(
            exchange=exchange,
            symbol=symbol,
            side=side,
            status='failed'
        ).inc()
    
    def update_open_positions(
        self,
        exchange: str,
        symbol: str,
        count: int,
    ):
        """Update gauge for open positions count."""
        self.positions_open.labels(
            exchange=exchange,
            symbol=symbol
        ).set(count)
    
    def update_position_size(
        self,
        exchange: str,
        symbol: str,
        side: str,
        size_usd: float,
    ):
        """Update gauge for position size."""
        self.position_size_usd.labels(
            exchange=exchange,
            symbol=symbol,
            side=side
        ).set(size_usd)
    
    # ========================================================================
    # P&L Methods
    # ========================================================================
    
    def update_realized_pnl(
        self,
        exchange: str,
        symbol: str,
        strategy: str,
        pnl_usd: float,
    ):
        """Update realized P&L gauge."""
        self.pnl_realized.labels(
            exchange=exchange,
            symbol=symbol,
            strategy=strategy
        ).set(pnl_usd)
    
    def update_unrealized_pnl(
        self,
        exchange: str,
        symbol: str,
        pnl_usd: float,
    ):
        """Update unrealized P&L gauge."""
        self.pnl_unrealized.labels(
            exchange=exchange,
            symbol=symbol
        ).set(pnl_usd)
    
    def update_win_rate(
        self,
        exchange: str,
        strategy: str,
        win_rate_pct: float,
    ):
        """Update win rate gauge."""
        self.win_rate.labels(
            exchange=exchange,
            strategy=strategy
        ).set(win_rate_pct)
    
    # ========================================================================
    # Signal Methods
    # ========================================================================
    
    def record_signal_generated(
        self,
        strategy: str,
        symbol: str,
        side: str,
        executed: bool = True,
    ):
        """Record trading signal generation."""
        action = 'executed' if executed else 'rejected'
        
        self.signals_total.labels(
            strategy=strategy,
            symbol=symbol,
            side=side,
            action=action
        ).inc()
    
    def record_signal_rejected(
        self,
        reason: str,
        strategy: str,
    ):
        """Record signal rejection with reason."""
        self.signal_rejection_reasons.labels(
            reason=reason,
            strategy=strategy
        ).inc()
    
    # ========================================================================
    # System Health Methods
    # ========================================================================
    
    def record_api_call(
        self,
        exchange: str,
        endpoint: str,
        latency_seconds: float,
        success: bool = True,
    ):
        """Record API call to exchange."""
        status = 'success' if success else 'failure'
        
        self.api_calls_total.labels(
            exchange=exchange,
            endpoint=endpoint,
            status=status
        ).inc()
        
        self.api_latency.labels(
            exchange=exchange,
            endpoint=endpoint
        ).observe(latency_seconds)
    
    def record_error(
        self,
        error_type: str,
        component: str,
    ):
        """Record system error."""
        self.errors_total.labels(
            error_type=error_type,
            component=component
        ).inc()
    
    def update_circuit_breaker(
        self,
        exchange: str,
        is_open: bool,
    ):
        """Update circuit breaker state gauge."""
        self.circuit_breaker_state.labels(
            exchange=exchange
        ).set(1 if is_open else 0)
    
    # ========================================================================
    # Reconciliation Methods
    # ========================================================================
    
    def update_reconciliation_mismatches(
        self,
        mismatch_type: str,
        count: int,
    ):
        """Update reconciliation mismatch gauge."""
        self.reconciliation_mismatches.labels(
            type=mismatch_type
        ).set(count)
    
    def record_reconciliation_repair(
        self,
        repair_type: str,
    ):
        """Record reconciliation repair."""
        self.reconciliation_repairs.labels(
            type=repair_type
        ).inc()
    
    # ========================================================================
    # Watchdog Methods
    # ========================================================================
    
    def record_watchdog_alert(
        self,
        watchdog_type: str,
        severity: str,
    ):
        """Record watchdog alert."""
        self.watchdog_alerts.labels(
            watchdog_type=watchdog_type,
            severity=severity
        ).inc()
    
    def update_watchdog_health(
        self,
        watchdog_type: str,
        health_score: float,
    ):
        """Update watchdog health score (0-1)."""
        self.watchdog_state.labels(
            watchdog_type=watchdog_type
        ).set(health_score)
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def get_metrics(self) -> bytes:
        """Get all metrics in Prometheus exposition format."""
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        """Get Prometheus content type."""
        return CONTENT_TYPE_LATEST


# ============================================================================
# Global Metrics Instance
# ============================================================================

# Create a single global instance for the application
metrics_collector = TradingMetricsCollector()


def get_metrics_collector() -> TradingMetricsCollector:
    """Get the global metrics collector instance."""
    return metrics_collector
