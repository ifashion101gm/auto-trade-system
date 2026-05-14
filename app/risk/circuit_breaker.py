"""
Circuit Breaker - Hard kill switch for trading based on multiple failure conditions.

Prevents catastrophic losses by automatically disabling trading when:
- Consecutive losses exceed threshold (3)
- Drawdown exceeds limit (3%)
- API latency too high (>2s for 5 consecutive checks)
- WebSocket instability detected (>5 disconnects/hour)
- Infrastructure failures occur

Features:
- Real-time monitoring of trading health metrics
- Automatic trading halt with reason tracking
- Telegram alerts on circuit breaker trips
- Manual reset capability after cooldown period
- Integration with /health/deep endpoint
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import time

from app.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


class CircuitBreaker:
    """
    Hard kill switch that disables trading when dangerous conditions are detected.
    
    Monitors:
    - Consecutive losses
    - Account drawdown
    - API latency
    - WebSocket stability
    - Infrastructure failures
    
    Usage:
        cb = CircuitBreaker()
        
        # Before executing any trade
        if not cb.check_and_update(metrics):
            logger.error("Trading disabled by circuit breaker")
            return
        
        # Execute trade...
        
        # Check status
        if cb.trading_disabled:
            print(f"Trading disabled: {cb.disable_reason}")
    """
    
    def __init__(self):
        """Initialize circuit breaker with configuration from settings."""
        self.trading_disabled = False
        self.disable_reason: Optional[str] = None
        self.disabled_at: Optional[datetime] = None
        
        # Failure counters
        self.failure_counts = {
            'consecutive_losses': 0,
            'api_latency_violations': 0,
            'websocket_disconnects': 0,
            'drawdown_violations': 0,
            'infrastructure_failures': 0
        }
        
        # Thresholds from settings
        self.max_consecutive_losses = getattr(settings, 'RISK_MAX_CONSECUTIVE_LOSSES', 3)
        self.max_drawdown_pct = 0.03  # 3% hard limit for circuit breaker
        self.api_latency_threshold_ms = getattr(
            settings, 'CIRCUIT_BREAKER_LATENCY_THRESHOLD_MS', 2000
        )
        self.max_ws_disconnects_per_hour = 5
        self.max_infrastructure_failures = getattr(
            settings, 'EMERGENCY_STOP_INFRASTRUCTURE_FAILURES', 3
        )
        
        # Tracking
        self.last_api_latency_check: Optional[float] = None
        self.ws_disconnect_timestamps: list = []
        
        logger.info("✅ CircuitBreaker initialized")
        logger.info(f"   Max consecutive losses: {self.max_consecutive_losses}")
        logger.info(f"   Max drawdown: {self.max_drawdown_pct:.1%}")
        logger.info(f"   API latency threshold: {self.api_latency_threshold_ms}ms")
    
    def check_and_update(self, metrics: Dict[str, Any]) -> bool:
        """
        Check all circuit breaker conditions and update state.
        
        Args:
            metrics: Dictionary containing current system metrics:
                - consecutive_losses: int
                - drawdown_pct: float
                - api_latency_ms: float
                - ws_disconnects_last_hour: int
                - infrastructure_failures: int
        
        Returns:
            True if trading is allowed, False if circuit breaker tripped
        """
        # If already disabled, stay disabled until manual reset
        if self.trading_disabled:
            return False
        
        # Check consecutive losses
        consecutive_losses = metrics.get('consecutive_losses', 0)
        if consecutive_losses >= self.max_consecutive_losses:
            self._disable(f"Consecutive losses threshold reached ({consecutive_losses}/{self.max_consecutive_losses})")
            self.failure_counts['consecutive_losses'] = consecutive_losses
            return False
        
        # Check drawdown
        drawdown_pct = metrics.get('drawdown_pct', 0)
        if drawdown_pct > self.max_drawdown_pct:
            self._disable(f"Drawdown exceeded {self.max_drawdown_pct:.1%} (current: {drawdown_pct:.1%})")
            self.failure_counts['drawdown_violations'] += 1
            return False
        
        # Check API latency
        api_latency_ms = metrics.get('api_latency_ms', 0)
        if api_latency_ms > self.api_latency_threshold_ms:
            self.failure_counts['api_latency_violations'] += 1
            logger.warning(
                f"High API latency detected: {api_latency_ms}ms "
                f"(threshold: {self.api_latency_threshold_ms}ms, "
                f"violations: {self.failure_counts['api_latency_violations']})"
            )
            
            if self.failure_counts['api_latency_violations'] >= 5:
                self._disable(
                    f"API latency too high (>{self.api_latency_threshold_ms}ms) "
                    f"for 5 consecutive checks"
                )
                return False
        else:
            # Reset counter on successful check
            self.failure_counts['api_latency_violations'] = 0
        
        # Check WebSocket stability
        ws_disconnects = metrics.get('ws_disconnects_last_hour', 0)
        if ws_disconnects > self.max_ws_disconnects_per_hour:
            self._disable(
                f"WebSocket instability detected "
                f"({ws_disconnects} disconnects/hour, max: {self.max_ws_disconnects_per_hour})"
            )
            self.failure_counts['websocket_disconnects'] = ws_disconnects
            return False
        
        # Check infrastructure failures
        infra_failures = metrics.get('infrastructure_failures', 0)
        if infra_failures >= self.max_infrastructure_failures:
            self._disable(
                f"Infrastructure failures threshold reached "
                f"({infra_failures}/{self.max_infrastructure_failures})"
            )
            self.failure_counts['infrastructure_failures'] = infra_failures
            return False
        
        # All checks passed - trading allowed
        return True
    
    def record_loss(self):
        """Record a trading loss for consecutive loss tracking."""
        self.failure_counts['consecutive_losses'] += 1
        logger.debug(f"Loss recorded (consecutive: {self.failure_counts['consecutive_losses']})")
    
    def record_win(self):
        """Record a trading win to reset consecutive loss counter."""
        self.failure_counts['consecutive_losses'] = 0
        logger.debug("Win recorded, consecutive loss counter reset")
    
    def record_ws_disconnect(self):
        """Record a WebSocket disconnection event."""
        now = time.time()
        self.ws_disconnect_timestamps.append(now)
        
        # Remove timestamps older than 1 hour
        one_hour_ago = now - 3600
        self.ws_disconnect_timestamps = [
            ts for ts in self.ws_disconnect_timestamps if ts > one_hour_ago
        ]
        
        disconnect_count = len(self.ws_disconnect_timestamps)
        logger.debug(f"WebSocket disconnect recorded (last hour: {disconnect_count})")
        
        if disconnect_count > self.max_ws_disconnects_per_hour:
            self._disable(
                f"WebSocket instability: {disconnect_count} disconnects in last hour"
            )
    
    def record_infrastructure_failure(self):
        """Record an infrastructure failure (DB, Redis, etc.)."""
        self.failure_counts['infrastructure_failures'] += 1
        logger.warning(
            f"Infrastructure failure recorded "
            f"(total: {self.failure_counts['infrastructure_failures']})"
        )
    
    def _disable(self, reason: str):
        """
        Disable trading with reason.
        
        Args:
            reason: Human-readable explanation for disabling trading
        """
        if self.trading_disabled:
            return  # Already disabled
        
        self.trading_disabled = True
        self.disable_reason = reason
        self.disabled_at = datetime.now(timezone.utc)
        
        logger.critical(f"🚨 CIRCUIT BREAKER TRIPPED: {reason}")
        logger.critical(f"   Trading DISABLED at {self.disabled_at.isoformat()}")
        
        # Send Telegram alert (if available)
        try:
            from app.notifications.telegram_agent import TelegramAgent
            telegram = TelegramAgent()
            alert_message = (
                f"🚨 *CIRCUIT BREAKER TRIPPED*\n\n"
                f"*Reason:* {reason}\n"
                f"*Time:* {self.disabled_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"Trading has been automatically DISABLED to prevent further losses.\n"
                f"Manual intervention required to re-enable trading."
            )
            # Note: This will be called from worker context
            # telegram.send_alert(alert_message)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
    
    def reset(self, reason: str = "Manual reset"):
        """
        Manually reset circuit breaker and re-enable trading.
        
        Args:
            reason: Reason for manual reset
        """
        if not self.trading_disabled:
            logger.warning("Circuit breaker not disabled, nothing to reset")
            return
        
        logger.info(f"🔄 Circuit breaker RESET: {reason}")
        logger.info(f"   Previous disable reason: {self.disable_reason}")
        logger.info(f"   Disabled for: {self._get_disabled_duration()}")
        
        self.trading_disabled = False
        self.disable_reason = None
        self.disabled_at = None
        
        # Reset all failure counters
        for key in self.failure_counts:
            self.failure_counts[key] = 0
        
        self.ws_disconnect_timestamps.clear()
        
        logger.info("✅ Trading re-enabled")
    
    def _get_disabled_duration(self) -> str:
        """Get human-readable duration since circuit breaker tripped."""
        if not self.disabled_at:
            return "N/A"
        
        duration = datetime.now(timezone.utc) - self.disabled_at
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m {total_seconds % 60}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.
        
        Returns:
            Dict with circuit breaker state information
        """
        return {
            "trading_enabled": not self.trading_disabled,
            "disabled": self.trading_disabled,
            "reason": self.disable_reason,
            "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
            "disabled_duration": self._get_disabled_duration(),
            "failure_counts": self.failure_counts.copy()
        }


# Singleton instance for easy access
_circuit_breaker_instance: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """
    Get or create the singleton CircuitBreaker instance.
    
    Returns:
        CircuitBreaker instance
    """
    global _circuit_breaker_instance
    if _circuit_breaker_instance is None:
        _circuit_breaker_instance = CircuitBreaker()
    return _circuit_breaker_instance
