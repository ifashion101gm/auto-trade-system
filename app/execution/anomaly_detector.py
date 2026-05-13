"""
AI Anomaly Detector for Trading System.

Monitors system behavior patterns and detects anomalies that may indicate:
- Unusual API latency spikes
- Repeated order failures
- Abnormal slippage patterns
- Overtrading behavior
- Market regime changes

Uses statistical analysis to identify deviations from normal behavior.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detects anomalous patterns in trading system behavior.
    
    Monitors:
    - API latency patterns
    - Order failure rates
    - Slippage distributions
    - Trade frequency (overtrading)
    - Position concentration
    
    Triggers alerts when metrics deviate significantly from baseline.
    """
    
    def __init__(
        self,
        window_size: int = 100,           # Number of samples for baseline
        latency_threshold_std: float = 3.0,  # Std devs for latency anomaly
        failure_rate_threshold: float = 0.3, # 30% failure rate triggers alert
        slippage_threshold_std: float = 2.5, # Std devs for slippage anomaly
        max_trades_per_hour: int = 20,    # Overtrading threshold
        cooldown_seconds: int = 300       # Alert cooldown (5 min)
    ):
        """
        Initialize anomaly detector.
        
        Args:
            window_size: Samples to maintain for baseline calculation
            latency_threshold_std: Standard deviations for latency anomaly
            failure_rate_threshold: Failure rate that triggers alert
            slippage_threshold_std: Standard deviations for slippage anomaly
            max_trades_per_hour: Maximum trades per hour before overtrading alert
            cooldown_seconds: Minimum time between alerts
        """
        self.window_size = window_size
        self.latency_threshold_std = latency_threshold_std
        self.failure_rate_threshold = failure_rate_threshold
        self.slippage_threshold_std = slippage_threshold_std
        self.max_trades_per_hour = max_trades_per_hour
        self.cooldown_seconds = cooldown_seconds
        
        # Data windows for rolling statistics
        self.latencies: deque = deque(maxlen=window_size)
        self.slippages: deque = deque(maxlen=window_size)
        self.order_results: deque = deque(maxlen=window_size)  # True=success, False=failure
        self.trade_timestamps: deque = deque(maxlen=window_size * 2)
        
        # Alert tracking
        self.last_alert_time: Dict[str, datetime] = {}
        self.alert_counts: Dict[str, int] = {}
        
        self.logger = logging.getLogger("anomaly_detector")
    
    def record_latency(self, latency_ms: float):
        """
        Record API latency measurement.
        
        Args:
            latency_ms: Latency in milliseconds
        """
        self.latencies.append(latency_ms)
        self.logger.debug(f"Recorded latency: {latency_ms:.0f}ms")
    
    def record_slippage(self, slippage_pct: float):
        """
        Record trade slippage percentage.
        
        Args:
            slippage_pct: Slippage as percentage
        """
        self.slippages.append(slippage_pct)
        self.logger.debug(f"Recorded slippage: {slippage_pct:.2f}%")
    
    def record_order_result(self, success: bool):
        """
        Record order execution result.
        
        Args:
            success: True if order succeeded, False if failed
        """
        self.order_results.append(success)
        self.logger.debug(f"Recorded order result: {'success' if success else 'failure'}")
    
    def record_trade(self, symbol: str, side: str):
        """
        Record trade execution for overtrading detection.
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
        """
        self.trade_timestamps.append({
            'timestamp': datetime.utcnow(),
            'symbol': symbol,
            'side': side
        })
    
    def detect_latency_anomaly(self, current_latency_ms: float) -> Optional[Dict[str, Any]]:
        """
        Detect if current latency is anomalous.
        
        Uses z-score method: flags values > N standard deviations from mean.
        
        Args:
            current_latency_ms: Current latency measurement
            
        Returns:
            Anomaly details dict if detected, None otherwise
        """
        if len(self.latencies) < 10:
            return None  # Not enough data for baseline
        
        mean_latency = statistics.mean(self.latencies)
        std_latency = statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
        
        if std_latency == 0:
            return None
        
        # Calculate z-score
        z_score = abs(current_latency_ms - mean_latency) / std_latency
        
        if z_score > self.latency_threshold_std:
            anomaly = {
                'type': 'latency_spike',
                'severity': 'HIGH' if z_score > 4.0 else 'MEDIUM',
                'current_value': current_latency_ms,
                'baseline_mean': mean_latency,
                'baseline_std': std_latency,
                'z_score': z_score,
                'message': f"API latency spike: {current_latency_ms:.0f}ms "
                          f"(baseline: {mean_latency:.0f}±{std_latency:.0f}ms)"
            }
            
            return self._check_cooldown(anomaly)
        
        return None
    
    def detect_failure_rate_anomaly(self) -> Optional[Dict[str, Any]]:
        """
        Detect if order failure rate is abnormally high.
        
        Analyzes recent order results in sliding window.
        
        Returns:
            Anomaly details dict if detected, None otherwise
        """
        if len(self.order_results) < 20:
            return None  # Not enough data
        
        # Calculate failure rate in recent window
        recent_failures = sum(1 for result in self.order_results if not result)
        failure_rate = recent_failures / len(self.order_results)
        
        if failure_rate > self.failure_rate_threshold:
            anomaly = {
                'type': 'high_failure_rate',
                'severity': 'CRITICAL' if failure_rate > 0.5 else 'HIGH',
                'current_value': failure_rate,
                'threshold': self.failure_rate_threshold,
                'recent_failures': recent_failures,
                'total_orders': len(self.order_results),
                'message': f"High order failure rate: {failure_rate:.1%} "
                          f"({recent_failures}/{len(self.order_results)} orders failed)"
            }
            
            return self._check_cooldown(anomaly)
        
        return None
    
    def detect_slippage_anomaly(self, current_slippage_pct: float) -> Optional[Dict[str, Any]]:
        """
        Detect if current slippage is anomalous.
        
        Args:
            current_slippage_pct: Current slippage percentage
            
        Returns:
            Anomaly details dict if detected, None otherwise
        """
        if len(self.slippages) < 10:
            return None
        
        mean_slippage = statistics.mean(self.slippages)
        std_slippage = statistics.stdev(self.slippages) if len(self.slippages) > 1 else 0
        
        if std_slippage == 0:
            return None
        
        z_score = abs(current_slippage_pct - mean_slippage) / std_slippage
        
        if z_score > self.slippage_threshold_std:
            anomaly = {
                'type': 'slippage_spike',
                'severity': 'HIGH' if z_score > 3.5 else 'MEDIUM',
                'current_value': current_slippage_pct,
                'baseline_mean': mean_slippage,
                'baseline_std': std_slippage,
                'z_score': z_score,
                'message': f"Abnormal slippage: {current_slippage_pct:.2f}% "
                          f"(baseline: {mean_slippage:.2f}%±{std_slippage:.2f}%)"
            }
            
            return self._check_cooldown(anomaly)
        
        return None
    
    def detect_overtrading(self) -> Optional[Dict[str, Any]]:
        """
        Detect if system is overtrading (too many trades in short period).
        
        Returns:
            Anomaly details dict if detected, None otherwise
        """
        if len(self.trade_timestamps) < 5:
            return None
        
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Count trades in last hour
        recent_trades = [
            t for t in self.trade_timestamps
            if isinstance(t, dict) and t['timestamp'] > one_hour_ago
        ]
        
        trade_count = len(recent_trades)
        
        if trade_count > self.max_trades_per_hour:
            anomaly = {
                'type': 'overtrading',
                'severity': 'HIGH' if trade_count > self.max_trades_per_hour * 1.5 else 'MEDIUM',
                'current_value': trade_count,
                'threshold': self.max_trades_per_hour,
                'period': '1 hour',
                'message': f"Overtrading detected: {trade_count} trades in last hour "
                          f"(threshold: {self.max_trades_per_hour})"
            }
            
            return self._check_cooldown(anomaly)
        
        return None
    
    def run_comprehensive_check(
        self,
        current_latency_ms: float = None,
        current_slippage_pct: float = None
    ) -> List[Dict[str, Any]]:
        """
        Run all anomaly detection checks.
        
        Args:
            current_latency_ms: Optional current latency to check
            current_slippage_pct: Optional current slippage to check
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Check latency anomaly
        if current_latency_ms is not None:
            latency_anomaly = self.detect_latency_anomaly(current_latency_ms)
            if latency_anomaly:
                anomalies.append(latency_anomaly)
        
        # Check failure rate anomaly
        failure_anomaly = self.detect_failure_rate_anomaly()
        if failure_anomaly:
            anomalies.append(failure_anomaly)
        
        # Check slippage anomaly
        if current_slippage_pct is not None:
            slippage_anomaly = self.detect_slippage_anomaly(current_slippage_pct)
            if slippage_anomaly:
                anomalies.append(slippage_anomaly)
        
        # Check overtrading
        overtrading_anomaly = self.detect_overtrading()
        if overtrading_anomaly:
            anomalies.append(overtrading_anomaly)
        
        if anomalies:
            self.logger.warning(f"⚠️ Detected {len(anomalies)} anomalies:")
            for anomaly in anomalies:
                self.logger.warning(f"  - [{anomaly['severity']}] {anomaly['message']}")
        
        return anomalies
    
    def _check_cooldown(self, anomaly: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if anomaly alert is in cooldown period.
        
        Args:
            anomaly: Anomaly dictionary
            
        Returns:
            Anomaly if should alert, None if in cooldown
        """
        anomaly_type = anomaly['type']
        now = datetime.utcnow()
        
        if anomaly_type in self.last_alert_time:
            time_since_last = (now - self.last_alert_time[anomaly_type]).total_seconds()
            
            if time_since_last < self.cooldown_seconds:
                self.logger.debug(
                    f"Suppressing {anomaly_type} alert (cooldown: "
                    f"{self.cooldown_seconds - time_since_last:.0f}s remaining)"
                )
                return None
        
        # Update alert tracking
        self.last_alert_time[anomaly_type] = now
        self.alert_counts[anomaly_type] = self.alert_counts.get(anomaly_type, 0) + 1
        
        anomaly['alert_count'] = self.alert_counts[anomaly_type]
        anomaly['timestamp'] = now.isoformat()
        
        return anomaly
    
    def get_baseline_stats(self) -> Dict[str, Any]:
        """
        Get current baseline statistics.
        
        Returns:
            Dictionary with baseline metrics
        """
        stats = {
            'samples_collected': {
                'latencies': len(self.latencies),
                'slippages': len(self.slippages),
                'order_results': len(self.order_results),
                'trades': len(self.trade_timestamps)
            }
        }
        
        if len(self.latencies) >= 10:
            stats['latency_baseline'] = {
                'mean_ms': statistics.mean(self.latencies),
                'std_ms': statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0,
                'min_ms': min(self.latencies),
                'max_ms': max(self.latencies)
            }
        
        if len(self.slippages) >= 10:
            stats['slippage_baseline'] = {
                'mean_pct': statistics.mean(self.slippages),
                'std_pct': statistics.stdev(self.slippages) if len(self.slippages) > 1 else 0,
                'min_pct': min(self.slippages),
                'max_pct': max(self.slippages)
            }
        
        if len(self.order_results) >= 20:
            failures = sum(1 for r in self.order_results if not r)
            stats['failure_rate'] = {
                'rate': failures / len(self.order_results),
                'failures': failures,
                'total': len(self.order_results)
            }
        
        # Recent trade count
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        recent_trades = [
            t for t in self.trade_timestamps
            if isinstance(t, dict) and t['timestamp'] > one_hour_ago
        ]
        stats['trades_last_hour'] = len(recent_trades)
        
        return stats
    
    def reset_baselines(self):
        """Reset all baselines (use after major system changes)."""
        self.latencies.clear()
        self.slippages.clear()
        self.order_results.clear()
        self.trade_timestamps.clear()
        self.last_alert_time.clear()
        self.alert_counts.clear()
        
        self.logger.info("Anomaly detector baselines reset")
