"""
Alert Manager - Centralized alert system with deduplication and severity levels.

Features:
- Alert deduplication to prevent spam (configurable time windows)
- Severity levels: INFO, WARNING, CRITICAL, EMERGENCY
- Integration with TelegramNotifier for delivery
- Session-aware alerting (suppress non-critical alerts during off-hours)
- Alert history tracking for audit trail

This module implements the alerting layer for Phase 2 of the production roadmap.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

from app.logging_config import get_logger
from app.notifications.notifier import TelegramNotifier

logger = get_logger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class AlertUrgency(Enum):
    """Alert urgency for delivery priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    IMMEDIATE = "immediate"


class AlertDeduplicator:
    """
    Prevents duplicate alerts within configurable time windows.
    
    Tracks recently sent alerts and suppresses duplicates based on:
    - Alert type/key
    - Configurable deduplication window (default: 15 minutes)
    - Severity level (critical alerts may bypass deduplication)
    """
    
    def __init__(self, dedup_window_minutes: int = 15):
        """
        Initialize alert deduplicator.
        
        Args:
            dedup_window_minutes: Time window for deduplication (minutes)
        """
        self.dedup_window = timedelta(minutes=dedup_window_minutes)
        self.recent_alerts: Dict[str, datetime] = {}
        self.alert_counts: Dict[str, int] = {}
        
        logger.info(f"✅ AlertDeduplicator initialized (window: {dedup_window_minutes}min)")
    
    def should_send(self, alert_key: str, level: AlertLevel = AlertLevel.WARNING) -> bool:
        """
        Check if alert should be sent (not duplicated).
        
        Args:
            alert_key: Unique identifier for the alert type
            level: Alert severity level
            
        Returns:
            True if alert should be sent, False if suppressed
        """
        now = datetime.utcnow()
        
        # Emergency alerts always bypass deduplication
        if level == AlertLevel.EMERGENCY:
            logger.debug(f"Emergency alert bypasses deduplication: {alert_key}")
            return True
        
        # Check if alert was recently sent
        if alert_key in self.recent_alerts:
            last_sent = self.recent_alerts[alert_key]
            if now - last_sent < self.dedup_window:
                # Track suppression count for monitoring
                self.alert_counts[alert_key] = self.alert_counts.get(alert_key, 0) + 1
                
                logger.debug(
                    f"Alert deduplicated: {alert_key} "
                    f"(suppressed {self.alert_counts[alert_key]} times)"
                )
                return False
        
        # Record this alert
        self.recent_alerts[alert_key] = now
        self.alert_counts[alert_key] = 0
        
        return True
    
    def cleanup_old_entries(self):
        """Remove expired entries from recent alerts cache."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, timestamp in self.recent_alerts.items()
            if now - timestamp > self.dedup_window * 2
        ]
        
        for key in expired_keys:
            del self.recent_alerts[key]
            del self.alert_counts[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired alert entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        return {
            'active_alerts': len(self.recent_alerts),
            'total_suppressions': sum(self.alert_counts.values()),
            'most_suppressed': max(
                self.alert_counts.items(),
                key=lambda x: x[1],
                default=('none', 0)
            )
        }


class AlertManager:
    """
    Centralized alert management system.
    
    Provides:
    - Unified alert interface with severity levels
    - Automatic deduplication via AlertDeduplicator
    - Telegram notification integration
    - Session-aware alerting (suppresses non-critical alerts during off-hours)
    - Alert history for audit trail
    """
    
    def __init__(
        self,
        dedup_window_minutes: int = 15,
        enable_session_awareness: bool = True
    ):
        """
        Initialize alert manager.
        
        Args:
            dedup_window_minutes: Deduplication time window
            enable_session_awareness: Suppress non-critical alerts during off-hours
        """
        self.deduplicator = AlertDeduplicator(dedup_window_minutes=dedup_window_minutes)
        self.notifier = TelegramNotifier()
        self.enable_session_awareness = enable_session_awareness
        
        # Alert history (last 100 alerts)
        self.alert_history: List[Dict[str, Any]] = []
        self.max_history_size = 100
        
        logger.info("✅ AlertManager initialized")
    
    async def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        alert_type: str,
        urgency: AlertUrgency = AlertUrgency.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        force_send: bool = False
    ) -> bool:
        """
        Send alert with deduplication and session awareness.
        
        Args:
            level: Alert severity level
            title: Alert title/summary
            message: Detailed alert message
            alert_type: Unique alert type identifier for deduplication
            urgency: Delivery urgency/priority
            metadata: Additional context data
            force_send: Bypass deduplication and session checks
            
        Returns:
            True if alert was sent, False if suppressed
        """
        try:
            # Check session awareness (unless forced)
            if not force_send and self.enable_session_awareness:
                if not self._is_active_trading_session():
                    # Suppress non-critical alerts during off-hours
                    if level in [AlertLevel.INFO, AlertLevel.WARNING]:
                        logger.debug(
                            f"Alert suppressed (off-hours): {title}"
                        )
                        return False
            
            # Check deduplication (unless emergency or forced)
            if not force_send and level != AlertLevel.EMERGENCY:
                if not self.deduplicator.should_send(alert_type, level):
                    logger.debug(f"Alert suppressed (duplicate): {alert_type}")
                    return False
            
            # Format alert message
            formatted_message = self._format_alert_message(
                level, title, message, metadata
            )
            
            # Send via Telegram
            success = await self._deliver_alert(formatted_message, urgency)
            
            # Record in history
            if success:
                self._record_alert(level, title, message, alert_type, metadata)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}", exc_info=True)
            return False
    
    async def _deliver_alert(self, message: str, urgency: AlertUrgency) -> bool:
        """
        Deliver alert via Telegram notifier.
        
        Args:
            message: Formatted alert message
            urgency: Delivery urgency
            
        Returns:
            True if delivered successfully
        """
        try:
            # For high/immediate urgency, use direct send
            if urgency in [AlertUrgency.HIGH, AlertUrgency.IMMEDIATE]:
                await self.notifier.send_message(message)
            else:
                # Normal/low urgency can use batched delivery (future enhancement)
                await self.notifier.send_message(message)
            
            logger.debug(f"Alert delivered: {urgency.value}")
            return True
            
        except Exception as e:
            logger.error(f"Alert delivery failed: {e}")
            return False
    
    def _format_alert_message(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format alert message with emoji and structure.
        
        Args:
            level: Alert severity
            title: Alert title
            message: Alert details
            metadata: Additional context
            
        Returns:
            Formatted message string
        """
        # Emoji mapping for severity levels
        emojis = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
            AlertLevel.EMERGENCY: "🆘"
        }
        
        emoji = emojis.get(level, "📢")
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        formatted = f"{emoji} **{level.value}: {title}**\n\n"
        formatted += f"{message}\n\n"
        formatted += f"_Timestamp: {timestamp}_"
        
        # Add metadata if provided
        if metadata:
            formatted += "\n\n_Details:_\n"
            for key, value in metadata.items():
                formatted += f"• {key}: {value}\n"
        
        return formatted
    
    def _record_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        alert_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record alert in history for audit trail."""
        alert_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.value,
            'title': title,
            'message': message,
            'alert_type': alert_type,
            'metadata': metadata or {}
        }
        
        self.alert_history.append(alert_record)
        
        # Trim history to max size
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size:]
    
    def _is_active_trading_session(self) -> bool:
        """
        Check if currently in active trading session.
        
        Returns:
            True if in London/NY trading hours, False otherwise
        """
        # Simple implementation: check current hour UTC
        # London session: 08:00-17:00 UTC
        # NY session: 13:00-22:00 UTC
        # Combined active hours: 08:00-22:00 UTC
        
        current_hour = datetime.utcnow().hour
        
        # Active during London or NY sessions
        is_active = 8 <= current_hour <= 22
        
        return is_active
    
    def get_alert_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent alert history.
        
        Args:
            limit: Maximum number of alerts to return
            
        Returns:
            List of recent alert records
        """
        return self.alert_history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get alert manager statistics."""
        return {
            'total_alerts_sent': len(self.alert_history),
            'deduplication_stats': self.deduplicator.get_stats(),
            'session_awareness_enabled': self.enable_session_awareness,
            'recent_alerts': self.get_alert_history(limit=5)
        }
    
    def cleanup(self):
        """Periodic cleanup of old deduplication entries."""
        self.deduplicator.cleanup_old_entries()


# ============================================================================
# Singleton Instance
# ============================================================================

_alert_manager_instance: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    Get or create singleton AlertManager instance.
    
    Returns:
        AlertManager singleton instance
    """
    global _alert_manager_instance
    
    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager(
            dedup_window_minutes=15,
            enable_session_awareness=True
        )
        logger.info("✅ AlertManager singleton created")
    
    return _alert_manager_instance


def reset_alert_manager():
    """Reset singleton instance (for testing)."""
    global _alert_manager_instance
    _alert_manager_instance = None
    logger.info("🔄 AlertManager singleton reset")
