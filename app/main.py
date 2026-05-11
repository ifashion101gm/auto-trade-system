"""
Main FastAPI application with multi-agent orchestration.
Enhanced with execution layer architecture upgrade.
"""
import asyncio
from datetime import datetime
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api import trading, ai, cache, llm
from app.storage.db import init_db, get_session
from app.logging_config import get_logger
from app.agents.sync_agent import SyncAgent
from app.services.recovery_service import RecoveryService
from app.services.reconciliation_service import ReconciliationService
from app.agents.telegram_agent import TelegramAgent
from app.events.event_bus import event_bus
from app.events.event_store import event_store

logger = get_logger(__name__)

# Background services
sync_agent = SyncAgent()
recovery_service = RecoveryService()
reconciliation_service = ReconciliationService()
telegram_agent = None  # Will be initialized on startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with all background services."""
    # Startup
    await init_db()
    logger.info("✅ PostgreSQL database initialized")
    
    # Initialize EventBus with background processing
    await event_bus.start_processing()
    logger.info("✅ EventBus started with priority processing")
    
    # Subscribe EventStore to persist critical events
    async def persist_critical_events(event):
        async for db_session in get_session():
            await event_store.persist_event(event, db_session)
            break
    
    # Subscribe to all critical event types
    from app.events.event_types import (
        ORDER_FILLED, ORDER_PARTIALLY_FILLED, ORDER_CANCELLED,
        POSITION_UPDATED, SYNC_MISMATCH, SYNC_REPAIRED, STATE_CHANGED
    )
    
    for event_type in [ORDER_FILLED, ORDER_PARTIALLY_FILLED, ORDER_CANCELLED,
                       POSITION_UPDATED, SYNC_MISMATCH, SYNC_REPAIRED, STATE_CHANGED]:
        event_bus.subscribe(event_type, persist_critical_events, priority=20)
    
    logger.info("✅ EventStore subscribed to critical events")
    
    # Initialize agents
    global telegram_agent, sync_agent
    telegram_agent = TelegramAgent()
    sync_agent = SyncAgent()
    logger.info("✅ Agents initialized")
    
    # Run recovery
    async for db_session in get_session():
        await recovery_service.recover_on_startup(db_session)
        break
    
    # Start sync agent with WebSocket
    asyncio.create_task(sync_agent.start_listening(
        symbols=['XAUT/USDT'],
        db_session_factory=get_session
    ))
    logger.info("✅ Sync agent with WebSocket started")
    
    # Start reconciliation loop (every 2 minutes)
    async def reconciliation_loop():
        while True:
            try:
                async for db_session in get_session():
                    await reconciliation_service.reconcile(mode='DEMO', db_session=db_session)
                    await reconciliation_service.reconcile(mode='LIVE', db_session=db_session)
                    break
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")
            await asyncio.sleep(120)
    
    asyncio.create_task(reconciliation_loop())
    logger.info("✅ Reconciliation loop started")
    
    yield
    
    # Shutdown
    await event_bus.stop_processing()
    logger.info("🛑 EventBus stopped")
    
    await sync_agent.stop()
    logger.info("🛑 Shutting down...")


app = FastAPI(
    title="Auto Trade System - Multi-Agent",
    description="Production-ready automated trading with multi-agent architecture",
    version="2.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(trading.router, prefix="/api/v1", tags=["trading"])
app.include_router(ai.router, prefix="/api/v1", tags=["ai-orchestration"])
app.include_router(cache.router, prefix="/api/v1", tags=["cache-management"])
app.include_router(llm.router, prefix="/api/v1", tags=["llm-optimization"])

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
async def get_system_metrics():
    """Get comprehensive system metrics from all components."""
    return {
        "event_bus": event_bus.get_metrics(),
        "websocket": sync_agent.websocket_manager.get_metrics() if sync_agent else None,
        "timestamp": datetime.utcnow().isoformat()
    }
