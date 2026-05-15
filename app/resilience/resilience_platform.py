"""
Resilience Platform - Centralized failure management and recovery orchestration.

This module transforms the auto-trade system from a reactive watchdog framework
into a coordinated resilience platform with:

- Centralized ResilienceManager as single source of truth
- Deterministic recovery sequencing via RecoveryPlanner
- Failure domain isolation and correlation
- State-aware healing with global SystemStateMachine
- Recovery idempotency and cooldown management
- Backpressure-aware execution control

Architecture:
    Watchdogs/Monitors → FailureBus → ResilienceManager → RecoveryExecutor
                                    ↓
                          SystemStateMachine (global state)
                                    ↓
                         RecoveryPlanner (ordered plans)
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Global System States
# ============================================================================

class SystemMode(Enum):
    """
    Global operational states that govern all system behavior.
    
    This is the SINGLE SOURCE OF TRUTH for what the system can/cannot do.
    All components must check current mode before taking actions.
    """
    NORMAL = "normal"           # Full operation
    DEGRADED = "degraded"       # Reduced capacity, caution mode
    SAFE_MODE = "safe_mode"     # No new entries, exits only
    RECOVERY = "recovery"       # Active recovery in progress
    RECONCILING = "reconciling" # Reconciliation running
    EMERGENCY = "emergency"     # Emergency stop, close all positions
    SHUTDOWN = "shutdown"       # Graceful shutdown in progress
    
    def allows_trading(self) -> bool:
        """Check if trading is allowed in this mode."""
        return self in (SystemMode.NORMAL, SystemMode.DEGRADED)
    
    def allows_new_entries(self) -> bool:
        """Check if new trade entries are allowed."""
        return self == SystemMode.NORMAL
    
    def allows_exits_only(self) -> bool:
        """Check if only position exits are allowed."""
        return self == SystemMode.SAFE_MODE
    
    def blocks_all_trading(self) -> bool:
        """Check if all trading is blocked."""
        return self in (SystemMode.RECOVERY, SystemMode.EMERGENCY, SystemMode.SHUTDOWN)


@dataclass
class HealthScore:
    """
    Weighted health scoring system (0-100).
    
    Prevents binary healthy/unhealthy decisions by using composite metrics.
    """
    api_health: float = 100.0           # 0-100
    websocket_health: float = 100.0     # 0-100
    execution_health: float = 100.0     # 0-100
    memory_health: float = 100.0        # 0-100
    reconciliation_health: float = 100.0  # 0-100
    
    # Weights for composite score
    WEIGHTS = {
        'api': 0.35,
        'websocket': 0.25,
        'execution': 0.20,
        'memory': 0.10,
        'reconciliation': 0.10
    }
    
    @property
    def composite_score(self) -> float:
        """Calculate weighted composite health score."""
        return (
            self.api_health * self.WEIGHTS['api'] +
            self.websocket_health * self.WEIGHTS['websocket'] +
            self.execution_health * self.WEIGHTS['execution'] +
            self.memory_health * self.WEIGHTS['memory'] +
            self.reconciliation_health * self.WEIGHTS['reconciliation']
        )
    
    def determine_mode(self) -> SystemMode:
        """Determine system mode based on health score."""
        score = self.composite_score
        
        if score >= 90:
            return SystemMode.NORMAL
        elif score >= 70:
            return SystemMode.DEGRADED
        elif score >= 50:
            return SystemMode.SAFE_MODE
        elif score >= 30:
            return SystemMode.RECOVERY
        else:
            return SystemMode.EMERGENCY


# ============================================================================
# Failure Events
# ============================================================================

class FailureSeverity(Enum):
    """Failure severity levels for prioritization."""
    INFO = "info"               # Informational only
    WARNING = "warning"         # Needs attention
    CRITICAL = "critical"       # Immediate action required
    EMERGENCY = "emergency"     # System-threatening


class FailureDomain(Enum):
    """Failure domains for isolation and targeted recovery."""
    API = "api"
    WEBSOCKET = "websocket"
    DATABASE = "database"
    MEMORY = "memory"
    EXECUTION = "execution"
    RECONCILIATION = "reconciliation"
    STATE_MACHINE = "state_machine"
    EXTERNAL = "external"  # News, exchange maintenance, etc.


@dataclass
class FailureEvent:
    """
    Immutable failure event for event-sourced recovery.
    
    All failures flow through this structure for consistent handling.
    """
    source: str                           # Component that detected failure
    failure_type: str                     # Type of failure
    severity: FailureSeverity             # Severity level
    domain: FailureDomain                 # Failure domain
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str = field(default_factory=lambda: str(uuid4())[:8])
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/event bus."""
        return {
            'source': self.source,
            'failure_type': self.failure_type,
            'severity': self.severity.value,
            'domain': self.domain.value,
            'timestamp': self.timestamp.isoformat(),
            'correlation_id': self.correlation_id,
            'metadata': self.metadata
        }


# ============================================================================
# Recovery Plans
# ============================================================================

@dataclass
class RecoveryStep:
    """Single step in a recovery plan."""
    action_name: str
    description: str
    timeout_seconds: int = 30
    rollback_action: Optional[str] = None
    idempotent: bool = True  # Can be safely retried


@dataclass
class RecoveryPlan:
    """
    Ordered sequence of recovery steps.
    
    Plans are deterministic, auditable, and can be simulated before execution.
    """
    plan_id: str = field(default_factory=lambda: str(uuid4())[:12])
    failure_event: Optional[FailureEvent] = None
    steps: List[RecoveryStep] = field(default_factory=list)
    priority: int = 5  # 1=highest, 10=lowest
    estimated_downtime_seconds: int = 0
    risk_level: str = "low"  # low/medium/high/critical
    
    def add_step(self, action_name: str, description: str, **kwargs):
        """Add a step to the recovery plan."""
        self.steps.append(RecoveryStep(
            action_name=action_name,
            description=description,
            **kwargs
        ))
    
    def simulate(self) -> Dict[str, Any]:
        """Simulate plan execution without taking action."""
        return {
            'plan_id': self.plan_id,
            'steps_count': len(self.steps),
            'estimated_downtime': self.estimated_downtime_seconds,
            'risk_level': self.risk_level,
            'actions': [step.action_name for step in self.steps]
        }


# ============================================================================
# Healing Cooldown Manager
# ============================================================================

class HealingCooldownManager:
    """
    Prevents recovery action spam and restart loops.
    
    Tracks when recovery actions were last executed and enforces minimum
    intervals between repeated actions.
    """
    
    def __init__(self):
        self._cooldowns: Dict[str, datetime] = {}
        self._execution_counts: Dict[str, List[datetime]] = {}
        
        # Default cooldowns (seconds)
        self.DEFAULT_COOLDOWNS = {
            'api_reconnect': 60,
            'reconciliation': 120,
            'system_restart': 3600,  # Max 3 per hour
            'position_close': 30,
            'circuit_breaker_reset': 300,
            'state_reset': 600,
        }
    
    def should_execute(self, action_name: str, custom_cooldown: Optional[int] = None) -> bool:
        """Check if action can be executed (not in cooldown period)."""
        cooldown_sec = custom_cooldown or self.DEFAULT_COOLDOWNS.get(action_name, 60)
        last_execution = self._cooldowns.get(action_name)
        
        if not last_execution:
            return True
        
        elapsed = (datetime.utcnow() - last_execution).total_seconds()
        return elapsed >= cooldown_sec
    
    def record_execution(self, action_name: str):
        """Record that an action was executed."""
        now = datetime.utcnow()
        self._cooldowns[action_name] = now
        
        # Track execution history for rate limiting
        if action_name not in self._execution_counts:
            self._execution_counts[action_name] = []
        
        self._execution_counts[action_name].append(now)
        
        # Keep only last hour of history
        cutoff = now - timedelta(hours=1)
        self._execution_counts[action_name] = [
            ts for ts in self._execution_counts[action_name]
            if ts > cutoff
        ]
    
    def get_execution_count(self, action_name: str, window_minutes: int = 60) -> int:
        """Get number of executions in time window."""
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        executions = self._execution_counts.get(action_name, [])
        return len([ts for ts in executions if ts > cutoff])
    
    def would_exceed_rate_limit(self, action_name: str, max_per_hour: int = 3) -> bool:
        """Check if executing would exceed rate limit."""
        return self.get_execution_count(action_name, 60) >= max_per_hour


# ============================================================================
# Failure Correlation Engine
# ============================================================================

class FailureCorrelationEngine:
    """
    Groups related failures into incidents for root-cause analysis.
    
    Prevents alert storms by correlating cascading failures from a single root cause.
    """
    
    def __init__(self, correlation_window_seconds: int = 60):
        self.correlation_window = timedelta(seconds=correlation_window_seconds)
        self.active_incidents: Dict[str, List[FailureEvent]] = {}
        self.incident_counter = 0
    
    def correlate(self, new_event: FailureEvent) -> Optional[str]:
        """
        Try to correlate new failure with existing incidents.
        
        Returns incident ID if correlated, None if new incident.
        """
        # Check each active incident for correlation
        for incident_id, events in self.active_incidents.items():
            if self._is_correlated(new_event, events):
                events.append(new_event)
                logger.info(
                    f"🔗 Correlated failure {new_event.failure_type} "
                    f"with incident {incident_id}"
                )
                return incident_id
        
        # Create new incident
        self.incident_counter += 1
        incident_id = f"INC-{self.incident_counter:04d}"
        self.active_incidents[incident_id] = [new_event]
        
        logger.info(f"🆕 New incident {incident_id}: {new_event.failure_type}")
        return incident_id
    
    def _is_correlated(self, new_event: FailureEvent, existing_events: List[FailureEvent]) -> bool:
        """Check if new event is correlated with existing events."""
        if not existing_events:
            return False
        
        # Time-based correlation
        latest_event = max(existing_events, key=lambda e: e.timestamp)
        time_diff = (new_event.timestamp - latest_event.timestamp).total_seconds()
        
        if abs(time_diff) > self.correlation_window.total_seconds():
            return False
        
        # Domain-based correlation (same domain or related domains)
        related_domains = self._get_related_domains(new_event.domain)
        if any(e.domain in related_domains for e in existing_events):
            return True
        
        # Source-based correlation (same component)
        if any(e.source == new_event.source for e in existing_events):
            return True
        
        return False
    
    def _get_related_domains(self, domain: FailureDomain) -> Set[FailureDomain]:
        """Get domains that are commonly related."""
        correlations = {
            FailureDomain.API: {FailureDomain.WEBSOCKET, FailureDomain.EXECUTION},
            FailureDomain.WEBSOCKET: {FailureDomain.API, FailureDomain.EXECUTION},
            FailureDomain.DATABASE: {FailureDomain.EXECUTION, FailureDomain.RECONCILIATION},
            FailureDomain.MEMORY: {FailureDomain.EXECUTION, FailureDomain.STATE_MACHINE},
            FailureDomain.EXECUTION: {FailureDomain.API, FailureDomain.RECONCILIATION},
            FailureDomain.RECONCILIATION: {FailureDomain.DATABASE, FailureDomain.EXECUTION},
        }
        return correlations.get(domain, set())
    
    def close_incident(self, incident_id: str) -> List[FailureEvent]:
        """Close incident and return event history."""
        return self.active_incidents.pop(incident_id, [])
    
    def get_incident_summary(self, incident_id: str) -> Dict[str, Any]:
        """Get summary of incident for debugging."""
        events = self.active_incidents.get(incident_id, [])
        if not events:
            return {}
        
        return {
            'incident_id': incident_id,
            'event_count': len(events),
            'duration_seconds': (
                max(e.timestamp for e in events) - min(e.timestamp for e in events)
            ).total_seconds(),
            'domains': list(set(e.domain.value for e in events)),
            'severities': list(set(e.severity.value for e in events)),
            'events': [e.to_dict() for e in events]
        }


# ============================================================================
# Backpressure Controller
# ============================================================================

class BackpressureController:
    """
    Slows down execution when system is under stress.
    
    Prevents recovery system collapse under load by reducing trade frequency
    when queues grow, latency increases, or reconciliation lags.
    """
    
    def __init__(
        self,
        max_queue_depth: int = 100,
        max_latency_ms: float = 5000,
        reconciliation_lag_threshold_sec: int = 300
    ):
        self.max_queue_depth = max_queue_depth
        self.max_latency_ms = max_latency_ms
        self.reconciliation_lag_threshold = reconciliation_lag_threshold_sec
        
        self.current_delay_ms = 0
        self.trade_frequency_multiplier = 1.0  # 1.0 = normal, 0.5 = half speed
    
    def calculate_backpressure(
        self,
        queue_depth: int = 0,
        current_latency_ms: float = 0,
        reconciliation_lag_sec: float = 0
    ) -> Dict[str, Any]:
        """Calculate backpressure parameters based on system load."""
        
        # Queue depth pressure
        queue_pressure = min(queue_depth / self.max_queue_depth, 1.0)
        
        # Latency pressure
        latency_pressure = min(current_latency_ms / self.max_latency_ms, 1.0)
        
        # Reconciliation lag pressure
        recon_pressure = min(reconciliation_lag_sec / self.reconciliation_lag_threshold, 1.0)
        
        # Combined pressure (weighted)
        total_pressure = (
            queue_pressure * 0.4 +
            latency_pressure * 0.4 +
            recon_pressure * 0.2
        )
        
        # Calculate trade frequency reduction
        if total_pressure > 0.8:
            self.trade_frequency_multiplier = 0.25  # 75% reduction
            self.current_delay_ms = 2000
        elif total_pressure > 0.6:
            self.trade_frequency_multiplier = 0.5   # 50% reduction
            self.current_delay_ms = 1000
        elif total_pressure > 0.4:
            self.trade_frequency_multiplier = 0.75  # 25% reduction
            self.current_delay_ms = 500
        else:
            self.trade_frequency_multiplier = 1.0   # Normal
            self.current_delay_ms = 0
        
        return {
            'total_pressure': round(total_pressure, 2),
            'trade_frequency_multiplier': self.trade_frequency_multiplier,
            'recommended_delay_ms': self.current_delay_ms,
            'queue_pressure': round(queue_pressure, 2),
            'latency_pressure': round(latency_pressure, 2),
            'reconciliation_pressure': round(recon_pressure, 2)
        }
    
    def should_delay_execution(self) -> bool:
        """Check if execution should be delayed."""
        return self.current_delay_ms > 0
    
    async def apply_backpressure_delay(self):
        """Apply calculated delay before next execution."""
        if self.current_delay_ms > 0:
            logger.warning(
                f"⏳ Applying backpressure delay: {self.current_delay_ms}ms "
                f"(frequency multiplier: {self.trade_frequency_multiplier})"
            )
            await asyncio.sleep(self.current_delay_ms / 1000)
