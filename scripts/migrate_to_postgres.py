"""
Migration script to transfer data from SQLite to PostgreSQL.
Exports SQLite data to JSON, creates PostgreSQL schema, and imports data.
"""
import asyncio
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
SQLITE_DB_PATH = Path("data/vmassit.db")
POSTGRES_URL = "postgresql+asyncpg://user:password@localhost:5432/vmassit"


def export_sqlite_to_json(sqlite_path: Path) -> dict:
    """Export all tables from SQLite to JSON."""
    logger.info(f"📤 Exporting SQLite database: {sqlite_path}")
    
    if not sqlite_path.exists():
        logger.warning("SQLite database not found, skipping export")
        return {}
    
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    data = {}
    for table in tables:
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        
        data[table] = [dict(zip(columns, row)) for row in rows]
        logger.info(f"  Exported {len(data[table])} rows from {table}")
    
    conn.close()
    
    # Save to JSON file
    export_file = Path("data/sqlite_export.json")
    with open(export_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    logger.info(f"✅ Exported to {export_file}")
    return data


async def create_postgres_schema():
    """Create PostgreSQL schema using Alembic."""
    logger.info("🔧 Creating PostgreSQL schema...")
    
    # Run Alembic migration
    import subprocess
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("✅ PostgreSQL schema created successfully")
    else:
        logger.error(f"❌ Schema creation failed: {result.stderr}")
        raise Exception(result.stderr)


async def import_to_postgres(data: dict):
    """Import data from JSON to PostgreSQL."""
    if not data:
        logger.info("No data to import")
        return
    
    logger.info("📥 Importing data to PostgreSQL...")
    
    engine = create_async_engine(POSTGRES_URL)
    
    try:
        async with engine.begin() as conn:
            for table_name, rows in data.items():
                if not rows:
                    continue
                
                logger.info(f"  Importing {len(rows)} rows to {table_name}")
                
                # Skip schema_migrations table (handled by Alembic)
                if table_name == 'schema_migrations':
                    continue
                
                # Build insert statement
                columns = list(rows[0].keys())
                placeholders = ", ".join([f":{col}" for col in columns])
                column_names = ", ".join(columns)
                
                insert_sql = text(
                    f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                )
                
                # Insert rows in batches
                batch_size = 100
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i + batch_size]
                    await conn.execute(insert_sql, batch)
                
                logger.info(f"  ✅ Imported {len(rows)} rows to {table_name}")
    
    finally:
        await engine.dispose()


async def verify_migration():
    """Verify data integrity after migration."""
    logger.info("🔍 Verifying migration...")
    
    engine = create_async_engine(POSTGRES_URL)
    
    try:
        async with engine.begin() as conn:
            # Check table count
            result = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            table_count = result.scalar()
            logger.info(f"  Tables in PostgreSQL: {table_count}")
            
            # Check trades count
            result = await conn.execute(text("SELECT COUNT(*) FROM trades"))
            trade_count = result.scalar()
            logger.info(f"  Total trades: {trade_count}")
            
            # Check positions count
            result = await conn.execute(text("SELECT COUNT(*) FROM positions"))
            position_count = result.scalar()
            logger.info(f"  Total positions: {position_count}")
            
            logger.info("✅ Verification complete")
    
    finally:
        await engine.dispose()


async def main():
    """Run complete migration."""
    logger.info("=" * 60)
    logger.info("Starting SQLite to PostgreSQL Migration")
    logger.info("=" * 60)
    
    # Step 1: Export SQLite to JSON
    data = export_sqlite_to_json(SQLITE_DB_PATH)
    
    # Step 2: Create PostgreSQL schema
    await create_postgres_schema()
    
    # Step 3: Import data to PostgreSQL
    await import_to_postgres(data)
    
    # Step 4: Verify migration
    await verify_migration()
    
    logger.info("=" * 60)
    logger.info("✅ Migration completed successfully!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Update .env file with PostgreSQL URL")
    logger.info("2. Restart application")
    logger.info("3. Monitor logs for any issues")


if __name__ == "__main__":
    asyncio.run(main())
