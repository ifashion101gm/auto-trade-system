"""
Recovery Service - Recovers system state after restart/crash.
Fetches exchange positions and restores database consistency.
"""
from app.exchange.exchange_router import ExchangeRouter
from app.database.models import Trades, Positions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RecoveryService:
    """
    Recovers system state after restart/crash.
    Fetches exchange positions and restores database consistency.
    """
    
    def __init__(self):
        self.router = ExchangeRouter()
    
    async def recover_on_startup(self, db_session: AsyncSession = None):
        """Run recovery on system startup."""
        logger.info("🔄 Recovery: Starting system recovery...")
        
        if not db_session:
            return
        
        # Fetch all open positions from exchange
        for mode in ['LIVE', 'DEMO']:
            try:
                exchange = self.router.get_exchange(mode)
                exchange_positions = await exchange.get_positions()
                
                logger.info(f"   Found {len(exchange_positions)} {mode} positions on exchange")
                
                # Restore each position
                for ex_pos in exchange_positions:
                    await self._restore_position(ex_pos, mode, db_session)
                
            except Exception as e:
                logger.error(f"Recovery failed for {mode}: {e}")
        
        logger.info("✅ Recovery completed")
    
    async def _restore_position(self, ex_pos, mode, db_session):
        """Restore a single position to database."""
        symbol = ex_pos['symbol']
        
        # Check if position already exists in DB
        stmt = select(Positions).where(
            (Positions.symbol == symbol) & (Positions.status == 'open')
        )
        result = await db_session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"   Position {symbol} already in DB, updating...")
            existing.current_price = ex_pos.get('current_price', 0)
            existing.unrealized_pnl = ex_pos.get('unrealized_pnl', 0)
            existing.last_sync = datetime.utcnow().isoformat()
        else:
            logger.info(f"   Restoring missing position: {symbol}")
            
            # Try to find associated trade
            trade_stmt = select(Trades).where(
                (Trades.symbol == symbol) & (Trades.status == 'open')
            )
            trade_result = await db_session.execute(trade_stmt)
            trade = trade_result.scalar_one_or_none()
            
            # Create position record
            position = Positions(
                trade_id=trade.id if trade else None,
                symbol=symbol,
                size=ex_pos.get('size', 0),
                entry_price=ex_pos.get('entry_price', 0),
                current_price=ex_pos.get('current_price', 0),
                unrealized_pnl=ex_pos.get('unrealized_pnl', 0),
                liquidation_price=ex_pos.get('liquidation_price'),
                leverage=ex_pos.get('leverage', 1),
                status='open',
                last_sync=datetime.utcnow().isoformat()
            )
            db_session.add(position)
        
        await db_session.commit()
