"""
Main FastAPI application with multi-agent orchestration.
"""
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api import trading, ai, cache, llm
from app.storage.db import init_db, get_session
from app.logging_config import get_logger
from app.agents.sync_agent import SyncAgent
from app.services.recovery_service import RecoveryService
from app.services.reconciliation_service import ReconciliationService
from app.agents.telegram_agent import TelegramAgent

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
