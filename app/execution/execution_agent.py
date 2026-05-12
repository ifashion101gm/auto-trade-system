"""
Execution Agent - Executes validated trades on exchanges.
Handles order lifecycle: OPEN → FILLED → CLOSED
Persists all state changes to database.
"""
from app.exchange.exchange_router import ExchangeRouter
from app.events.event_bus import event_bus
from app.events.event_types import ORDER_OPENED, ORDER_CLOSED, API_ERROR
from app.database.models import Trades
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class ExecutionAgent:
    """
    Executes validated trades on exchanges.
    Handles order lifecycle: OPEN → FILLED → CLOSED
    Persists all state changes to database.
    """
    
    def __init__(self):
        self.router = ExchangeRouter()
    
    async def execute_trade(self, proposal, mode='DEMO', db_session: AsyncSession = None):
        """Execute trade after validation."""
        logger.info(f"⚡ Execution Agent: Executing {mode} trade...")
        
        try:
            # Get appropriate exchange
            exchange = self.router.get_exchange(mode)
            
            # Execute order
            order_result = await exchange.open_position(
                symbol=proposal['symbol'],
                side=proposal['side'],
                amount=proposal['quantity'],
                leverage=proposal['leverage'],
                stop_loss=proposal.get('stop_loss'),
                take_profit=proposal.get('take_profit')
            )
            
            # Create trade record in database
            trade_id = str(uuid.uuid4())
            trade_record = Trades(
                id=trade_id,
                mode=mode,
                exchange='mexc',
                symbol=proposal['symbol'],
                side=proposal['side'].upper(),
                status='open',
                entry_price=order_result['filled_price'],
                current_price=order_result['filled_price'],
                stop_loss=proposal.get('stop_loss'),
                take_profit=proposal.get('take_profit'),
                leverage=proposal['leverage'],
                quantity=proposal['quantity'],
                pnl=0.0,
                exchange_order_id=order_result['order_id'],
                strategy_name=proposal.get('strategy_name'),
                regime=proposal.get('regime'),
                confidence=proposal.get('confidence'),
                created_at=datetime.utcnow().isoformat()
            )
            
            if db_session:
                db_session.add(trade_record)
                await db_session.commit()
            
            # Publish events
            await event_bus.publish(ORDER_OPENED, {
                'trade_id': trade_id,
                'order_id': order_result['order_id'],
                'mode': mode,
                'symbol': proposal['symbol'],
                'side': proposal['side'],
                'entry_price': order_result['filled_price']
            })
            
            logger.info(f"✅ Trade executed: {trade_id}")
            return {'trade_id': trade_id, 'order': order_result}
            
        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")
            await event_bus.publish(API_ERROR, {
                'error': str(e),
                'context': 'execution'
            })
            raise
    
    async def close_trade(self, trade_id, db_session: AsyncSession = None):
        """Close an open trade."""
        logger.info(f"⚡ Execution Agent: Closing trade {trade_id}...")
        
        # Fetch trade from DB
        if db_session:
            from sqlalchemy import select
            stmt = select(Trades).where(Trades.id == trade_id)
            result = await db_session.execute(stmt)
            trade = result.scalar_one_or_none()
            
            if not trade:
                raise ValueError(f"Trade {trade_id} not found")
            
            # Get exchange
            exchange = self.router.get_exchange(trade.mode)
            
            # Close position
            close_result = await exchange.close_position(trade.symbol, trade_id)
            
            # Update trade record
            trade.status = 'closed'
            trade.exit_price = close_result.get('exit_price')
            trade.pnl = close_result.get('pnl', 0)
            trade.closed_at = datetime.utcnow().isoformat()
            
            await db_session.commit()
            
            # Publish event
            await event_bus.publish(ORDER_CLOSED, {
                'trade_id': trade_id,
                'pnl': trade.pnl,
                'exit_price': trade.exit_price
            })
            
            return {'trade_id': trade_id, 'pnl': trade.pnl}
