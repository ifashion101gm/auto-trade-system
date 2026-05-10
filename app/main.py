"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api import trading, ai, cache, llm
from app.storage.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup: Initialize database
    await init_db()
    print("✅ Database initialized with WAL mode")
    
    yield
    
    # Shutdown: Cleanup resources
    print("🛑 Shutting down...")


app = FastAPI(
    title="Auto Trade System",
    description="Production-ready automated trading system with AI orchestration",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(trading.router, prefix="/api/v1", tags=["trading"])
app.include_router(ai.router, prefix="/api/v1", tags=["ai-orchestration"])
app.include_router(cache.router, prefix="/api/v1", tags=["cache-management"])
app.include_router(llm.router, prefix="/api/v1", tags=["llm-optimization"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Auto Trade System API",
        "docs": "/docs",
        "version": "1.0.0"
    }
