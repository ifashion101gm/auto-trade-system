#!/usr/bin/env python3
"""
Migration script: Move risk state from .risk_state.json to PostgreSQL.

This script should be run once during deployment after applying migration 006.
It reads the existing JSON file and inserts/updates the risk_state table.

Usage:
    python scripts/migrate_risk_state_to_db.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.connection import get_session, init_db
from app.database.models import RiskState
from app.logging_config import logger
from sqlalchemy import select


async def migrate_risk_state():
    """Migrate risk state from JSON file to PostgreSQL."""
    json_file = project_root / '.risk_state.json'
    
    logger.info("=" * 80)
    logger.info("RISK STATE MIGRATION: JSON → PostgreSQL")
    logger.info("=" * 80)
    
    # Check if JSON file exists
    if not json_file.exists():
        logger.info("✅ No .risk_state.json file found - nothing to migrate")
        logger.info("   Database will use default values on first run")
        return
    
    logger.info(f"📄 Reading risk state from: {json_file}")
    
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        logger.info(f"✅ Loaded JSON data:")
        for key, value in data.items():
            logger.info(f"   {key}: {value}")
        
    except Exception as e:
        logger.error(f"❌ Failed to read JSON file: {e}")
        return
    
    # Initialize database
    logger.info("\n🔌 Connecting to database...")
    await init_db()
    
    async with get_session() as db_session:
        # Check if row already exists
        result = await db_session.execute(select(RiskState).where(RiskState.id == 1))
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info("⚠️  Risk state row already exists in database")
            logger.info("   Updating with JSON data...")
            
            # Update existing row
            existing.daily_loss_lock_active = int(data.get('daily_loss_lock_active', False))
            existing.drawdown_lock_active = int(data.get('drawdown_lock_active', False))
            existing.daily_pnl = data.get('daily_pnl', 0.0)
            existing.daily_pnl_pct = data.get('daily_pnl_pct', 0.0)
            existing.current_balance = data.get('current_balance', 0.0)
            existing.peak_balance = data.get('peak_balance', 0.0)
            existing.today_date = data.get('today_date')
            
            await db_session.commit()
            logger.info("✅ Updated existing row")
        else:
            logger.info("➕ Inserting new risk state row...")
            
            # Insert new row
            new_state = RiskState(
                id=1,
                daily_loss_lock_active=int(data.get('daily_loss_lock_active', False)),
                drawdown_lock_active=int(data.get('drawdown_lock_active', False)),
                daily_pnl=data.get('daily_pnl', 0.0),
                daily_pnl_pct=data.get('daily_pnl_pct', 0.0),
                current_balance=data.get('current_balance', 0.0),
                peak_balance=data.get('peak_balance', 0.0),
                today_date=data.get('today_date')
            )
            db_session.add(new_state)
            await db_session.commit()
            logger.info("✅ Inserted new row")
    
    # Verify migration
    logger.info("\n🔍 Verifying migration...")
    async with get_session() as db_session:
        result = await db_session.execute(select(RiskState).where(RiskState.id == 1))
        state = result.scalar_one_or_none()
        
        if state:
            logger.info("✅ Verification successful:")
            logger.info(f"   ID: {state.id}")
            logger.info(f"   Daily Loss Lock: {bool(state.daily_loss_lock_active)}")
            logger.info(f"   Drawdown Lock: {bool(state.drawdown_lock_active)}")
            logger.info(f"   Daily P&L: ${state.daily_pnl:.2f}")
            logger.info(f"   Current Balance: ${state.current_balance:.2f}")
            logger.info(f"   Peak Balance: ${state.peak_balance:.2f}")
            logger.info(f"   Today Date: {state.today_date}")
        else:
            logger.error("❌ Verification failed - no row found in database")
            return
    
    # Ask user about deleting JSON file
    logger.info("\n" + "=" * 80)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"\nThe .risk_state.json file has been migrated to PostgreSQL.")
    logger.info(f"You can now safely delete the JSON file:")
    logger.info(f"   rm {json_file}")
    logger.info(f"\nOr keep it as backup (it will be ignored by the system).")
    

if __name__ == "__main__":
    try:
        asyncio.run(migrate_risk_state())
        logger.info("\n✅ Migration completed successfully")
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)
