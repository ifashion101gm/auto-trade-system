"""
Analytics Agent - Calculates performance metrics and generates reports.
Provides data for dashboard and Telegram summaries.
"""
from app.database.models import Trades
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AnalyticsAgent:
    """
    Calculates performance metrics and generates reports.
    Provides data for dashboard and Telegram summaries.
    """
    
    async def calculate_daily_performance(self, db_session: AsyncSession, date=None):
        """Calculate daily trading performance."""
        if not date:
            date = datetime.utcnow().date()
        
        start_date = datetime.combine(date, datetime.min.time())
        end_date = datetime.combine(date, datetime.max.time())
        
        # Query closed trades for the day
        stmt = select(Trades).where(
            (Trades.status == 'closed') &
            (Trades.created_at >= start_date.isoformat()) &
            (Trades.created_at <= end_date.isoformat())
        )
        result = await db_session.execute(stmt)
        trades = result.scalars().all()
        
        if not trades:
            return {
                'date': date.isoformat(),
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0
            }
        
        total_pnl = sum(t.pnl or 0 for t in trades)
        winning = [t for t in trades if (t.pnl or 0) > 0]
        losing = [t for t in trades if (t.pnl or 0) <= 0]
        
        return {
            'date': date.isoformat(),
            'total_trades': len(trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(trades) * 100 if trades else 0,
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(total_pnl / len(trades), 2) if trades else 0,
            'best_trade': max((t.pnl or 0) for t in trades),
            'worst_trade': min((t.pnl or 0) for t in trades)
        }
    
    async def generate_strategy_report(self, db_session: AsyncSession):
        """Generate performance report by strategy."""
        stmt = select(
            Trades.strategy_name,
            func.count(Trades.id).label('total_trades'),
            func.avg(Trades.pnl).label('avg_pnl'),
            func.sum(Trades.pnl).label('total_pnl')
        ).where(
            Trades.status == 'closed'
        ).group_by(Trades.strategy_name)
        
        result = await db_session.execute(stmt)
        strategies = result.fetchall()
        
        return [
            {
                'strategy': row.strategy_name,
                'total_trades': row.total_trades,
                'avg_pnl': round(row.avg_pnl or 0, 2),
                'total_pnl': round(row.total_pnl or 0, 2)
            }
            for row in strategies
        ]
