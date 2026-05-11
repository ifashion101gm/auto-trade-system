"""
Async repository pattern for clean database access.
Provides centralized data access methods for trades and positions.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.storage.models import Trades, Positions, OrderEvents
from datetime import datetime
import uuid
import json
import logging

logger = logging.getLogger(__name__)


class TradeRepository:
    """Repository for trade-related database operations."""
    
    async def create_trade(self, trade_data: dict, db_session: AsyncSession) -> Trades:
        """Create a new trade record."""
        trade_id = trade_data.get('id', str(uuid.uuid4()))
        
        trade = Trades(
            id=trade_id,
            mode=trade_data['mode'],
            exchange=trade_data['exchange'],
            symbol=trade_data['symbol'],
            side=trade_data['side'],
            status=trade_data.get('status', 'PENDING'),
            entry_price=trade_data['entry_price'],
            current_price=trade_data['entry_price'],
            stop_loss=trade_data.get('stop_loss'),
            take_profit=trade_data.get('take_profit'),
            leverage=trade_data['leverage'],
            quantity=trade_data['quantity'],
            filled_quantity=trade_data.get('filled_quantity'),
            pnl=0.0,
            exchange_order_id=trade_data.get('exchange_order_id'),
            strategy_name=trade_data.get('strategy_name'),
            regime=trade_data.get('regime'),
            confidence=trade_data.get('confidence'),
            created_at=datetime.utcnow().isoformat()
        )
        
        db_session.add(trade)
        await db_session.commit()
        await db_session.refresh(trade)
        
        logger.info(f"✅ Trade created: {trade_id}")
        return trade
    
    async def get_trade(self, trade_id: str, db_session: AsyncSession) -> Optional[Trades]:
        """Get a single trade by ID."""
        stmt = select(Trades).where(Trades.id == trade_id)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_trade_by_order_id(self, order_id: str, db_session: AsyncSession) -> Optional[Trades]:
        """Get a trade by exchange order ID."""
        stmt = select(Trades).where(Trades.exchange_order_id == order_id)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_open_trade_by_symbol(self, symbol: str, db_session: AsyncSession) -> Optional[Trades]:
        """Get open trade by symbol."""
        stmt = select(Trades).where(
            (Trades.symbol == symbol) & (Trades.status.in_(['OPEN', 'PENDING', 'PARTIAL']))
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_trade_status(self, trade_id: str, status: str, db_session: AsyncSession):
        """Update trade status."""
        stmt = update(Trades).where(Trades.id == trade_id).values(
            status=status,
            updated_at=datetime.utcnow().isoformat()
        )
        await db_session.execute(stmt)
        await db_session.commit()
        logger.info(f"📝 Trade {trade_id} status updated to {status}")
    
    async def update_trade_prices(self, trade_id: str, current_price: float, db_session: AsyncSession):
        """Update trade current price and recalculate PnL."""
        trade = await self.get_trade(trade_id, db_session)
        if not trade:
            return
        
        trade.current_price = current_price
        
        # Calculate PnL
        if trade.side == 'LONG':
            trade.pnl = (current_price - trade.entry_price) * trade.quantity
        else:  # SHORT
            trade.pnl = (trade.entry_price - current_price) * trade.quantity
        
        trade.pnl_pct = (trade.pnl / (trade.entry_price * trade.quantity)) * 100 if trade.entry_price > 0 else 0
        trade.updated_at = datetime.utcnow().isoformat()
        
        await db_session.commit()
    
    async def close_trade(self, trade_id: str, exit_price: float, pnl: float, db_session: AsyncSession):
        """Close a trade with exit price and PnL."""
        stmt = update(Trades).where(Trades.id == trade_id).values(
            status='CLOSED',
            exit_price=exit_price,
            pnl=pnl,
            closed_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        await db_session.execute(stmt)
        await db_session.commit()
        logger.info(f"✅ Trade {trade_id} closed with PnL: ${pnl:.2f}")
    
    async def get_open_trades(self, db_session: AsyncSession) -> List[Trades]:
        """Get all open trades."""
        stmt = select(Trades).where(Trades.status.in_(['OPEN', 'PENDING', 'PARTIAL']))
        result = await db_session.execute(stmt)
        return result.scalars().all()
    
    async def add_order_event(self, trade_id: str, event_type: str, payload: dict, db_session: AsyncSession):
        """Add an order event for audit trail."""
        event_id = str(uuid.uuid4())
        
        event = OrderEvents(
            id=event_id,
            trade_id=trade_id,
            event_type=event_type,
            payload=json.dumps(payload),
            created_at=datetime.utcnow().isoformat()
        )
        
        db_session.add(event)
        await db_session.commit()
        
        logger.debug(f"📋 Order event added: {event_type} for trade {trade_id}")


class PositionRepository:
    """Repository for position-related database operations."""
    
    async def upsert_position(self, position_data: dict, db_session: AsyncSession):
        """Insert or update a position record."""
        symbol = position_data['symbol']
        
        # Check if position exists
        stmt = select(Positions).where(
            (Positions.symbol == symbol) & (Positions.status.in_(['open', 'partial']))
        )
        result = await db_session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing position
            existing.size = position_data.get('size', existing.size)
            existing.entry_price = position_data.get('entry_price', existing.entry_price)
            existing.current_price = position_data.get('current_price', existing.current_price)
            existing.unrealized_pnl = position_data.get('unrealized_pnl', existing.unrealized_pnl)
            existing.realized_pnl = position_data.get('realized_pnl', existing.realized_pnl)
            existing.liquidation_price = position_data.get('liquidation_price', existing.liquidation_price)
            existing.leverage = position_data.get('leverage', existing.leverage)
            existing.last_sync = position_data.get('last_sync') or datetime.utcnow()
            existing.sync_source = position_data.get('sync_source', existing.sync_source)
            
            logger.debug(f"📊 Position updated: {symbol}")
        else:
            # Create new position
            position = Positions(
                id=str(uuid.uuid4()),
                trade_id=position_data.get('trade_id'),
                symbol=symbol,
                size=position_data['size'],
                entry_price=position_data['entry_price'],
                current_price=position_data['current_price'],
                unrealized_pnl=position_data.get('unrealized_pnl', 0),
                realized_pnl=position_data.get('realized_pnl'),
                liquidation_price=position_data.get('liquidation_price'),
                leverage=position_data.get('leverage', 1),
                status=position_data.get('status', 'open'),
                last_sync=position_data.get('last_sync') or datetime.utcnow(),
                sync_source=position_data.get('sync_source', 'manual')
            )
            db_session.add(position)
            logger.info(f"✅ Position created: {symbol}")
        
        await db_session.commit()
    
    async def get_position_by_symbol(self, symbol: str, db_session: AsyncSession) -> Optional[Positions]:
        """Get position by symbol."""
        stmt = select(Positions).where(
            (Positions.symbol == symbol) & (Positions.status.in_(['open', 'partial']))
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_open_positions(self, db_session: AsyncSession) -> List[Positions]:
        """Get all open positions."""
        stmt = select(Positions).where(Positions.status.in_(['open', 'partial']))
        result = await db_session.execute(stmt)
        return result.scalars().all()
    
    async def update_position_price(self, symbol: str, price: float, db_session: AsyncSession):
        """Update position current price."""
        position = await self.get_position_by_symbol(symbol, db_session)
        if position:
            position.current_price = price
            position.last_sync = datetime.utcnow()
            await db_session.commit()
    
    async def close_position(self, symbol: str, db_session: AsyncSession):
        """Mark position as closed."""
        stmt = update(Positions).where(
            (Positions.symbol == symbol) & (Positions.status.in_(['open', 'partial']))
        ).values(
            status='closed',
            last_sync=datetime.utcnow()
        )
        await db_session.execute(stmt)
        await db_session.commit()
        logger.info(f"✅ Position closed: {symbol}")
