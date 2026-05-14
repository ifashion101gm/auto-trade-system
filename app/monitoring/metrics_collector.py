"""
Collects and exposes system performance metrics.
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from collections import defaultdict
from app.logging_config import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Tracks trading system metrics for monitoring and debugging."""
    
    def __init__(self):
        self.metrics = {
            'signals_generated': 0,
            'orders_executed': 0,
            'orders_rejected': 0,
            'fills_successful': 0,
            'fills_failed': 0,
            'reconciliation_mismatches': 0,
            'api_latency_ms': [],
            'exceptions_count': 0,
            'last_signal_time': None,
            'last_order_time': None,
            'cycle_times_ms': []
        }
        self.daily_metrics = defaultdict(lambda: defaultdict(int))
    
    def record_signal(self):
        """Record signal generation."""
        self.metrics['signals_generated'] += 1
        self.metrics['last_signal_time'] = datetime.utcnow()
        today = datetime.utcnow().strftime('%Y-%m-%d')
        self.daily_metrics[today]['signals'] += 1
    
    def record_order_execution(self, success: bool):
        """Record order execution attempt."""
        if success:
            self.metrics['orders_executed'] += 1
            self.metrics['fills_successful'] += 1
        else:
            self.metrics['orders_rejected'] += 1
            self.metrics['fills_failed'] += 1
        self.metrics['last_order_time'] = datetime.utcnow()
        today = datetime.utcnow().strftime('%Y-%m-%d')
        self.daily_metrics[today]['orders'] += 1
    
    def record_api_latency(self, latency_ms: float):
        """Record API call latency."""
        self.metrics['api_latency_ms'].append(latency_ms)
        # Keep only last 100 measurements
        if len(self.metrics['api_latency_ms']) > 100:
            self.metrics['api_latency_ms'] = self.metrics['api_latency_ms'][-100:]
    
    def record_reconciliation_mismatch(self):
        """Record reconciliation mismatch."""
        self.metrics['reconciliation_mismatches'] += 1
    
    def record_exception(self):
        """Record exception occurrence."""
        self.metrics['exceptions_count'] += 1
    
    def record_cycle_time(self, cycle_time_ms: float):
        """Record trading cycle duration."""
        self.metrics['cycle_times_ms'].append(cycle_time_ms)
        if len(self.metrics['cycle_times_ms']) > 100:
            self.metrics['cycle_times_ms'] = self.metrics['cycle_times_ms'][-100:]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get current metrics summary."""
        avg_latency = (
            sum(self.metrics['api_latency_ms']) / len(self.metrics['api_latency_ms'])
            if self.metrics['api_latency_ms'] else 0
        )
        
        avg_cycle_time = (
            sum(self.metrics['cycle_times_ms']) / len(self.metrics['cycle_times_ms'])
            if self.metrics['cycle_times_ms'] else 0
        )
        
        total_orders = self.metrics['orders_executed'] + self.metrics['orders_rejected']
        fill_rate = (
            self.metrics['orders_executed'] / total_orders * 100
            if total_orders > 0 else 0
        )
        
        today = datetime.utcnow().strftime('%Y-%m-%d')
        today_signals = self.daily_metrics[today]['signals']
        today_orders = self.daily_metrics[today]['orders']
        
        return {
            'signals_today': today_signals,
            'orders_today': today_orders,
            'fill_success_rate_pct': round(fill_rate, 2),
            'avg_api_latency_ms': round(avg_latency, 2),
            'avg_cycle_time_ms': round(avg_cycle_time, 2),
            'reconciliation_mismatches': self.metrics['reconciliation_mismatches'],
            'exceptions_count': self.metrics['exceptions_count'],
            'total_signals': self.metrics['signals_generated'],
            'total_orders': total_orders,
            'last_signal': self.metrics['last_signal_time'].isoformat() if self.metrics['last_signal_time'] else None,
            'last_order': self.metrics['last_order_time'].isoformat() if self.metrics['last_order_time'] else None,
            'targets': {
                'signals_per_day': '> 10',
                'orders_per_day': '> 3',
                'fill_success_rate': '> 95%',
                'reconciliation_mismatch_rate': '< 1%',
                'api_latency': '< 500ms',
                'exception_rate': '< 0.1%'
            }
        }


# Global instance
metrics_collector = MetricsCollector()
