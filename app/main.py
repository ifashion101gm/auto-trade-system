"""
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

# Phase 2: Self-healing watchdogs
from app.self_healing.watchdogs import WatchdogOrchestrator, QueueWatchdog

# Phase 3: Resilience Platform
try:
    from app.resilience import (
        ResilienceManager,
        SystemStateMachine,
        RecoveryExecutor,
    )
    RESILIENCE_PLATFORM_AVAILABLE = True
except ImportError:
    RESILIENCE_PLATFORM_AVAILABLE = False
    logger.warning("Resilience platform not available - using legacy fallback")

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

# Trading Performance Metrics
TRADES_TOTAL = Counter(
    "trades_total",
    "Total number of trades executed",
    ["side", "symbol", "outcome"],  # side: long/short, outcome: win/loss/breakeven
    registry=CUSTOM_REGISTRY,
)

TRADES_WINNING = Counter(
    "trades_winning_total",
    "Total number of winning trades",
    ["side", "symbol"],
    registry=CUSTOM_REGISTRY,
)

TRADES_LOSING = Counter(
    "trades_losing_total",
    "Total number of losing trades",
    ["side", "symbol"],
    registry=CUSTOM_REGISTRY,
)

PNL_CUMULATIVE = Gauge(
    "pnl_cumulative_usd",
    "Cumulative P&L in USD",
    registry=CUSTOM_REGISTRY,
)

PNL_PER_TRADE = Histogram(
    "pnl_per_trade_usd",
    "P&L per trade distribution",
    buckets=[-50, -20, -10, -5, -2, -1, 0, 1, 2, 5, 10, 20, 50, 100],
    registry=CUSTOM_REGISTRY,
)

WIN_RATE = Gauge(
    "win_rate_percent",
    "Current win rate percentage",
    registry=CUSTOM_REGISTRY,
)

SHARPE_RATIO = Gauge(
    "sharpe_ratio",
    "Sharpe ratio (rolling)",
    registry=CUSTOM_REGISTRY,
)

# Risk Management Metrics
RISK_EXPOSURE_USD = Gauge(
    "risk_exposure_usd",
    "Current risk exposure in USD",
    registry=CUSTOM_REGISTRY,
)

DRAWDOWN_CURRENT = Gauge(
    "drawdown_current_percent",
    "Current drawdown percentage",
    registry=CUSTOM_REGISTRY,
)

DRAWDOWN_MAX = Gauge(
    "drawdown_max_percent",
    "Maximum drawdown percentage",
    registry=CUSTOM_REGISTRY,
)

CONSECUTIVE_LOSSES = Gauge(
    "consecutive_losses",
    "Current consecutive losing trades",
    registry=CUSTOM_REGISTRY,
)

# Execution Metrics
EXECUTION_LATENCY = Histogram(
    "execution_latency_seconds",
    "Order execution latency",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    registry=CUSTOM_REGISTRY,
)

ORDERS_TOTAL = Counter(
    "orders_total",
    "Total number of orders placed",
    ["order_type", "status"],  # market/limit, filled/rejected/cancelled
    registry=CUSTOM_REGISTRY,
)

ORDERS_REJECTED = Counter(
    "orders_rejected_total",
    "Total number of rejected orders",
    ["reason"],
    registry=CUSTOM_REGISTRY,
)

SLIPPAGE_AVG = Gauge(
    "slippage_avg_percent",
    "Average slippage percentage",
    registry=CUSTOM_REGISTRY,
)

# System Health Metrics
POSITIONS_OPEN = Gauge(
    "positions_open",
    "Number of open positions",
    registry=CUSTOM_REGISTRY,
)

BALANCE_TOTAL = Gauge(
    "balance_total_usd",
    "Total account balance in USD",
    registry=CUSTOM_REGISTRY,
)

BALANCE_AVAILABLE = Gauge(
    "balance_available_usd",
    "Available balance in USD",
    registry=CUSTOM_REGISTRY,
)

API_LATENCY = Histogram(
    "api_latency_seconds",
    "Exchange API call latency",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
    registry=CUSTOM_REGISTRY,
)

ERRORS_TOTAL = Counter(
    "errors_total",
    "Total number of errors",
    ["error_type", "severity"],  # connection/execution/risk, warning/critical
    registry=CUSTOM_REGISTRY,
)

# Infrastructure Health Metrics
REDIS_CONNECTION_STATUS = Gauge(
    "redis_connection_status",
    "Redis connection status (1=connected, 0=disconnected)",
    registry=CUSTOM_REGISTRY,
)

DATABASE_CONNECTION_POOL_SIZE = Gauge(
    "database_connection_pool_size",
    "Database connection pool size",
    ["pool_type"],  # active/idle
    registry=CUSTOM_REGISTRY,
)

WEBSOCKET_UPTIME_SECONDS = Gauge(
    "websocket_uptime_seconds",
    "WebSocket connection uptime in seconds",
    ["exchange"],
    registry=CUSTOM_REGISTRY,
)

WEBSOCKET_RECONNECT_TOTAL = Counter(
    "websocket_reconnect_total",
    "Total WebSocket reconnection attempts",
    ["exchange"],
    registry=CUSTOM_REGISTRY,
)

# AI/LLM Layer Metrics
LLM_TOKEN_USAGE_TOTAL = Counter(
    "llm_token_usage_total",
    "Total LLM token usage",
    ["provider", "model"],
    registry=CUSTOM_REGISTRY,
)

AI_CONFIDENCE_SCORES = Histogram(
    "ai_confidence_scores",
    "AI confidence score distribution",
    ["agent_type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=CUSTOM_REGISTRY,
)

# WebSocket & Event Bus Metrics
WEBSOCKET_CONNECTED = Gauge(
    "websocket_connected",
    "WebSocket connection status (1=connected, 0=disconnected)",
    ["exchange"],
    registry=CUSTOM_REGISTRY,
)

WEBSOCKET_MESSAGE_LATENCY = Histogram(
    "websocket_message_latency_ms",
    "WebSocket message latency in milliseconds",
    ["exchange", "message_type"],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
    registry=CUSTOM_REGISTRY,
)

EVENT_BUS_QUEUE_SIZE = Gauge(
    "event_bus_queue_size",
    "Current event bus queue depth",
    registry=CUSTOM_REGISTRY,
)

# Trade Execution Metrics
TRADE_EXECUTION_LATENCY = Histogram(
    "trade_execution_latency_ms",
    "Trade execution latency in milliseconds",
    ["exchange", "symbol", "side"],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
    registry=CUSTOM_REGISTRY,
)

# Data Integrity Metrics
DESYNC_EVENTS_TOTAL = Counter(
    "desync_events_total",
    "Total synchronization mismatch events",
    ["exchange", "mismatch_type"],
    registry=CUSTOM_REGISTRY,
)

# Risk Management Metrics
RISK_VIOLATIONS_TOTAL = Counter(
    "risk_violations_total",
    "Total risk limit violations",
    ["violation_type", "risk_level"],
    registry=CUSTOM_REGISTRY,
)

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half-open, 2=open)",
    ["component"],
    registry=CUSTOM_REGISTRY,
)

# Legacy metrics placeholder (now properly defined above)
REQUEST_COUNT = None
REQUEST_LATENCY = None

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
        
        # Phase 2: Self-healing watchdogs
        self.watchdog_orchestrator: WatchdogOrchestrator = None
        self.queue_watchdog: QueueWatchdog = None
        
        # Resilience Platform (Phase 3)
        self.resilience_manager = None
        self.state_machine = None
        self.recovery_executor = None
        
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

def require_admin(x_api_key: str | None = Header(default=None)):
    """
    Require admin API key for protected routes.
    
    Args:
        x_api_key: API key from header
        
    Raises:
        HTTPException: If key is missing or invalid
    """
    # SECURITY: ADMIN_API_KEY is validated at startup - no fallback to placeholder
    admin_key = settings.ADMIN_API_KEY
    
    if not admin_key:
        # This should never happen due to startup validation, but defense in depth
        logger.critical("ADMIN_API_KEY is not set - this indicates a configuration error")
        raise HTTPException(status_code=500, detail="Server configuration error - contact administrator")
    
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
            # Record task processing for QueueWatchdog
            # Use orchestrator's watchdog if available, fallback to state.queue_watchdog
            watchdog = None
            if state.watchdog_orchestrator and hasattr(state.watchdog_orchestrator, 'queue_watchdog'):
                watchdog = state.watchdog_orchestrator.queue_watchdog
            elif state.queue_watchdog:
                watchdog = state.queue_watchdog
            
            if watchdog:
                watchdog.record_task_processed()
            
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
            
            # Record task processing for QueueWatchdog
            # Use orchestrator's watchdog if available, fallback to state.queue_watchdog
            watchdog = None
            if state.watchdog_orchestrator and hasattr(state.watchdog_orchestrator, 'queue_watchdog'):
                watchdog = state.watchdog_orchestrator.queue_watchdog
            elif state.queue_watchdog:
                watchdog = state.queue_watchdog
            
            if watchdog:
                watchdog.record_task_processed()
            
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
            # Record task processing for QueueWatchdog
            # Use orchestrator's watchdog if available, fallback to state.queue_watchdog
            watchdog = None
            if state.watchdog_orchestrator and hasattr(state.watchdog_orchestrator, 'queue_watchdog'):
                watchdog = state.watchdog_orchestrator.queue_watchdog
            elif state.queue_watchdog:
                watchdog = state.queue_watchdog
            
            if watchdog:
                watchdog.record_task_processed()
            
            # Log heartbeat
            logger.debug(
                f"Heartbeat: uptime={uptime_seconds()}s, "
                f"trading={state.trading_enabled}, "
                f"tasks={len(state.task_supervisor.tasks) if state.task_supervisor else 0}"
            )
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        
        await asyncio.sleep(15)

def _initialize_metrics_defaults():
    """
    Initialize all Prometheus metrics with default values.
    This ensures metrics are visible in Grafana even before any events occur.
    """
    try:
        # WebSocket metrics - initialize to 0 (disconnected) until connected
        WEBSOCKET_CONNECTED.labels(exchange="mexc").set(0)
        WEBSOCKET_CONNECTED.labels(exchange="binance").set(0)
        WEBSOCKET_CONNECTED.labels(exchange="bybit").set(0)
        
        # Event bus queue - initialize to 0
        EVENT_BUS_QUEUE_SIZE.set(0)
        
        # Circuit breaker - initialize to 0 (closed/healthy)
        CIRCUIT_BREAKER_STATE.labels(component="execution_engine").set(0)
        CIRCUIT_BREAKER_STATE.labels(component="risk_engine").set(0)
        CIRCUIT_BREAKER_STATE.labels(component="exchange_adapter").set(0)
        
        # WebSocket reconnect - initialize to 0
        WEBSOCKET_RECONNECT_TOTAL.labels(exchange="mexc").inc(0)
        WEBSOCKET_RECONNECT_TOTAL.labels(exchange="binance").inc(0)
        WEBSOCKET_RECONNECT_TOTAL.labels(exchange="bybit").inc(0)
        
        # Desync events - initialize to 0
        DESYNC_EVENTS_TOTAL.labels(exchange="mexc", mismatch_type="position").inc(0)
        DESYNC_EVENTS_TOTAL.labels(exchange="mexc", mismatch_type="order").inc(0)
        DESYNC_EVENTS_TOTAL.labels(exchange="mexc", mismatch_type="balance").inc(0)
        
        # Risk violations - initialize to 0
        RISK_VIOLATIONS_TOTAL.labels(violation_type="max_drawdown", risk_level="critical").inc(0)
        RISK_VIOLATIONS_TOTAL.labels(violation_type="position_size", risk_level="warning").inc(0)
        RISK_VIOLATIONS_TOTAL.labels(violation_type="daily_loss", risk_level="warning").inc(0)
        
        logger.info("✅ All Prometheus metrics initialized with default values")
        
    except Exception as e:
        logger.error(f"Failed to initialize metrics defaults: {e}")

# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

async def init_services():
    """Initialize all services."""
    logger.info(" Initializing enterprise services...")
    
    # SECURITY BASELINE: Validate ADMIN_API_KEY before initializing any services
    # This ensures the application crashes on placeholder/insecure values
    try:
        settings.validate_admin_api_key()
        logger.info("✅ ADMIN_API_KEY validation passed (security baseline)")
    except ValueError as e:
        logger.critical(f"🚨 SECURITY VALIDATION FAILED: {e}")
        logger.critical("Application cannot start with insecure ADMIN_API_KEY configuration")
        raise SystemExit(1) from e
    
    # Database
    await init_db()
    state.db_ready = True
    logger.info("✅ Database ready")
    
    # Initialize metrics with default values
    _initialize_metrics_defaults()
    
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

    # Initialize global KillSwitch for admin control
    try:
        from app.infra.kill_switch import KillSwitch
        state.kill_switch = KillSwitch(notifier=state.telegram_agent, persist_path=getattr(settings, 'KILL_SWITCH_STATE_FILE', '.kill_switch_state.json'))
        logger.info("✅ KillSwitch initialized and attached to app state")
    except Exception as e:
        state.kill_switch = None
        logger.warning(f"KillSwitch not initialized: {e}")
    
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

    # Exchange preflight checks and attach exchange manager to state
    try:
        from app.infra.exchange_manager import UnifiedExchangeManager

        state.exchange_manager = UnifiedExchangeManager(
            exchange_name=settings.ACTIVE_EXCHANGE,
            use_testnet=settings.BINANCE_TESTNET
        )

        # If using Bybit, perform Pybit-specific preflight checks
        if settings.ACTIVE_EXCHANGE.lower() == 'bybit':
            try:
                client = getattr(state.exchange_manager, 'client', None)
                if client and hasattr(client, 'validate_clock_sync'):
                    ok = await client.validate_clock_sync()
                    if not ok:
                        logger.warning("Bybit clock sync check failed - review system clock")

                # Fetch balance for monitoring
                try:
                    bal = await state.exchange_manager.fetch_balance()
                    logger.info(f"Exchange balance preflight: {bal.get('total_usdt', bal)}")
                except Exception as e:
                    logger.warning(f"Failed to fetch balance during preflight: {e}")

                # Set conservative leverage for primary trading symbol
                primary = settings.PRIMARY_TRADING_SYMBOL
                try:
                    await state.exchange_manager.set_leverage(primary, settings.GOLD_MAX_LEVERAGE)
                    logger.info(f"Set default leverage {settings.GOLD_MAX_LEVERAGE}x for {primary}")
                except Exception as e:
                    logger.warning(f"Failed to set default leverage on preflight: {e}")

            except Exception as e:
                logger.warning(f"Bybit preflight checks encountered an issue: {e}")

        logger.info("✅ Exchange manager attached to application state")
    except Exception as e:
        state.exchange_manager = None
        logger.warning(f"Exchange manager not attached during init: {e}")
    
    # Phase 2: Initialize self-healing watchdogs
    logger.info("🔍 Initializing self-healing watchdogs...")
    
    # Phase 3: Initialize resilience platform (if available)
    if RESILIENCE_PLATFORM_AVAILABLE:
        logger.info("🛡️ Initializing resilience platform...")
        
        # 1. Create state machine
        state.state_machine = SystemStateMachine(
            notifier=state.telegram_agent,  # Use existing Telegram notifier
            event_bus=event_bus
        )
        logger.info("✅ State machine initialized")
        
        # 2. Create recovery executor
        state.recovery_executor = RecoveryExecutor(
            cooldown_manager=None,  # Created internally
            notifier=state.telegram_agent
        )
        logger.info("✅ Recovery executor initialized")
        
        # 3. Create resilience manager (central hub)
        state.resilience_manager = ResilienceManager(
            state_machine=state.state_machine,
            recovery_executor=state.recovery_executor,
            event_bus=event_bus,
            notifier=state.telegram_agent
        )
        logger.info("✅ Resilience manager initialized")
    else:
        logger.warning("⚠️ Resilience platform not available - using legacy mode")
    
    # 4. Initialize watchdog orchestrator with resilience manager
    state.watchdog_orchestrator = WatchdogOrchestrator(
        exchange_manager=None,  # Will be set when exchange is initialized
        db_session_factory=get_session,
        resilience_manager=state.resilience_manager,  # Pass resilience manager!
        api_check_interval=getattr(settings, 'API_WATCHDOG_CHECK_INTERVAL_SEC', 30),
        db_check_interval=getattr(settings, 'DB_WATCHDOG_CHECK_INTERVAL_SEC', 60),
        memory_check_interval=getattr(settings, 'MEMORY_WATCHDOG_CHECK_INTERVAL_SEC', 120),
        queue_check_interval=getattr(settings, 'QUEUE_WATCHDOG_CHECK_INTERVAL_SEC', 60)
    )
    logger.info("✅ Self-healing watchdogs initialized")
    
    # Initialize global QueueWatchdog for background workers
    state.queue_watchdog = QueueWatchdog(
        max_task_age_sec=300,
        max_queue_depth=100,
        check_interval_sec=60
    )
    logger.info("✅ Global QueueWatchdog initialized for background workers")
    
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

async def update_infrastructure_metrics():
    """
    Background task to periodically update infrastructure metrics.
    Runs every 10 seconds to keep Prometheus metrics fresh.
    """
    import redis.asyncio as aioredis
    from app.database.connection import engine, db_health_status
    
    while True:
        try:
            await asyncio.sleep(10)
            
            # Update Redis connection status
            try:
                r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
                await r.ping()
                REDIS_CONNECTION_STATUS.set(1)
                await r.close()
            except Exception:
                REDIS_CONNECTION_STATUS.set(0)
            
            # Update database connection pool metrics
            try:
                pool = engine.pool
                if hasattr(pool, 'status'):
                    # Get pool statistics
                    pool_status = pool.status()
                    # Parse pool status to extract active/idle counts
                    # Format varies by SQLAlchemy version
                    DATABASE_CONNECTION_POOL_SIZE.labels(pool_type="active").set(
                        getattr(pool, '_checkedin', 0)
                    )
                    DATABASE_CONNECTION_POOL_SIZE.labels(pool_type="idle").set(
                        getattr(pool, '_overflow', 0)
                    )
                else:
                    # Fallback: set to 0 if we can't get stats
                    DATABASE_CONNECTION_POOL_SIZE.labels(pool_type="active").set(0)
                    DATABASE_CONNECTION_POOL_SIZE.labels(pool_type="idle").set(0)
            except Exception:
                DATABASE_CONNECTION_POOL_SIZE.labels(pool_type="active").set(0)
                DATABASE_CONNECTION_POOL_SIZE.labels(pool_type="idle").set(0)
            
            # Note: WebSocket uptime and reconnects are updated by WebSocket managers
            # when events occur (see websocket/manager.py and infra/websocket_manager.py)
            
            # Note: LLM token usage and AI confidence scores are updated by AI agents
            # when they make predictions (see app/ai/ directory)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error updating infrastructure metrics: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    await init_services()
    
    # Phase 2: Start self-healing watchdogs
    if state.watchdog_orchestrator:
        await state.watchdog_orchestrator.start_all_watchdogs()
        logger.info("✅ Self-healing watchdogs started")
    
    # Start infrastructure metrics updater
    metrics_task = asyncio.create_task(update_infrastructure_metrics())
    logger.info("✅ Infrastructure metrics updater started")
    
    logger.info("🎉 Auto Trade System Enterprise fully operational!")
    logger.info(f"   Dashboard: http://localhost:8000/docs")
    logger.info(f"   Metrics: http://localhost:8000/metrics/prometheus")
    logger.info(f"   Health: http://localhost:8000/health/deep")
    logger.info(f"   Admin: http://localhost:8000/admin/state (requires API key)")
    
    yield
    
    # Stop infrastructure metrics updater
    metrics_task.cancel()
    try:
        await metrics_task
    except asyncio.CancelledError:
        pass
    
    # Phase 2: Stop self-healing watchdogs
    if state.watchdog_orchestrator:
        await state.watchdog_orchestrator.stop_all_watchdogs()
        logger.info("✅ Self-healing watchdogs stopped")
    
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

# Phase 2: Health check and monitoring routes
try:
    from app.dashboard.health_api import register_health_routes
    register_health_routes(app)
    logger.info("✅ Health check and monitoring API registered")
except ImportError as e:
    logger.warning(f"Health API not available (will be added in Phase 2): {e}")

# Phase 3: Resilience platform routes
try:
    from app.dashboard.resilience_api import router as resilience_router
    app.include_router(resilience_router, prefix="/api/v1")
    logger.info("✅ Resilience platform API registered")
except ImportError as e:
    logger.warning(f"Resilience API not available: {e}")

# Control Panel Dashboard
try:
    from app.dashboard.control_panel import router as control_panel_router
    app.include_router(control_panel_router)
    logger.info("✅ Control panel dashboard registered at /dashboard")
except ImportError as e:
    logger.warning(f"Control panel not available: {e}")

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.post("/admin/trading/enable")
async def enable_trading(x_api_key: str | None = Header(default=None)):
    """Enable trading (admin only)."""
    require_admin(x_api_key)
    
    state.daily_loss_lock = False
    state.trading_enabled = True
    BOT_STATUS.set(1)
    
    logger.info("🟢 Trading ENABLED by admin")
    
    return {"ok": True, "trading_enabled": True}

@app.post("/admin/trading/disable")
async def disable_trading(x_api_key: str | None = Header(default=None)):
    """Disable trading (admin only)."""
    require_admin(x_api_key)
    
    state.trading_enabled = False
    BOT_STATUS.set(0)
    
    logger.warning("🔴 Trading DISABLED by admin")
    
    return {"ok": True, "trading_enabled": False}

@app.post("/admin/circuit-breaker/reset")
async def reset_circuit_breaker(x_api_key: str | None = Header(default=None)):
    """Reset circuit breaker (admin only)."""
    require_admin(x_api_key)
    
    cb = get_circuit_breaker()
    cb.reset("Manual reset by admin")
    
    logger.info("🔄 Circuit breaker RESET by admin")
    
    return {"ok": True, "circuit_breaker": cb.get_status()}

@app.post("/admin/telegram/test")
async def telegram_test(x_api_key: str | None = Header(default=None)):
    """Queue test Telegram message (admin only)."""
    require_admin(x_api_key)
    
    await state.telegram_queue.put("🧪 Test message from enterprise admin panel.")
    
    return {"queued": True, "queue_size": state.telegram_queue.qsize()}

@app.get("/admin/state")
async def admin_state(x_api_key: str | None = Header(default=None)):
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


@app.post("/admin/kill-switch/engage")
async def admin_kill_switch_engage(payload: Dict[str, str], x_api_key: str | None = Header(default=None)):
    """Engage global kill switch (admin only)."""
    require_admin(x_api_key)

    if not state.kill_switch:
        raise HTTPException(status_code=500, detail="Kill switch not initialized")

    actor = payload.get('actor', 'admin')
    reason = payload.get('reason', 'manual_engage')

    status = state.kill_switch.engage(actor=actor, reason=reason)

    return {'ok': True, 'status': status.__dict__}


@app.post("/admin/kill-switch/disengage")
async def admin_kill_switch_disengage(payload: Dict[str, str], x_api_key: str | None = Header(default=None)):
    """Disengage global kill switch (admin only)."""
    require_admin(x_api_key)

    if not state.kill_switch:
        raise HTTPException(status_code=500, detail="Kill switch not initialized")

    actor = payload.get('actor', 'admin')
    reason = payload.get('reason', 'manual_disengage')

    status = state.kill_switch.disengage(actor=actor, reason=reason)

    return {'ok': True, 'status': status.__dict__}


@app.get("/admin/kill-switch/status")
async def admin_kill_switch_status(x_api_key: str | None = Header(default=None)):
    """Get kill switch status (admin only)."""
    require_admin(x_api_key)

    if not state.kill_switch:
        raise HTTPException(status_code=500, detail="Kill switch not initialized")

    status = state.kill_switch.get_status()
    return {'ok': True, 'status': status.__dict__}

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
