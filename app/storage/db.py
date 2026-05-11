"""
Database connection and configuration module.
Supports both SQLite (with WAL mode) and PostgreSQL.
"""
import os
import logging
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Database URL from environment variable via centralized config
DATABASE_URL = settings.DATABASE_URL

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    future=True,
)

# Enable WAL mode for SQLite using event listeners
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

# Create session factory
async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for ORM models
Base = declarative_base()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database initialized with WAL mode")


async def get_session() -> AsyncSession:
    """Dependency for getting async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
