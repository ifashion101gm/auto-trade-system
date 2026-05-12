"""Database repositories for order execution engine."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.models import Orders, Positions, Trades
from typing import List, Optional


class OrderRepository:
    """Repository for order operations."""
    
    async def get_pending_orders(self, db_session: AsyncSession) -> List[Orders]:
        """Get all pending/open orders."""
        stmt = select(Orders).where(
            Orders.status.in_(['PENDING', 'PARTIALLY_FILLED'])
        )
        result = await db_session.execute(stmt)
        return result.scalars().all()
    
    async def get_order_by_client_id(self, client_order_id: str, db_session: AsyncSession) -> Optional[Orders]:
        """Get order by client order ID (idempotency check)."""
        stmt = select(Orders).where(Orders.client_order_id == client_order_id)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create_order(self, order_data: dict, db_session: AsyncSession) -> Orders:
        """Create new order record."""
        order = Orders(**order_data)
        db_session.add(order)
        await db_session.flush()
        return order
    
    async def update_order_status(self, order_id: str, new_status: str, db_session: AsyncSession):
        """Update order status."""
        stmt = select(Orders).where(Orders.id == order_id)
        result = await db_session.execute(stmt)
        order = result.scalar_one_or_none()
        
        if order:
            order.status = new_status
            await db_session.commit()


class PositionRepository:
    """Repository for position operations."""
    
    async def get_open_positions(self, db_session: AsyncSession) -> List[Positions]:
        """Get all open positions."""
        stmt = select(Positions).where(Positions.status == 'open')
        result = await db_session.execute(stmt)
        return result.scalars().all()
    
    async def get_position_by_symbol(self, symbol: str, db_session: AsyncSession) -> Optional[Positions]:
        """Get position by symbol."""
        stmt = select(Positions).where(
            Positions.symbol == symbol,
            Positions.status == 'open'
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def upsert_position(self, position_data: dict, db_session: AsyncSession):
        """Create or update position."""
        existing = await self.get_position_by_symbol(position_data['symbol'], db_session)
        
        if existing:
            for key, value in position_data.items():
                setattr(existing, key, value)
        else:
            import uuid
            position = Positions(id=str(uuid.uuid4()), **position_data)
            db_session.add(position)


class TradeRepository:
    """Repository for trade operations."""
    
    async def get_open_trades(self, db_session: AsyncSession) -> List[Trades]:
        """Get all open trades."""
        stmt = select(Trades).where(Trades.status.in_(['OPEN', 'PENDING', 'PARTIAL']))
        result = await db_session.execute(stmt)
        return result.scalars().all()
    
    async def get_open_trade_by_symbol(self, symbol: str, db_session: AsyncSession) -> Optional[Trades]:
        """Get open trade by symbol."""
        stmt = select(Trades).where(
            Trades.symbol == symbol,
            Trades.status.in_(['OPEN', 'PENDING', 'PARTIAL'])
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_trade(self, trade_id: str, db_session: AsyncSession) -> Optional[Trades]:
        """Get trade by ID."""
        stmt = select(Trades).where(Trades.id == trade_id)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
