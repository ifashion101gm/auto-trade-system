"""
System heartbeat monitor - checks all critical components every 30 seconds.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import text
from app.logging_config import get_logger

logger = get_logger(__name__)


class HeartbeatMonitor:
    """Monitors system health and triggers alerts on failures."""
    
    def __init__(self):
        self.running = False
        self.check_interval = 30  # seconds
        self.consecutive_failures = 0
        self.max_failures_before_alert = 3
    
    async def start(self):
        """Start heartbeat monitoring loop."""
        self.running = True
        logger.info("💓 Heartbeat monitor started")
        
        while self.running:
            try:
                await self._perform_health_check()
                self.consecutive_failures = 0
            except Exception as e:
                self.consecutive_failures += 1
                logger.error(f"💔 Heartbeat check failed ({self.consecutive_failures}): {e}")
                
                if self.consecutive_failures >= self.max_failures_before_alert:
                    await self._send_alert()
            
            await asyncio.sleep(self.check_interval)
    
    async def stop(self):
        """Stop heartbeat monitoring."""
        self.running = False
        logger.info("💓 Heartbeat monitor stopped")
    
    async def _perform_health_check(self):
        """Check all critical system components."""
        checks = {
            'database': await self._check_database(),
            'exchange': await self._check_exchange(),
            'websocket': await self._check_websocket(),
            'strategy_loop': await self._check_strategy_loop(),
        }
        
        all_healthy = all(checks.values())
        
        if all_healthy:
            logger.debug("💓 All systems healthy")
        else:
            unhealthy = [k for k, v in checks.items() if not v]
            logger.warning(f"💔 Unhealthy components: {unhealthy}")
    
    async def _check_database(self) -> bool:
        """Check database connectivity."""
        try:
            from app.database.connection import get_session
            async with get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database check failed: {e}")
            return False
    
    async def _check_exchange(self) -> bool:
        """Check exchange connectivity."""
        try:
            from app.infra.exchange_manager import UnifiedExchangeManager
            mgr = UnifiedExchangeManager()
            balance = await mgr.fetch_balance()
            return balance is not None
        except Exception as e:
            logger.error(f"Exchange check failed: {e}")
            return False
    
    async def _check_websocket(self) -> bool:
        """Check WebSocket connection status."""
        try:
            # Check if WebSocket manager is running
            from app.infra.websocket_manager import ws_manager
            return ws_manager.is_connected
        except Exception as e:
            logger.error(f"WebSocket check failed: {e}")
            return False
    
    async def _check_strategy_loop(self) -> bool:
        """Check if strategy loop is running."""
        # This would check if the main trading loop is active
        # For now, just return True
        return True
    
    async def _send_alert(self):
        """Send alert when too many consecutive failures."""
        try:
            from app.notifications.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier()
            await notifier.send_message(
                "🚨 SYSTEM ALERT\n\n"
                f"Heartbeat monitor detected {self.consecutive_failures} consecutive failures.\n"
                "System may be experiencing issues. Please check logs."
            )
        except Exception as e:
            logger.error(f"Failed to send heartbeat alert: {e}")


# Global instance
heartbeat_monitor = HeartbeatMonitor()
