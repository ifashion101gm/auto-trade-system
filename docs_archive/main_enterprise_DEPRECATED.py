"""
DEPRECATED - ARCHIVED ON 2026-05-18

This file has been superseded by app/main.py which contains all enterprise features.
Do not use this file. See docs_archive/README.md for details.

Original description:
Enterprise Main - Enhanced FastAPI control plane with session scheduling and admin controls.

This is an ADDITIVE upgrade to the existing main.py that adds:
- Session scheduler integration
- News guard protection
- Telegram message queue
- Admin routes for trading control
- Enhanced metrics

To use: Replace app/main.py with this file after testing.
"""
import asyncio
import signal
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from sqlalchemy import select, func

# Existing imports
from app.dashboard import trading_router, ai_router, cache_router, llm_router
from app.database.connection import init_db, get_session
from app.database.models import PaperTrades
from app.logging_config import logger, log_websocket_event, log_sync_result
from app.config import settings
from app.sync.sync_agent import SyncAgent
from app.recovery.recovery_service import RecoveryService
from app.services.reconciliation_service import ReconciliationService
from app.sync.position_sync import PositionSyncService
from app.notifications.telegram_agent import TelegramAgent
from app.events.event_bus import event_bus
from app.events.event_store import event_store
from app.risk.risk_engine import RiskEngine
from app.monitoring.prometheus_metrics import get_metrics_collector
from app.runtime.task_supervisor import TaskSupervisor
from app.risk.circuit_breaker import get_circuit_breaker

# New enterprise imports
from app.runtime.session_scheduler import SessionScheduler
from app.runtime.news_guard import NewsGuard

# ============================================================================
# METRICS REGISTRY
# ============================================================================

CUSTOM_REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
    registry=CUSTOM_REGISTRY,
)

HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    registry=CUSTOM_REGISTRY,
)

BOT_STATUS = Gauge(
    "bot_trading_enabled",
    "1 if trading enabled else 0",
    registry=CUSTOM_REGISTRY,
)

BACKGROUND_TASKS = Gauge(
    "background_tasks_running",
    "Number of running background tasks",
    registry=CUSTOM_REGISTRY,
)

# Legacy metrics (for backward compatibility)
REQUEST_COUNT, REQUEST_LATENCY, WEBSOCKET_CONNECTED, EVENT_BUS_QUEUE_SIZE = None, None, None, None

def get_or_create_metrics():
    """Initialize legacy metrics."""
    global REQUEST_COUNT, REQUEST_LATENCY, WEBSOCKET_CONNECTED, EVENT_BUS_QUEUE_SIZE
    
    try:
        REQUEST_COUNT = CUSTOM_REGISTRY._names_to_collectors.get('http_requests_total')
        REQUEST_LATENCY = CUSTOM_REGISTRY._names_to_collectors.get('http_request_duration_seconds')
    except:
        pass
    
    return REQUEST_COUNT, REQUEST_LATENCY, None, None

REQUEST_COUNT, REQUEST_LATENCY, _, _ = get_or_create_metrics()

# ============================================================================
# APP STATE (Enterprise Pattern)
# ============================================================================

class AppState:
    """Centralized application state management."""
    
    def __init__(self):
        self.start_time = time.time()
        self.shutdown_event = asyncio.Event()
        
        # Trading control
        self.trading_enabled = True
        self.daily_loss_lock = False
        self.last_error = None
        
        # Service readiness
        self.db_ready = False
        self.redis_ready = False
        self.exchange_ready = False
        self.telegram_ready = False
        
        # Telegram queue (non-blocking)
        self.telegram_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # Enterprise components
        self.session_scheduler: SessionScheduler = SessionScheduler()
        self.news_guard: NewsGuard = NewsGuard(default_buffer_minutes=30)
        self.task_supervisor: TaskSupervisor = None
        
        # Legacy services (for backward compatibility)
        self.sync_agent = None
        self.telegram_agent = None
        self.position_sync_service = None
        self.heartbeat_monitor = None
        self.reconciliation_engine = None

state = AppState()

# ============================================================================
# HELPERS
# ============================================================================

def utc_now():
    """Get current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()

def uptime_seconds():
    """Get application uptime in seconds."""
    return int(time.time() - state.start_time)

def require_admin(x_api_key: str = Header(None)):
    """
    Require admin API key for protected routes.
    
    Args:
        x_api_key: API key from header
        
    Raises:
        HTTPException: If key is missing or invalid
    """
    # In production, use environment variable
    admin_key = getattr(settings, 'ADMIN_API_KEY', 'CHANGE_ME_IN_PRODUCTION')
    
    if not x_api_key or x_api_key != admin_key:
        raise HTTPException(status_code=401, detail="Unauthorized - Admin API key required")

async def safe_loop(name: str, coro_factory: Callable, max_failures: int = 5):
    """
    Supervisor wrapper for resilient background loops.
    Automatically restarts task if it crashes (up to max_failures).
    
    Args:
        name: Task identifier
        coro_factory: Async function to run
        max_failures: Maximum failures before stopping
    """
    failures = 0
    
    while not state.shutdown_event.is_set():
        try:
            await coro_factory()
            failures = 0  # Reset on success
            
        except asyncio.CancelledError:
            logger.info(f"Task '{name}' cancelled")
            break
            
        except Exception as e:
            failures += 1
            state.last_error = f"{name}: {str(e)}"
            
            logger.error(f"Task '{name}' failed ({failures}/{max_failures}): {e}", exc_info=True)
            
            if failures >= max_failures:
                logger.critical(f"Task '{name}' exceeded max failures, disabling trading")
                state.trading_enabled = False
                BOT_STATUS.set(0)
                break
            
            # Exponential backoff
            await asyncio.sleep(min(5 * (2 ** failures), 60))

# ============================================================================
# BACKGROUND WORKERS
# ============================================================================

async def session_scheduler_worker():
    """Updates trading_enabled based on session windows."""
    while not state.shutdown_event.is_set():
        try:
            # Check session
            trading_allowed = state.session_scheduler.is_trading_allowed()
            
            # Check news guard
            news_safe = state.news_guard.is_trading_safe()
            
            # Update trading state
            state.trading_enabled = trading_allowed and news_safe and not state.daily_loss_lock
            BOT_STATUS.set(1 if state.trading_enabled else 0)
            
            logger.debug(
                f"Session update: trading={state.trading_enabled}, "
                f"session={state.session_scheduler.get_current_session().value}"
            )
            
        except Exception as e:
            logger.error(f"Session scheduler error: {e}")
        
        await asyncio.sleep(30)  # Check every 30 seconds

async def telegram_queue_worker():
    """Processes queued Telegram messages (non-blocking)."""
    while not state.shutdown_event.is_set():
        try:
            # Wait for message with timeout
            msg = await asyncio.wait_for(state.telegram_queue.get(), timeout=2)
            
            # Send via Telegram agent
            if state.telegram_agent:
                try:
                    await state.telegram_agent.send_message(msg)
                except Exception as e:
                    logger.error(f"Failed to send Telegram message: {e}")
                    
        except asyncio.TimeoutError:
            pass  # No messages, continue loop
        except Exception as e:
            logger.error(f"Telegram worker error: {e}")
            await asyncio.sleep(5)

async def heartbeat_worker():
    """Periodic heartbeat for monitoring."""
    while not state.shutdown_event.is_set():
        try:
            # Log heartbeat
            logger.debug(
                f"Heartbeat: uptime={uptime_seconds()}s, "
                f"trading={state.trading_enabled}, "
                f"tasks={len(state.task_supervisor.tasks) if state.task_supervisor else 0}"
            )
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        
        await asyncio.sleep(15)

# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

async def init_services():
    """Initialize all services."""
    logger.info("🚀 Initializing enterprise services...")
    
    # Database
    await init_db()
    state.db_ready = True
    logger.info("✅ Database ready")
    
    # EventBus
    await event_bus.start_processing()
    logger.info("✅ EventBus started")
    
    # Subscribe EventStore
    async def persist_critical_events(event):
        async with get_session() as db_session:
            await event_store.persist_event(event, db_session)
    
    from app.events.event_types import (
        ORDER_FILLED, ORDER_PARTIALLY_FILLED, ORDER_CANCELLED,
        POSITION_UPDATED, SYNC_MISMATCH, SYNC_REPAIRED
    )
    
    for event_type in [ORDER_FILLED, ORDER_PARTIALLY_FILLED, ORDER_CANCELLED,
                       POSITION_UPDATED, SYNC_MISMATCH, SYNC_REPAIRED]:
        event_bus.subscribe(event_type, persist_critical_events, priority=20)
    
    # Initialize agents
    state.sync_agent = SyncAgent()
    state.telegram_agent = TelegramAgent()
    state.telegram_ready = True
    logger.info("✅ Agents initialized")
    
    # Recovery
    async with get_session() as db_session:
        recovery_service = RecoveryService()
        await recovery_service.recover_on_startup(db_session)
    logger.info("✅ Recovery completed")
    
    # Task Supervisor
    state.task_supervisor = TaskSupervisor(max_restart_attempts=3)
    logger.info("✅ Task Supervisor initialized")
    
    # Start supervised tasks (legacy)
    state.task_supervisor.create_task(
        state.sync_agent.start_listening(symbols=['XAU/USDT:USDT'], db_session_factory=get_session),
        name="sync_agent",
        critical=True,
        restart_delay=5.0
    )
    
    # Position sync
    state.position_sync_service = PositionSyncService(testnet=True)
    state.task_supervisor.create_task(
        state.position_sync_service.start(get_session),
        name="position_sync",
        critical=True,
        restart_delay=5.0
    )
    
    # Heartbeat monitor
    from app.heartbeat_monitor import HeartbeatMonitor
    state.heartbeat_monitor = HeartbeatMonitor()
    state.task_supervisor.create_task(
        state.heartbeat_monitor.start(),
        name="heartbeat_monitor",
        critical=True,
        restart_delay=2.0
    )
    
    # Reconciliation
    reconciliation_service = ReconciliationService()
    async def reconciliation_loop():
        while True:
            try:
                async with get_session() as db_session:
                    await reconciliation_service.reconcile(mode='DEMO', db_session=db_session)
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")
            await asyncio.sleep(120)
    
    state.task_supervisor.create_task(
        reconciliation_loop(),
        name="reconciliation",
        critical=False,
        restart_delay=10.0
    )
    
    # Order reconciliation engine
    from app.execution.reconciliation_engine import OrderReconciliationEngine
    state.reconciliation_engine = OrderReconciliationEngine(
        exchange_name=settings.ACTIVE_EXCHANGE,
        use_testnet=settings.BINANCE_TESTNET,
        reconciliation_interval=60,
        auto_repair_safe=True
    )
    state.task_supervisor.create_task(
        state.reconciliation_engine.start(get_session),
        name="order_reconciliation",
        critical=False,
        restart_delay=10.0
    )
    
    # Enterprise workers (safe_loop pattern)
    asyncio.create_task(safe_loop("session_scheduler", session_scheduler_worker))
    asyncio.create_task(safe_loop("telegram_queue", telegram_queue_worker))
    asyncio.create_task(safe_loop("heartbeat", heartbeat_worker))
    
    state.exchange_ready = True
    logger.info("✅ All services initialized")

async def close_services():
    """Gracefully shutdown all services."""
    logger.info("🛑 Shutting down services...")
    
    state.shutdown_event.set()
    
    # Stop task supervisor
    if state.task_supervisor:
        await state.task_supervisor.shutdown(timeout=10)
        logger.info("✅ Task supervisor stopped")
    
    # Stop reconciliation engine
    if state.reconciliation_engine:
        state.reconciliation_engine.stop()
    
    # Stop position sync
    if state.position_sync_service:
        state.position_sync_service.stop()
        await state.position_sync_service.close()
    
    # Stop heartbeat
    if state.heartbeat_monitor:
        await state.heartbeat_monitor.stop()
    
    # Stop sync agent
    if state.sync_agent:
        await state.sync_agent.stop()
    
    # Stop EventBus
    await event_bus.stop_processing()
    
    logger.info("👋 All services stopped")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    await init_services()
    
    logger.info("🎉 Auto Trade System Enterprise fully operational!")
    logger.info(f"   Dashboard: http://localhost:8000/docs")
    logger.info(f"   Metrics: http://localhost:8000/metrics/prometheus")
    logger.info(f"   Health: http://localhost:8000/health/deep")
    logger.info(f"   Admin: http://localhost:8000/admin/state (requires API key)")
    
    yield
    
    await close_services()

# ============================================================================
# APP
# ============================================================================

app = FastAPI(
    title="Auto Trade System - Enterprise",
    description="Production-grade gold trading bot with session scheduling and admin controls",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# MIDDLEWARE
# ============================================================================

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track HTTP metrics."""
    start = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start
    
    HTTP_REQUESTS.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    ).inc()
    
    HTTP_LATENCY.observe(duration)
    
    return response

# ============================================================================
# ROUTES
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Auto Trade System - Enterprise",
        "version": "3.0.0",
        "time": utc_now(),
        "uptime_sec": uptime_seconds(),
    }

@app.get("/health")
async def health():
    """Basic health check."""
    return {
        "status": "healthy",
        "uptime_sec": uptime_seconds(),
        "trading_enabled": state.trading_enabled,
    }

@app.get("/health/deep")
async def health_deep():
    """Comprehensive health check."""
    return {
        "status": "healthy",
        "db": state.db_ready,
        "redis": state.redis_ready,
        "exchange": state.exchange_ready,
        "telegram": state.telegram_ready,
        "tasks": list(state.task_supervisor.tasks.keys()) if state.task_supervisor else [],
        "last_error": state.last_error,
        "uptime_sec": uptime_seconds(),
        "circuit_breaker": get_circuit_breaker().get_status(),
        "session": state.session_scheduler.get_session_info(),
        "news_guard": state.news_guard.get_status(),
    }

@app.get("/metrics/prometheus")
async def metrics_prometheus():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(CUSTOM_REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )

@app.get("/metrics/json")
async def metrics_json():
    """JSON metrics endpoint."""
    return {
        "trading_enabled": state.trading_enabled,
        "tasks_running": len(state.task_supervisor.tasks) if state.task_supervisor else 0,
        "uptime_sec": uptime_seconds(),
        "last_error": state.last_error,
        "session": state.session_scheduler.get_session_info(),
    }

# Include existing routers
app.include_router(trading_router, prefix="/api/v1", tags=["trading"])
app.include_router(ai_router, prefix="/api/v1", tags=["ai-orchestration"])
app.include_router(cache_router, prefix="/api/v1", tags=["cache-management"])
app.include_router(llm_router, prefix="/api/v1", tags=["llm-optimization"])

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.post("/admin/trading/enable")
async def enable_trading(x_api_key: str = Header(None)):
    """Enable trading (admin only)."""
    require_admin(x_api_key)
    
    state.daily_loss_lock = False
    state.trading_enabled = True
    BOT_STATUS.set(1)
    
    logger.info("🟢 Trading ENABLED by admin")
    
    return {"ok": True, "trading_enabled": True}

@app.post("/admin/trading/disable")
async def disable_trading(x_api_key: str = Header(None)):
    """Disable trading (admin only)."""
    require_admin(x_api_key)
    
    state.trading_enabled = False
    BOT_STATUS.set(0)
    
    logger.warning("🔴 Trading DISABLED by admin")
    
    return {"ok": True, "trading_enabled": False}

@app.post("/admin/circuit-breaker/reset")
async def reset_circuit_breaker(x_api_key: str = Header(None)):
    """Reset circuit breaker (admin only)."""
    require_admin(x_api_key)
    
    cb = get_circuit_breaker()
    cb.reset("Manual reset by admin")
    
    logger.info("🔄 Circuit breaker RESET by admin")
    
    return {"ok": True, "circuit_breaker": cb.get_status()}

@app.post("/admin/telegram/test")
async def telegram_test(x_api_key: str = Header(None)):
    """Queue test Telegram message (admin only)."""
    require_admin(x_api_key)
    
    await state.telegram_queue.put("🧪 Test message from enterprise admin panel.")
    
    return {"queued": True, "queue_size": state.telegram_queue.qsize()}

@app.get("/admin/state")
async def admin_state(x_api_key: str = Header(None)):
    """Get full system state (admin only)."""
    require_admin(x_api_key)
    
    return {
        "tasks": list(state.task_supervisor.tasks.keys()) if state.task_supervisor else [],
        "trading_enabled": state.trading_enabled,
        "daily_loss_lock": state.daily_loss_lock,
        "last_error": state.last_error,
        "uptime_sec": uptime_seconds(),
        "session": state.session_scheduler.get_session_info(),
        "news_guard": state.news_guard.get_status(),
        "circuit_breaker": get_circuit_breaker().get_status(),
    }

@app.get("/admin/session/info")
async def session_info():
    """Get session scheduler information (public)."""
    return state.session_scheduler.get_session_info()

@app.get("/admin/news/status")
async def news_status():
    """Get news guard status (public)."""
    return state.news_guard.get_status()

# ============================================================================
# SIGNAL HANDLING
# ============================================================================

def install_signal_handlers():
    """Install graceful shutdown signal handlers."""
    loop = asyncio.get_event_loop()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(graceful_shutdown(s))
        )

async def graceful_shutdown(sig):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig.name}, initiating graceful shutdown...")
    state.shutdown_event.set()

# Install signal handlers when running directly
import sys
if __name__ == "__main__":
    install_signal_handlers()
