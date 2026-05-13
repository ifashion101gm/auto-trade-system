"""
Main FastAPI application with multi-agent orchestration.
Enhanced with execution layer architecture upgrade and production logging.
"""
import asyncio
import time
from datetime import datetime
from fastapi import FastAPI, Request, Response
from contextlib import asynccontextmanager
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from app.dashboard import trading_router, ai_router, cache_router, llm_router
from app.database.connection import init_db, get_session
from app.logging_config import logger, log_websocket_event, log_sync_result
from app.config import settings
from app.sync.sync_agent import SyncAgent
from app.recovery.recovery_service import RecoveryService
from app.services.reconciliation_service import ReconciliationService
from app.sync.position_sync import PositionSyncService
from app.notifications.telegram_agent import TelegramAgent
from app.events.event_bus import event_bus
from app.events.event_store import event_store

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency'
)
WEBSOCKET_CONNECTED = Counter(
    'websocket_connected',
    'WebSocket connection status (1=connected, 0=disconnected)'
)
EVENT_BUS_QUEUE_SIZE = Histogram(
    'event_bus_queue_size',
    'Event bus queue size'
)

# Background services
sync_agent = SyncAgent()
recovery_service = RecoveryService()
reconciliation_service = ReconciliationService()
position_sync_service = None  # Will be initialized on startup
telegram_agent = None  # Will be initialized on startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with all background services."""
    # Startup
    logger.info("🚀 Auto Trade System starting up...")
    logger.info(f"   Version: 2.0.0")
    logger.info(f"   Environment: {getattr(settings, 'ENVIRONMENT', 'production')}")
    
    await init_db()
    logger.info("✅ PostgreSQL database initialized")
    
    # Initialize EventBus with background processing
    await event_bus.start_processing()
    logger.info("✅ EventBus started with priority processing")
    logger.debug(f"   Event types registered: {len(event_bus._subscribers)}")
    
    # Subscribe EventStore to persist critical events
    async def persist_critical_events(event):
        async for db_session in get_session():
            await event_store.persist_event(event, db_session)
            break
    
    # Subscribe to all critical event types
    from app.events.event_types import (
        ORDER_FILLED, ORDER_PARTIALLY_FILLED, ORDER_CANCELLED,
        POSITION_UPDATED, SYNC_MISMATCH, SYNC_REPAIRED
    )
    
    for event_type in [ORDER_FILLED, ORDER_PARTIALLY_FILLED, ORDER_CANCELLED,
                       POSITION_UPDATED, SYNC_MISMATCH, SYNC_REPAIRED]:
        event_bus.subscribe(event_type, persist_critical_events, priority=20)
    
    logger.info("✅ EventStore subscribed to critical events")
    logger.debug(f"   Subscribed to: ORDER_FILLED, ORDER_PARTIALLY_FILLED, ORDER_CANCELLED, POSITION_UPDATED, SYNC_MISMATCH, SYNC_REPAIRED")
    
    # Initialize agents
    global telegram_agent, sync_agent
    telegram_agent = TelegramAgent()
    sync_agent = SyncAgent()
    logger.info("✅ Agents initialized (Telegram, Sync)")
    
    # Run recovery
    logger.info("🔄 Running startup recovery checks...")
    async for db_session in get_session():
        await recovery_service.recover_on_startup(db_session)
        break
    logger.info("✅ Startup recovery completed")
    
    # Start sync agent with WebSocket (Bybit Demo Trading)
    logger.info("🔌 Starting Bybit WebSocket connection...")
    asyncio.create_task(sync_agent.start_listening(
        symbols=['XAU/USDT:USDT'],  # Bybit Gold perpetual swap
        db_session_factory=get_session
    ))
    logger.info("✅ Sync agent with Bybit WebSocket started")
    logger.debug(f"   Symbols: XAU/USDT:USDT")
    
    # Start reconciliation loop (every 2 minutes)
    logger.info("⏱️  Starting reconciliation loop (2-minute interval)...")
    async def reconciliation_loop():
        while True:
            try:
                async for db_session in get_session():
                    await reconciliation_service.reconcile(mode='DEMO', db_session=db_session)
                    await reconciliation_service.reconcile(mode='LIVE', db_session=db_session)
                    break
            except Exception as e:
                logger.error(f"Reconciliation error: {e}", exc_info=True)
            await asyncio.sleep(120)
    
    asyncio.create_task(reconciliation_loop())
    logger.info("✅ Reconciliation loop started")
    
    # Start position sync service (every 5 seconds) - Bybit Demo Trading
    global position_sync_service
    position_sync_service = PositionSyncService(testnet=True)  # Testnet flag for Bybit demo
    logger.info("🔄 Starting position sync service...")
    asyncio.create_task(position_sync_service.start(get_session))
    logger.info("✅ Position sync service started (5s interval, Bybit Demo mode)")
    
    logger.info("🎉 Auto Trade System fully operational!")
    logger.info(f"   Dashboard: http://localhost:8000/docs")
    logger.info(f"   Metrics: http://localhost:8000/metrics/prometheus")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Auto Trade System...")
    
    await event_bus.stop_processing()
    logger.info("✅ EventBus stopped")
    
    if position_sync_service:
        position_sync_service.stop()
        await position_sync_service.close()
        logger.info("✅ Position sync service stopped")
    
    await sync_agent.stop()
    logger.info("✅ Sync agent stopped")
    
    logger.info("👋 Auto Trade System shutdown complete")


app = FastAPI(
    title="Auto Trade System - Multi-Agent",
    description="Production-ready automated trading with multi-agent architecture",
    version="2.0.0",
    lifespan=lifespan
)

# Add Prometheus metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to track HTTP request metrics for Prometheus."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.observe(duration)
    return response

# Include routers
app.include_router(trading_router, prefix="/api/v1", tags=["trading"])
app.include_router(ai_router, prefix="/api/v1", tags=["ai-orchestration"])
app.include_router(cache_router, prefix="/api/v1", tags=["cache-management"])
app.include_router(llm_router, prefix="/api/v1", tags=["llm-optimization"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}

@app.get("/")
async def root():
    return {
        "message": "Auto Trade System - Multi-Agent Architecture",
        "docs": "/docs",
        "version": "2.0.0"
    }

@app.get("/metrics")
async def get_system_metrics(request: Request):
    """Get comprehensive system metrics from all components."""
    # If the request accepts Prometheus format, return that instead
    accept_header = request.headers.get('accept', '')
    if 'application/openmetrics-text' in accept_header or 'text/plain' in accept_header:
        # Return Prometheus format
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    # Otherwise return the existing format
    return {
        "event_bus": event_bus.get_metrics(),
        "websocket": sync_agent.websocket_manager.get_metrics() if sync_agent and hasattr(sync_agent, 'websocket_manager') else None,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
