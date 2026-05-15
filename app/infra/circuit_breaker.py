"""
System Circuit Breaker - Unified health monitoring and protective actions.
Monitors system-wide health metrics and triggers protective actions when anomalies detected.

Features:
- API failure rate tracking
- Slippage monitoring
- Position sync verification
- API latency monitoring
- Spread widening detection
- WebSocket health monitoring
- Automatic circuit state transitions (CLOSED → OPEN → HALF_OPEN)
- Emergency position closure
- Telegram alerts for critical events
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import time
import logging
from collections import deque

from app.config import settings
from app.logging_config import get_logger
from app.notifications.notifier import TelegramNotifier
from app.infra.kill_switch import KillSwitch

logger = get_logger(__name__)


@dataclass
class CircuitBreakerState:
    """Current state of the circuit breaker system."""
    state: str  # CLOSED, OPEN, HALF_OPEN
    reason: Optional[str] = None
    triggered_at: Optional[datetime] = None
    api_failure_count: int = 0
    avg_slippage_pct: float = 0.0
    position_sync_ok: bool = True
    avg_latency_ms: float = 0.0
    spread_ok: bool = True
    websocket_healthy: bool = True
    can_trade: bool = True


class SystemCircuitBreaker:
    """
    Monitor system-wide health and trigger protective actions.
    
    Health Metrics Tracked:
    1. API Failure Rate: Consecutive API errors from exchange calls
    2. Slippage Monitoring: Track actual vs expected fill prices
    3. Position Sync State: Compare local database vs exchange positions
    4. API Latency: Monitor response times for degradation
    5. Spread Widening: Detect abnormal bid-ask spreads
    6. WebSocket Health: Monitor data stream freshness
    """
    
    def __init__(self, notifier: TelegramNotifier):
        """
        Initialize circuit breaker system.
        
        Args:
            notifier: Telegram notifier for sending alerts
        """
        self.notifier = notifier
        
        # Load configuration
        self.failure_threshold = settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self.recovery_timeout = settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
        self.slippage_threshold = settings.CIRCUIT_BREAKER_SLIPPAGE_THRESHOLD
        self.latency_threshold_ms = settings.CIRCUIT_BREAKER_LATENCY_THRESHOLD_MS
        self.spread_threshold_pct = settings.CIRCUIT_BREAKER_SPREAD_THRESHOLD_PCT
        self.sync_tolerance_pct = settings.CIRCUIT_BREAKER_SYNC_TOLERANCE_PCT
        self.websocket_stale_threshold = settings.WEBSOCKET_STALE_STREAM_THRESHOLD
        
        # Circuit state
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.triggered_at: Optional[datetime] = None
        self.trigger_reason: Optional[str] = None
        
        # API failure tracking
        self.api_failure_count = 0
        self.api_success_count = 0
        self.recent_latencies: deque = deque(maxlen=100)
        
        # Slippage tracking
        self.recent_slippages: deque = deque(maxlen=50)
        
        # Position sync tracking
        self.position_sync_ok = True
        self.last_sync_check: Optional[float] = None
        
        # Spread tracking
        self.spread_ok = True
        
        # WebSocket tracking
        self.websocket_healthy = True
        self.last_websocket_message: Dict[str, float] = {}  # stream_name -> timestamp
        
        logger.info("✅ System Circuit Breaker initialized")
        logger.info(f"   Failure Threshold: {self.failure_threshold}")
        logger.info(f"   Recovery Timeout: {self.recovery_timeout}s")
        logger.info(f"   Slippage Threshold: {self.slippage_threshold:.2%}")
        logger.info(f"   Latency Threshold: {self.latency_threshold_ms}ms")
    
    async def check_system_health(self) -> CircuitBreakerState:
        """
        Aggregate all health metrics and determine overall circuit state.
        
        Returns:
            CircuitBreakerState with comprehensive health report
        """
        # Check if we should attempt recovery
        if self.state == 'OPEN':
            await self._check_recovery()
        
        # Calculate average latency
        avg_latency = (
            sum(self.recent_latencies) / len(self.recent_latencies)
            if self.recent_latencies else 0
        )
        
        # Calculate average slippage
        avg_slippage = (
            sum(self.recent_slippages) / len(self.recent_slippages)
            if self.recent_slippages else 0
        )
        
        # Determine if trading is allowed
        can_trade = (
            self.state != 'OPEN' and
            self.api_failure_count < self.failure_threshold and
            avg_slippage <= self.slippage_threshold and
            avg_latency <= self.latency_threshold_ms and
            self.position_sync_ok and
            self.spread_ok and
            self.websocket_healthy
        )
        
        return CircuitBreakerState(
            state=self.state,
            reason=self.trigger_reason,
            triggered_at=self.triggered_at,
            api_failure_count=self.api_failure_count,
            avg_slippage_pct=avg_slippage,
            position_sync_ok=self.position_sync_ok,
            avg_latency_ms=avg_latency,
            spread_ok=self.spread_ok,
            websocket_healthy=self.websocket_healthy,
            can_trade=can_trade
        )
    
    async def record_api_call(
        self,
        success: bool,
        latency_ms: float,
        endpoint: str
    ):
        """
        Track API call results for failure rate and latency monitoring.
        
        Args:
            success: Whether the API call succeeded
            latency_ms: Response time in milliseconds
            endpoint: API endpoint called
        """
        # Track latency
        self.recent_latencies.append(latency_ms)
        
        if success:
            self.api_success_count += 1
            
            # Reset failure count on success
            if self.api_failure_count > 0:
                old_count = self.api_failure_count
                self.api_failure_count = 0
                logger.debug(f"API success after {old_count} failures, counter reset")
        else:
            self.api_failure_count += 1
            logger.warning(
                f"⚠️  API call failed ({endpoint}): "
                f"{self.api_failure_count}/{self.failure_threshold}"
            )
            
            # Check if we've hit the threshold
            if self.api_failure_count >= self.failure_threshold:
                await self.trigger_circuit_breaker(
                    reason=f"API failures: {self.api_failure_count} consecutive failures on {endpoint}",
                    severity='critical'
                )
        
        # Check latency threshold
        if latency_ms > self.latency_threshold_ms:
            logger.warning(
                f"⚠️  High API latency: {latency_ms:.0f}ms > {self.latency_threshold_ms}ms"
            )
            # Don't trigger immediately, but track it
    
    async def record_fill_slippage(
        self,
        symbol: str,
        expected_price: float,
        actual_price: float
    ):
        """
        Track slippage between expected and actual fill prices.
        
        Args:
            symbol: Trading pair
            expected_price: Expected fill price
            actual_price: Actual fill price
        """
        if expected_price > 0:
            slippage_pct = abs(actual_price - expected_price) / expected_price
            self.recent_slippages.append(slippage_pct)
            
            # Check if slippage exceeds threshold
            if slippage_pct > self.slippage_threshold:
                logger.warning(
                    f"⚠️  High slippage on {symbol}: "
                    f"{slippage_pct:.3%} > {self.slippage_threshold:.2%}"
                )
                
                # Calculate rolling average
                avg_slippage = sum(self.recent_slippages) / len(self.recent_slippages)
                
                if avg_slippage > self.slippage_threshold:
                    await self.trigger_circuit_breaker(
                        reason=f"Excessive slippage: avg {avg_slippage:.3%} on {symbol}",
                        severity='warning'
                    )
    
    async def verify_position_sync(
        self,
        local_positions: List[Dict[str, Any]],
        exchange_positions: List[Dict[str, Any]]
    ):
        """
        Compare local database positions vs exchange positions.
        
        Args:
            local_positions: Positions from local database
            exchange_positions: Positions from exchange API
        """
        try:
            # Simple comparison: check if counts match
            local_count = len(local_positions)
            exchange_count = len(exchange_positions)
            
            if local_count != exchange_count:
                logger.warning(
                    f"⚠️  Position sync mismatch: local={local_count}, exchange={exchange_count}"
                )
                self.position_sync_ok = False
                
                await self.trigger_circuit_breaker(
                    reason=f"Position sync mismatch: local={local_count}, exchange={exchange_count}",
                    severity='critical'
                )
            else:
                # More detailed comparison could be added here
                self.position_sync_ok = True
            
            self.last_sync_check = time.time()
            
        except Exception as e:
            logger.error(f"Position sync verification failed: {e}")
            self.position_sync_ok = False
    
    async def check_spread_health(
        self,
        symbol: str,
        bid: float,
        ask: float
    ) -> bool:
        """
        Check if bid-ask spread is within acceptable limits.
        
        Args:
            symbol: Trading pair
            bid: Current bid price
            ask: Current ask price
            
        Returns:
            True if spread is healthy
        """
        if bid > 0 and ask > 0:
            spread_pct = (ask - bid) / bid
            
            if spread_pct > self.spread_threshold_pct:
                logger.warning(
                    f"⚠️  Wide spread on {symbol}: "
                    f"{spread_pct:.3%} > {self.spread_threshold_pct:.2%}"
                )
                self.spread_ok = False
                return False
            else:
                self.spread_ok = True
                return True
        
        return True  # Assume OK if no data
    
    async def handle_websocket_disconnect(self, stream_name: str):
        """
        Handle WebSocket disconnection event.
        
        Args:
            stream_name: Name of the disconnected stream
        """
        logger.warning(f"⚠️  WebSocket disconnected: {stream_name}")
        self.websocket_healthy = False
        
        # Check how long since last message
        last_msg_time = self.last_websocket_message.get(stream_name, 0)
        elapsed = time.time() - last_msg_time
        
        if elapsed > self.websocket_stale_threshold:
            await self.trigger_circuit_breaker(
                reason=f"WebSocket stale: {stream_name} disconnected for {elapsed:.0f}s",
                severity='warning'
            )
    
    async def handle_websocket_message(self, stream_name: str):
        """
        Record WebSocket message receipt to track stream health.
        
        Args:
            stream_name: Name of the stream
        """
        self.last_websocket_message[stream_name] = time.time()
        
        # If we were unhealthy, mark as healthy again
        if not self.websocket_healthy:
            self.websocket_healthy = True
            logger.info(f"✅ WebSocket stream recovered: {stream_name}")
    
    async def trigger_circuit_breaker(
        self,
        reason: str,
        severity: str = 'warning'
    ):
        """
        Transition to OPEN state and trigger protective actions.
        
        Args:
            reason: Reason for triggering
            severity: Severity level (warning, critical, emergency)
        """
        old_state = self.state
        self.state = 'OPEN'
        self.triggered_at = datetime.utcnow()
        self.trigger_reason = reason
        
        logger.error(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason} (severity: {severity})")
        
        # Send Telegram alert
        try:
            metrics = {
                'api_failures': self.api_failure_count,
                'avg_slippage': sum(self.recent_slippages) / len(self.recent_slippages) if self.recent_slippages else 0,
                'avg_latency': sum(self.recent_latencies) / len(self.recent_latencies) if self.recent_latencies else 0,
                'position_sync': self.position_sync_ok
            }
            
            await self.notifier.send_circuit_breaker_alert(
                state='OPEN',
                reason=reason,
                metrics=metrics
            )
        except Exception as e:
            logger.error(f"Failed to send circuit breaker alert: {e}")
        
        # For critical/emergency severity, consider closing positions
        if severity in ['critical', 'emergency']:
            logger.warning("🚨 Critical circuit breaker - considering emergency position closure")
            # In production, you might want to close high-risk positions here
            # Engage global kill switch to prevent further trade submissions
            try:
                ks = KillSwitch(notifier=self.notifier, persist_path=getattr(settings, 'KILL_SWITCH_STATE_FILE', '.kill_switch_state.json'))
                ks.engage(actor='circuit_breaker', reason=reason)
                logger.critical("Kill switch engaged by circuit breaker")
            except Exception as e:
                logger.error(f"Failed to engage kill switch: {e}")

            # Start emergency position closure in background to avoid blocking the breaker
            try:
                import asyncio
                logger.warning("Starting emergency close positions task (background)")
                asyncio.create_task(self.emergency_close_positions())
            except Exception as e:
                logger.error(f"Failed to start emergency close task: {e}")
    
    async def attempt_recovery(self) -> bool:
        """
        Test if system has recovered (HALF_OPEN state).
        
        Returns:
            True if recovery successful
        """
        if self.state != 'OPEN':
            return True
        
        # Check if recovery timeout has passed
        if self.triggered_at:
            elapsed = (datetime.utcnow() - self.triggered_at).total_seconds()
            
            if elapsed >= self.recovery_timeout:
                logger.info("🔧 Circuit breaker: Transitioning to HALF_OPEN for recovery test")
                self.state = 'HALF_OPEN'
                
                # Send notification about recovery attempt
                try:
                    await self.notifier.send_circuit_breaker_alert(
                        state='HALF_OPEN',
                        reason='Testing recovery after timeout',
                        metrics={}
                    )
                except Exception as e:
                    logger.error(f"Failed to send HALF_OPEN alert: {e}")
                
                # Run a comprehensive health check
                health = await self.check_system_health()
                
                if health.can_trade:
                    logger.info("✅ Circuit breaker: Recovery successful, returning to CLOSED")
                    self.state = 'CLOSED'
                    self.trigger_reason = None
                    self.triggered_at = None
                    
                    # Reset counters
                    self.api_failure_count = 0
                    self.recent_slippages.clear()
                    
                    await self.notifier.send_circuit_breaker_alert(
                        state='CLOSED',
                        reason='System recovered successfully',
                        metrics={}
                    )
                    
                    return True
                else:
                    logger.warning("⚠️  Circuit breaker: Recovery test failed, returning to OPEN")
                    self.state = 'OPEN'
                    self.triggered_at = datetime.utcnow()  # Reset timer
                    
                    await self.notifier.send_circuit_breaker_alert(
                        state='OPEN',
                        reason=f'Recovery failed: {health.reason or "Health check failed"}',
                        metrics={}
                    )
                    
                    return False
        
        return False
    
    async def _check_recovery(self):
        """Internal method to check if recovery should be attempted."""
        if self.state == 'OPEN' and self.triggered_at:
            elapsed = (datetime.utcnow() - self.triggered_at).total_seconds()
            
            if elapsed >= self.recovery_timeout:
                await self.attempt_recovery()
    
    async def emergency_close_positions(
        self,
        exchange_manager=None,
        exclude_symbols: List[str] = None
    ):
        """
        Close all open positions except excluded ones.
        
        Args:
            exchange_manager: Exchange manager instance for closing positions
            exclude_symbols: Symbols to exclude from closure
        """
        if exclude_symbols is None:
            exclude_symbols = []
        
        logger.warning("🚨 EMERGENCY: Closing all positions")

        if exclude_symbols is None:
            exclude_symbols = []

        closed_positions = []

        try:
            # If no exchange_manager provided, create one
            from app.infra.exchange_manager import UnifiedExchangeManager

            em = exchange_manager or UnifiedExchangeManager()

            # Fetch open positions
            open_positions = await em.get_open_positions()

            # Iterate and close safely
            for pos in open_positions:
                symbol = pos.get('symbol') or pos.get('market') or pos.get('instrument')
                if not symbol:
                    continue

                if symbol in exclude_symbols:
                    logger.info(f"Skipping excluded symbol during emergency close: {symbol}")
                    continue

                try:
                    logger.warning(f"Attempting emergency close for {symbol}")
                    res = await em.close_position(symbol)
                    closed_positions.append({'symbol': symbol, 'result': res})
                    logger.info(f"Emergency close result for {symbol}: {res}")
                except Exception as e:
                    logger.error(f"Failed to close position {symbol}: {e}")

            # Notify about closed positions
            try:
                await self.notifier.send_emergency_position_closure(
                    closed_positions=closed_positions,
                    reason="Circuit breaker triggered emergency closure"
                )
            except Exception as e:
                logger.error(f"Failed to send emergency position closure alert: {e}")

        except Exception as e:
            logger.error(f"Emergency position closure failed: {e}")
    
    def get_health_report(self) -> Dict[str, Any]:
        """
        Return comprehensive health dashboard.
        
        Returns:
            Dictionary with all metrics, states, and thresholds
        """
        avg_latency = (
            sum(self.recent_latencies) / len(self.recent_latencies)
            if self.recent_latencies else 0
        )
        
        avg_slippage = (
            sum(self.recent_slippages) / len(self.recent_slippages)
            if self.recent_slippages else 0
        )
        
        return {
            'circuit_state': self.state,
            'trigger_reason': self.trigger_reason,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'can_trade': self.state != 'OPEN',
            'metrics': {
                'api_failures': self.api_failure_count,
                'api_successes': self.api_success_count,
                'avg_latency_ms': round(avg_latency, 2),
                'avg_slippage_pct': round(avg_slippage * 100, 3),
                'position_sync_ok': self.position_sync_ok,
                'spread_ok': self.spread_ok,
                'websocket_healthy': self.websocket_healthy
            },
            'thresholds': {
                'failure_threshold': self.failure_threshold,
                'recovery_timeout_s': self.recovery_timeout,
                'slippage_threshold_pct': self.slippage_threshold * 100,
                'latency_threshold_ms': self.latency_threshold_ms,
                'spread_threshold_pct': self.spread_threshold_pct * 100,
                'sync_tolerance_pct': self.sync_tolerance_pct * 100
            }
        }
