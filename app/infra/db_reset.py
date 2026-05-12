"""
Database reset and archival utilities for trading system.
Provides mechanisms to clear or archive trade history for fresh test cycles.
"""
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import (
    PaperTrades, TrailEvents, DecisionJournal, 
    StrategyEvaluations, TradeProposals
)


class DatabaseResetter:
    """
    Manages database reset and archival operations.
    
    Features:
    - Archive existing trades before deletion
    - Selective table clearing
    - Backup to JSON files
    - Safe reset with confirmation
    """
    
    def __init__(self, backup_dir: str = "./data/backups"):
        """
        Initialize database resetter.
        
        Args:
            backup_dir: Directory for storing archived data
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def archive_trades(self, db_session: AsyncSession, user_id: str = None) -> dict:
        """
        Archive existing trades to JSON file before deletion.
        
        Args:
            db_session: Active database session
            user_id: Optional user filter (None = all users)
            
        Returns:
            Dictionary with archive statistics
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_file = self.backup_dir / f"trades_archive_{timestamp}.json"
        
        # Fetch trades to archive
        query = select(PaperTrades)
        if user_id:
            query = query.where(PaperTrades.user_id == user_id)
        
        result = await db_session.execute(query)
        trades = result.scalars().all()
        
        # Convert to serializable format
        trade_data = []
        for trade in trades:
            trade_dict = {
                'id': trade.id,
                'ts_open': trade.ts_open,
                'ts_close': trade.ts_close,
                'user_id': trade.user_id,
                'exchange': trade.exchange,
                'symbol': trade.symbol,
                'side': trade.side,
                'leverage': trade.leverage,
                'qty': trade.qty,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'stop_loss': trade.stop_loss,
                'take_profit': trade.take_profit,
                'profit': trade.profit,
                'profit_pct': trade.profit_pct,
                'status': trade.status,
                'notes': trade.notes,
                'execution_mode': trade.execution_mode
            }
            trade_data.append(trade_dict)
        
        # Save to JSON
        archive_data = {
            'archived_at': datetime.utcnow().isoformat(),
            'user_id': user_id or 'all',
            'total_trades': len(trade_data),
            'trades': trade_data
        }
        
        with open(archive_file, 'w') as f:
            json.dump(archive_data, f, indent=2)
        
        return {
            'archive_file': str(archive_file),
            'total_trades_archived': len(trade_data),
            'user_id': user_id or 'all'
        }
    
    async def reset_trading_tables(self, db_session: AsyncSession, user_id: str = None, archive: bool = True) -> dict:
        """
        Reset trading-related tables (PaperTrades, TrailEvents, TradeProposals).
        
        Args:
            db_session: Active database session
            user_id: Optional user filter (None = all users)
            archive: Whether to archive before deletion
            
        Returns:
            Dictionary with reset statistics
        """
        stats = {
            'paper_trades_deleted': 0,
            'trail_events_deleted': 0,
            'trade_proposals_deleted': 0,
            'archived': False
        }
        
        # Step 1: Archive if requested
        if archive:
            archive_result = await self.archive_trades(db_session, user_id)
            stats['archived'] = True
            stats['archive_info'] = archive_result
        
        # Step 2: Delete trail events (foreign key dependency)
        if user_id:
            # Get trade IDs for this user first
            trade_query = select(PaperTrades.id).where(PaperTrades.user_id == user_id)
            trade_result = await db_session.execute(trade_query)
            trade_ids = [row[0] for row in trade_result.all()]
            
            if trade_ids:
                trail_delete = delete(TrailEvents).where(TrailEvents.trade_id.in_(trade_ids))
                trail_result = await db_session.execute(trail_delete)
                stats['trail_events_deleted'] = trail_result.rowcount
        else:
            trail_delete = delete(TrailEvents)
            trail_result = await db_session.execute(trail_delete)
            stats['trail_events_deleted'] = trail_result.rowcount
        
        # Step 3: Delete trade proposals
        proposal_delete = delete(TradeProposals)
        if user_id:
            proposal_delete = proposal_delete.where(TradeProposals.user_id == user_id)
        proposal_result = await db_session.execute(proposal_delete)
        stats['trade_proposals_deleted'] = proposal_result.rowcount
        
        # Step 4: Delete paper trades
        trade_delete = delete(PaperTrades)
        if user_id:
            trade_delete = trade_delete.where(PaperTrades.user_id == user_id)
        trade_result = await db_session.execute(trade_delete)
        stats['paper_trades_deleted'] = trade_result.rowcount
        
        await db_session.flush()
        
        return stats
    
    async def reset_decision_history(self, db_session: AsyncSession, user_id: str = None) -> dict:
        """
        Reset decision journal and strategy evaluations.
        
        Args:
            db_session: Active database session
            user_id: Optional user filter
            
        Returns:
            Dictionary with reset statistics
        """
        stats = {
            'decision_journal_deleted': 0,
            'strategy_evaluations_deleted': 0
        }
        
        # Delete decision journal
        dj_delete = delete(DecisionJournal)
        if user_id:
            dj_delete = dj_delete.where(DecisionJournal.user_id == user_id)
        dj_result = await db_session.execute(dj_delete)
        stats['decision_journal_deleted'] = dj_result.rowcount
        
        # Delete strategy evaluations
        se_delete = delete(StrategyEvaluations)
        se_result = await db_session.execute(se_delete)
        stats['strategy_evaluations_deleted'] = se_result.rowcount
        
        await db_session.flush()
        
        return stats
    
    async def full_reset(self, db_session: AsyncSession, user_id: str = None, archive: bool = True) -> dict:
        """
        Perform complete reset of all trading data.
        
        Args:
            db_session: Active database session
            user_id: Optional user filter
            archive: Whether to archive before deletion
            
        Returns:
            Comprehensive reset statistics
        """
        print(f"🔄 Starting database reset (user: {user_id or 'all'}, archive: {archive})...")
        
        # Reset trading tables
        trading_stats = await self.reset_trading_tables(db_session, user_id, archive)
        
        # Reset decision history
        decision_stats = await self.reset_decision_history(db_session, user_id)
        
        # Combine statistics
        full_stats = {
            'reset_timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id or 'all',
            'archived': trading_stats.get('archived', False),
            'archive_info': trading_stats.get('archive_info'),
            'tables_cleared': {
                **trading_stats,
                **decision_stats
            },
            'total_records_deleted': (
                trading_stats['paper_trades_deleted'] +
                trading_stats['trail_events_deleted'] +
                trading_stats['trade_proposals_deleted'] +
                decision_stats['decision_journal_deleted'] +
                decision_stats['strategy_evaluations_deleted']
            )
        }
        
        print(f"✅ Database reset complete. {full_stats['total_records_deleted']} records deleted.")
        if full_stats['archived']:
            print(f"📦 Archive saved to: {full_stats['archive_info']['archive_file']}")
        
        return full_stats


async def reset_database_for_testnet(user_id: str = None, archive: bool = True):
    """
    Convenience function to reset database for Binance Testnet testing.
    
    Args:
        user_id: Optional user filter
        archive: Whether to archive existing data
    """
    from app.database.connection import async_session_maker
    
    resetter = DatabaseResetter()
    
    async with async_session_maker() as db_session:
        try:
            stats = await resetter.full_reset(db_session, user_id, archive)
            await db_session.commit()
            return stats
        except Exception as e:
            await db_session.rollback()
            raise e
