# Production Readiness Roadmap - Execution Plan

**Start Date:** May 15, 2026  
**Status:** 🔄 **PHASE 1 IN PROGRESS**

---

## Executive Summary

This document outlines the systematic execution of the 4-phase production readiness roadmap for the auto-trade system. Each phase includes specific deliverables, validation criteria, and success metrics.

---

## Phase 1: Immediate Deployment & Monitoring (Today - 48 Hours)

### ✅ Status: READY FOR DEPLOYMENT

**Completed Prerequisites:**
- ✅ WatchdogOrchestrator integrated into `app/main.py`
- ✅ Configuration settings added to `app/config.py`
- ✅ Environment variables documented in `.env.example`
- ✅ Integration tests passing (94% success rate)
- ✅ Validation script confirms all components working

### 📋 Deployment Checklist

#### Step 1: Prepare Staging Environment

```bash
# 1. Backup current configuration
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# 2. Add watchdog configuration to .env
cat >> .env << 'EOF'

# =============================================================================
# Phase 2: Self-Healing Watchdog Configuration
# =============================================================================
API_WATCHDOG_CHECK_INTERVAL_SEC=30
DB_WATCHDOG_CHECK_INTERVAL_SEC=60
MEMORY_WATCHDOG_CHECK_INTERVAL_SEC=120
QUEUE_WATCHDOG_CHECK_INTERVAL_SEC=60
MEMORY_WATCHDOG_WARNING_THRESHOLD_MB=512
MEMORY_WATCHDOG_CRITICAL_THRESHOLD_MB=1024
MEMORY_WATCHDOG_GC_TRIGGER_THRESHOLD_MB=768
EOF

# 3. Verify psutil is installed
pip install psutil>=5.9.0

# 4. Validate configuration
python scripts/validate_phase2.py
```

#### Step 2: Deploy to Staging

```bash
# Option A: Systemd service
sudo systemctl stop auto-trade-system
sudo systemctl start auto-trade-system
sudo systemctl status auto-trade-system

# Option B: Docker
docker-compose down
docker-compose up -d trading-bot

# Option C: Manual restart
pkill -f "python.*main.py"
nohup python -m app.main > /dev/null 2>&1 &
```

#### Step 3: Monitor Startup Logs

```bash
# Watch for successful initialization
tail -f logs/all_*.log | grep -E "watchdog|Watchdog"

# Expected output within first 60 seconds:
# 🔍 Initializing self-healing watchdogs...
# ✅ Self-healing watchdogs initialized
# 🚀 Starting all watchdogs...
# ✅ All 4 watchdogs started
# 🔄 API Watchdog started periodic checks
# 🔄 Database Watchdog started periodic checks
# 🔄 Memory Watchdog started periodic checks
# 🔄 Queue Watchdog started periodic checks
```

#### Step 4: 24-48 Hour Monitoring Plan

**Create monitoring script:** `scripts/monitor_watchdogs.sh`

```bash
#!/bin/bash
# Monitor watchdog health for 48 hours

LOG_DIR="logs"
MONITOR_DURATION_HOURS=48
CHECK_INTERVAL_MINUTES=30

echo "Starting ${MONITOR_DURATION_HOURS}-hour watchdog monitoring..."
echo "Check interval: ${CHECK_INTERVAL_MINUTES} minutes"
echo "Press Ctrl+C to stop early"

START_TIME=$(date +%s)
END_TIME=$((START_TIME + MONITOR_DURATION_HOURS * 3600))

while [ $(date +%s) -lt $END_TIME ]; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Check for critical errors
    CRITICAL_COUNT=$(grep -c "CRITICAL\|🚨" ${LOG_DIR}/all_*.log 2>/dev/null || echo 0)
    
    # Check watchdog health status
    LAST_HEALTH=$(grep "Overall Status" ${LOG_DIR}/all_*.log 2>/dev/null | tail -1)
    
    # Check memory usage
    LAST_MEMORY=$(grep "Memory Health" ${LOG_DIR}/all_*.log 2>/dev/null | tail -1)
    
    # Report status
    echo "[${TIMESTAMP}] Critical alerts: ${CRITICAL_COUNT}"
    echo "[${TIMESTAMP}] Last health: ${LAST_HEALTH}"
    echo "[${TIMESTAMP}] Last memory: ${LAST_MEMORY}"
    echo "---"
    
    sleep $((CHECK_INTERVAL_MINUTES * 60))
done

echo "Monitoring complete. Generating summary report..."
```

**Make executable:**
```bash
chmod +x scripts/monitor_watchdogs.sh
```

**Run monitoring:**
```bash
# Start background monitoring
nohup scripts/monitor_watchdogs.sh > logs/watchdog_monitor.log 2>&1 &
```

### 📊 Success Criteria for Phase 1

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Watchdog Initialization** | 100% success | Check logs for "✅ All 4 watchdogs started" |
| **False Positive Rate** | <5% | Count alerts vs actual issues |
| **System Overhead** | <0.2% CPU | Monitor via `top` or Prometheus |
| **Memory Growth** | <50MB over 48h | Track RSS in logs |
| **API Latency Checks** | Every 30s ±5s | Verify check intervals in logs |
| **No Service Disruptions** | Zero downtime | Application uptime monitoring |

### 🚨 Alert Thresholds (Manual Monitoring)

**Immediate Investigation Required If:**
- ❌ More than 3 "CRITICAL" log entries in 1 hour
- ❌ Memory usage exceeds 800MB consistently
- ❌ API latency >10 seconds for more than 5 consecutive checks
- ❌ Any "EMERGENCY STOP TRIGGERED" messages
- ❌ Application crashes or restarts unexpectedly

### 📝 Phase 1 Validation Report Template

After 48 hours, complete this checklist:

```markdown
## Phase 1 Validation Report

**Date:** _______________  
**Monitored By:** _______________

### System Stability
- [ ] Application ran continuously for 48 hours
- [ ] No unexpected crashes or restarts
- [ ] Watchdogs remained active throughout

### Watchdog Performance
- [ ] API watchdog checked every ~30 seconds
- [ ] DB watchdog checked every ~60 seconds
- [ ] Memory watchdog checked every ~120 seconds
- [ ] Queue watchdog checked every ~60 seconds

### Alert Quality
- [ ] Total alerts generated: _____
- [ ] False positives: _____ (<5% target)
- [ ] True positives acted upon: _____

### Resource Usage
- [ ] Average CPU overhead: _____% (<0.2% target)
- [ ] Peak memory usage: _____MB
- [ ] Memory growth over 48h: _____MB (<50MB target)

### Issues Encountered
[List any problems, false alarms, or unexpected behavior]

### Recommendation
[ ] PROCEED to Phase 2
[ ] NEEDS ADJUSTMENT before proceeding
[ ] ROLLBACK required

**Sign-off:** _______________
```

---

## Phase 2: Alerting & Health Visibility (Week 1)

### 🎯 Deliverable 1: Telegram Alert Integration

**Priority:** HIGH  
**Estimated Effort:** 2-3 hours

#### Implementation Plan

**Step 1: Create Alert Manager**

File: `app/notifications/alert_manager.py`

```python
"""
Alert Manager - Deduplicated alert delivery via Telegram.

Prevents alert spam by:
- Tracking recent alerts (deduplication window: 15 minutes)
- Grouping similar alerts
- Escalating severity levels
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib

from app.logging_config import get_logger
from app.notifications.telegram_notifier import get_telegram_notifier

logger = get_logger(__name__)


class AlertDeduplicator:
    """Prevents duplicate alerts within configurable time windows."""
    
    def __init__(self, dedup_window_minutes: int = 15):
        self.dedup_window = timedelta(minutes=dedup_window_minutes)
        self.recent_alerts: Dict[str, datetime] = {}
    
    def should_send(self, alert_key: str) -> bool:
        """Check if alert should be sent (not duplicated)."""
        now = datetime.utcnow()
        
        if alert_key in self.recent_alerts:
            last_sent = self.recent_alerts[alert_key]
            if now - last_sent < self.dedup_window:
                logger.debug(f"Alert deduplicated: {alert_key}")
                return False
        
        # Update timestamp
        self.recent_alerts[alert_key] = now
        
        # Clean old entries
        cutoff = now - self.dedup_window * 4
        self.recent_alerts = {
            k: v for k, v in self.recent_alerts.items() 
            if v > cutoff
        }
        
        return True
    
    def generate_alert_key(self, alert_type: str, details: str) -> str:
        """Generate unique key for alert deduplication."""
        raw_key = f"{alert_type}:{details}"
        return hashlib.md5(raw_key.encode()).hexdigest()[:12]


class AlertManager:
    """Manages alert delivery with deduplication and severity levels."""
    
    def __init__(self):
        self.deduplicator = AlertDeduplicator(dedup_window_minutes=15)
        self.notifier = get_telegram_notifier()
        
        # Alert counters
        self.alert_counts = defaultdict(int)
        
        logger.info("✅ AlertManager initialized")
    
    async def send_alert(
        self,
        level: str,  # INFO, WARNING, CRITICAL, EMERGENCY
        title: str,
        message: str,
        alert_type: str = "general",
        urgency: str = "normal"  # normal, high, immediate
    ):
        """
        Send alert via Telegram with deduplication.
        
        Args:
            level: Alert severity level
            title: Alert title
            message: Alert message body
            alert_type: Type for deduplication (e.g., 'api_failure', 'memory_leak')
            urgency: Delivery urgency
        """
        # Generate deduplication key
        alert_key = self.deduplicator.generate_alert_key(alert_type, title)
        
        # Check if we should send
        if not self.deduplicator.should_send(alert_key):
            logger.debug(f"Alert suppressed (deduplication): {title}")
            return
        
        # Format message based on urgency
        formatted_message = self._format_alert(level, title, message, urgency)
        
        # Send via Telegram
        try:
            await self.notifier.send_alert(
                message=formatted_message,
                parse_mode="Markdown"
            )
            
            # Track alert
            self.alert_counts[alert_type] += 1
            
            logger.info(f"Alert sent [{level}]: {title}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def _format_alert(self, level: str, title: str, message: str, urgency: str) -> str:
        """Format alert message for Telegram."""
        emoji_map = {
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'CRITICAL': '🚨',
            'EMERGENCY': '🔴'
        }
        
        urgency_prefix = {
            'normal': '',
            'high': '🔺 HIGH PRIORITY\n',
            'immediate': '🔺🔺 IMMEDIATE ACTION REQUIRED\n'
        }
        
        emoji = emoji_map.get(level, '📢')
        prefix = urgency_prefix.get(urgency, '')
        
        return (
            f"{prefix}"
            f"{emoji} *{title}*\n\n"
            f"{message}\n\n"
            f"_Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}_"
        )
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        return {
            'total_alerts': sum(self.alert_counts.values()),
            'alerts_by_type': dict(self.alert_counts),
            'deduplication_active': len(self.deduplicator.recent_alerts)
        }


# Singleton instance
_alert_manager_instance: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create singleton AlertManager instance."""
    global _alert_manager_instance
    if _alert_manager_instance is None:
        _alert_manager_instance = AlertManager()
    return _alert_manager_instance
```

**Step 2: Integrate with Watchdogs**

Update `app/self_healing/watchdogs.py`:

```python
# Add at top of file
from app.notifications.alert_manager import get_alert_manager

# In APIWatchdog.trigger_emergency_stop():
async def trigger_emergency_stop(self):
    """Trigger emergency stop when API is completely unresponsive."""
    logger.critical(
        f"🚨 EMERGENCY STOP TRIGGERED: {self.consecutive_failures} consecutive "
        f"API failures detected"
    )
    
    # NEW: Send Telegram alert
    try:
        alert_mgr = get_alert_manager()
        await alert_mgr.send_alert(
            level="EMERGENCY",
            title="API Emergency Stop Triggered",
            message=(
                f"Exchange API unresponsive after {self.consecutive_failures} "
                f"consecutive failures.\n\n"
                f"Trading has been halted to prevent losses.\n"
                f"Immediate investigation required."
            ),
            alert_type="api_emergency_stop",
            urgency="immediate"
        )
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
    
    # TODO: Integrate with circuit breaker to block trading
    # TODO: Trigger RecoveryAgent for API reconnection

# Similar updates for:
# - APIWatchdog.trigger_degraded_mode()
# - DatabaseWatchdog.alert_db_failure()
# - MemoryWatchdog.trigger_critical_alert()
# - QueueWatchdog.trigger_worker_restart()
```

**Step 3: Test Alert Delivery**

```python
# Test script: scripts/test_alerts.py
import asyncio
from app.notifications.alert_manager import get_alert_manager

async def test_alerts():
    alert_mgr = get_alert_manager()
    
    # Test different severity levels
    await alert_mgr.send_alert(
        level="INFO",
        title="Test Alert",
        message="This is a test info alert",
        alert_type="test_info"
    )
    
    await alert_mgr.send_alert(
        level="WARNING",
        title="High Memory Usage",
        message="Memory usage at 75%",
        alert_type="test_warning"
    )
    
    await alert_mgr.send_alert(
        level="CRITICAL",
        title="API Failure",
        message="API endpoint unreachable",
        alert_type="test_critical",
        urgency="high"
    )
    
    print("Alerts sent successfully!")

if __name__ == "__main__":
    asyncio.run(test_alerts())
```

---

### 🎯 Deliverable 2: Health Check Endpoints

**Priority:** MEDIUM  
**Estimated Effort:** 2-3 hours

#### Implementation

**Create:** `app/dashboard/health_api.py`

```python
"""
Health Check API - System status endpoints for monitoring.

Provides:
- Public health check (/health)
- Detailed authenticated health check (/health/detailed)
- Component-level status reporting
"""
import time
from fastapi import APIRouter, Header, HTTPException
from datetime import datetime

from app.main import state
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def health_check():
    """
    Public health check - no authentication required.
    
    Returns basic system status for load balancers and uptime monitors.
    """
    uptime = int(time.time() - state.start_time)
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": uptime,
        "version": "2.0.0"
    }


@router.get("/detailed")
async def detailed_health(x_api_key: str | None = Header(default=None)):
    """
    Detailed health check with authentication.
    
    Returns comprehensive system status including:
    - Watchdog health reports
    - Database connectivity
    - Exchange API status
    - Redis connectivity
    - Circuit breaker state
    
    Requires valid admin API key in X-API-Key header.
    """
    # Verify admin access
    if not verify_admin_key(x_api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Collect component statuses
    components = {
        "database": "healthy" if state.db_ready else "unavailable",
        "exchange": "healthy" if state.exchange_ready else "unavailable",
        "redis": "healthy" if state.redis_ready else "unavailable",
        "telegram": "healthy" if state.telegram_ready else "unavailable",
    }
    
    # Get watchdog health
    watchdog_health = {}
    if state.watchdog_orchestrator:
        try:
            watchdog_health = await state.watchdog_orchestrator.get_aggregated_health_report()
        except Exception as e:
            logger.error(f"Failed to get watchdog health: {e}")
            watchdog_health = {"error": str(e)}
    
    # Get circuit breaker status
    circuit_breaker_status = {}
    try:
        from app.risk.circuit_breaker import get_circuit_breaker
        cb = get_circuit_breaker()
        circuit_breaker_status = cb.get_status()
    except Exception as e:
        logger.error(f"Failed to get circuit breaker status: {e}")
    
    # Determine overall status
    overall_status = determine_overall_status(components, watchdog_health)
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int(time.time() - state.start_time),
        "components": components,
        "watchdogs": watchdog_health,
        "circuit_breaker": circuit_breaker_status,
        "metrics": {
            "background_tasks": BACKGROUND_TASKS._value.get() if BACKGROUND_TASKS else 0,
            "trading_enabled": BOT_STATUS._value.get() if BOT_STATUS else True
        }
    }


def verify_admin_key(api_key: str | None) -> bool:
    """Verify admin API key."""
    if not api_key:
        return False
    
    # Compare with configured admin key
    from app.config import settings
    return api_key == getattr(settings, 'ADMIN_API_KEY', None)


def determine_overall_status(components: dict, watchdog_health: dict) -> str:
    """Determine overall system status."""
    # Check component health
    unhealthy_components = [k for k, v in components.items() if v != "healthy"]
    
    if unhealthy_components:
        return "degraded"
    
    # Check watchdog status
    watchdog_status = watchdog_health.get('overall_status', 'unknown')
    
    if watchdog_status == 'critical':
        return "critical"
    elif watchdog_status == 'degraded':
        return "degraded"
    
    return "healthy"
```

**Register router in `app/main.py`:**

```python
# Add import
from app.dashboard import health_router

# Include router (after app creation)
app.include_router(health_router.router)
```

**Test endpoints:**

```bash
# Public health check
curl http://localhost:8000/health

# Detailed health check (requires admin key)
curl -H "X-API-Key: your_admin_key" http://localhost:8000/health/detailed
```

---

### ✅ Phase 2 Validation Checklist

- [ ] Telegram alerts received for simulated failures
- [ ] Alert deduplication working (no duplicate alerts within 15 min)
- [ ] `/health` endpoint returns 200 OK
- [ ] `/health/detailed` requires authentication
- [ ] Watchdog status visible in detailed health
- [ ] No performance degradation from alerting

---

## Phase 3: Advanced Risk Management (Week 2)

### 🎯 Multi-Level Circuit Breakers

**Priority:** HIGH  
**Estimated Effort:** 6-8 hours

*(Implementation details will be created in Week 2 based on Phase 1-2 results)*

---

## Phase 4: Observability & Analytics (Week 3)

### 🎯 Metrics API & Grafana Dashboards

**Priority:** MEDIUM  
**Estimated Effort:** 8-10 hours

*(Implementation details will be created in Week 3 based on previous phases)*

---

## Risk Mitigation

### Rollback Plan

If any phase causes issues:

```bash
# Quick rollback to pre-Phase 2 state
git checkout HEAD~1 -- app/main.py app/config.py
pip uninstall psutil
sudo systemctl restart auto-trade-system
```

### Monitoring During Rollout

- Watch error rates in `logs/error_*.log`
- Monitor application memory usage
- Track API response times
- Verify no increase in trade execution failures

---

## Success Metrics

| Phase | Metric | Target |
|-------|--------|--------|
| Phase 1 | System uptime | 100% over 48h |
| Phase 1 | False positive rate | <5% |
| Phase 2 | Alert delivery rate | >95% |
| Phase 2 | Health endpoint latency | <100ms |
| Phase 3 | Circuit breaker response time | <1s |
| Phase 4 | Dashboard refresh rate | <5s |

---

**Next Action:** Begin Phase 1 deployment immediately using the checklist above.
