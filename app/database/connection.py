"""
Database connection and configuration module.
Supports both SQLite (with WAL mode) and PostgreSQL.
Enhanced with robust error handling, health checks, and automatic reconnection.
"""
import os
import logging
import asyncio
from typing import Optional
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError, DisconnectionError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Database URL from environment variable via centralized config
DATABASE_URL = settings.DATABASE_URL

# Create async engine with connection pooling and robust error handling
engine = create_async_engine(
    DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,  # Enable connection health checks before each use
    pool_recycle=300,  # Recycle connections after 5 minutes to prevent stale connections
    echo=False,  # Set to True for SQL debugging
    future=True,
)

# Connection health monitoring
db_health_status = {
    'is_healthy': True,
    'last_check': None,
    'consecutive_failures': 0,
    'last_error': None
}

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

# Create session factory with proper error handling
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
    """Initialize database tables with retry logic."""
    max_retries = 5
    retry_delay = 2.0
    
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database initialized successfully")
            db_health_status['is_healthy'] = True
            db_health_status['consecutive_failures'] = 0
            return
        except OperationalError as e:
            logger.warning(f"⚠️  Database initialization failed (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** (attempt - 1))
                logger.info(f"Retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ Database initialization failed after {max_retries} attempts")
                db_health_status['is_healthy'] = False
                db_health_status['last_error'] = str(e)
                raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during database initialization: {e}")
            db_health_status['is_healthy'] = False
            db_health_status['last_error'] = str(e)
            raise


from contextlib import asynccontextmanager

@asynccontextmanager
async def get_session() -> AsyncSession:
    """
    Dependency for getting async database sessions with robust error handling.
    Implements automatic reconnection and fail-safe mechanisms.
    Enhanced to handle Errno 111 (Connection refused) gracefully.
    """
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(1, max_retries + 1):
        try:
            async with async_session_maker() as session:
                try:
                    # Test connection before yielding
                    await session.execute(text("SELECT 1"))
                    
                    # Update health status on successful connection
                    if not db_health_status['is_healthy']:
                        logger.info("✅ Database connection restored")
                    db_health_status['is_healthy'] = True
                    db_health_status['last_check'] = asyncio.get_event_loop().time()
                    db_health_status['consecutive_failures'] = 0
                    
                    yield session
                    return
                except (OperationalError, DisconnectionError) as e:
                    error_str = str(e).lower()
                    is_connection_refused = 'errno 111' in error_str or 'connection refused' in error_str
                    
                    logger.warning(f"⚠️  Database connection error (attempt {attempt}/{max_retries}): {e}")
                    if is_connection_refused:
                        logger.warning("   → Connection refused - PostgreSQL may be starting or unreachable")
                    
                    db_health_status['is_healthy'] = False
                    db_health_status['last_error'] = str(e)
                    db_health_status['consecutive_failures'] += 1
                    
                    if attempt < max_retries:
                        wait_time = retry_delay * (2 ** (attempt - 1))
                        logger.info(f"Retrying database connection in {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"❌ Database connection failed after {max_retries} attempts")
                        raise
        except (OperationalError, DisconnectionError) as e:
            error_str = str(e).lower()
            is_connection_refused = 'errno 111' in error_str or 'connection refused' in error_str
            
            logger.error(f"❌ Failed to create database session (attempt {attempt}/{max_retries}): {e}")
            if is_connection_refused:
                logger.error("   → Connection refused - Check if PostgreSQL is running and accessible")
            
            db_health_status['is_healthy'] = False
            db_health_status['last_error'] = str(e)
            db_health_status['consecutive_failures'] += 1
            
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** (attempt - 1))
                await asyncio.sleep(wait_time)
            else:
                logger.critical("🚨 DATABASE UNAVAILABLE - System may operate in degraded mode")
                raise
        except Exception as e:
            logger.error(f"❌ Unexpected error in database session: {type(e).__name__}: {e}")
            db_health_status['is_healthy'] = False
            db_health_status['last_error'] = str(e)
            raise


async def check_database_health() -> dict:
    """
    Perform comprehensive database health check.
    
    Returns:
        Dictionary with health status information
    """
    import time
    
    health_info = {
        'timestamp': time.time(),
        'is_healthy': False,
        'database_url': DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'unknown',
        'pool_size': settings.DB_POOL_SIZE,
        'checks': {}
    }
    
    try:
        # Check 1: Basic connectivity
        start_time = time.time()
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        connectivity_time = time.time() - start_time
        
        health_info['checks']['connectivity'] = {
            'status': 'pass',
            'latency_ms': round(connectivity_time * 1000, 2)
        }
        
        # Check 2: Pool status
        pool_status = engine.pool.status() if hasattr(engine.pool, 'status') else 'unknown'
        health_info['checks']['pool'] = {
            'status': 'pass',
            'info': pool_status
        }
        
        # Overall health
        health_info['is_healthy'] = True
        db_health_status['is_healthy'] = True
        db_health_status['last_check'] = time.time()
        
    except Exception as e:
        health_info['checks']['connectivity'] = {
            'status': 'fail',
            'error': str(e)
        }
        health_info['is_healthy'] = False
        db_health_status['is_healthy'] = False
        db_health_status['last_error'] = str(e)
    
    return health_info
