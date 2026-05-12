"""
Async repository pattern for clean database access.
Provides centralized data access methods for trades and positions.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Trades, Positions, OrderEvents, Orders, ExecutionLogs, RiskEvents, RecoveryEvents, Signals
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


class OrderRepository:
    """Repository for order lifecycle operations."""
    
    async def create_order(self, order_data: dict, db_session: AsyncSession) -> Orders:
        """Create a new order record."""
        order_id = order_data.get('id', str(uuid.uuid4()))
        
        order = Orders(
            id=order_id,
            client_order_id=order_data['client_order_id'],
            trade_id=order_data.get('trade_id'),
            exchange=order_data['exchange'],
            symbol=order_data['symbol'],
            side=order_data['side'],
            order_type=order_data.get('order_type', 'MARKET'),
            status=order_data.get('status', 'NEW'),
            quantity=order_data['quantity'],
            filled_quantity=order_data.get('filled_quantity', 0),
            remaining_quantity=order_data.get('remaining_quantity', order_data['quantity']),
            price=order_data.get('price'),
            average_fill_price=order_data.get('average_fill_price'),
            stop_loss=order_data.get('stop_loss'),
            take_profit=order_data.get('take_profit'),
            leverage=order_data.get('leverage'),
            reduce_only=order_data.get('reduce_only', 0),
            time_in_force=order_data.get('time_in_force', 'GTC'),
            exchange_order_id=order_data.get('exchange_order_id'),
            error_message=order_data.get('error_message')
        )
        
        db_session.add(order)
        await db_session.commit()
        await db_session.refresh(order)
        
        logger.info(f"✅ Order created: {order_id} (client_id: {order.client_order_id})")
        return order
    
    async def get_order(self, order_id: str, db_session: AsyncSession) -> Optional[Orders]:
        """Get a single order by ID."""
        stmt = select(Orders).where(Orders.id == order_id)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_order_by_client_id(self, client_order_id: str, db_session: AsyncSession) -> Optional[Orders]:
        """Get order by client order ID (for idempotency checks)."""
        stmt = select(Orders).where(Orders.client_order_id == client_order_id)
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_order_status(self, order_id: str, new_status: str, db_session: AsyncSession):
        """Update order status with timestamp."""
        from datetime import datetime
        
        order = await self.get_order(order_id, db_session)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        old_status = order.status
        order.status = new_status
        order.updated_at = datetime.utcnow()
        
        # Set terminal state timestamps
        if new_status == 'FILLED' and not order.filled_at:
            order.filled_at = datetime.utcnow()
        elif new_status in ['CANCELED', 'REJECTED', 'EXPIRED'] and not order.canceled_at:
            order.canceled_at = datetime.utcnow()
        
        await db_session.commit()
        logger.info(f"📝 Order {order_id} status updated: {old_status} -> {new_status}")
    
    async def update_order_fills(self, order_id: str, filled_qty: float, avg_price: float, db_session: AsyncSession):
        """Update order fill information."""
        order = await self.get_order(order_id, db_session)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        order.filled_quantity = filled_qty
        order.remaining_quantity = order.quantity - filled_qty
        order.average_fill_price = avg_price
        order.updated_at = datetime.utcnow()
        
        # Auto-update status if fully filled
        if filled_qty >= order.quantity:
            order.status = 'FILLED'
            order.filled_at = datetime.utcnow()
        elif filled_qty > 0:
            order.status = 'PARTIALLY_FILLED'
        
        await db_session.commit()
        logger.debug(f"📊 Order {order_id} fills updated: {filled_qty}/{order.quantity}")
    
    async def get_open_orders(self, db_session: AsyncSession) -> List[Orders]:
        """Get all open/pending orders."""
        stmt = select(Orders).where(
            Orders.status.in_(['NEW', 'PENDING', 'PARTIALLY_FILLED'])
        )
        result = await db_session.execute(stmt)
        return result.scalars().all()
    
    async def get_orders_by_trade(self, trade_id: str, db_session: AsyncSession) -> List[Orders]:
        """Get all orders associated with a trade."""
        stmt = select(Orders).where(Orders.trade_id == trade_id).order_by(Orders.created_at)
        result = await db_session.execute(stmt)
        return result.scalars().all()


class ExecutionLogRepository:
    """Repository for execution log operations."""
    
    async def log_execution(self, log_data: dict, db_session: AsyncSession):
        """Log an execution attempt."""
        log_id = str(uuid.uuid4())
        
        log = ExecutionLogs(
            id=log_id,
            trade_id=log_data.get('trade_id'),
            order_id=log_data.get('order_id'),
            action=log_data['action'],
            exchange=log_data['exchange'],
            symbol=log_data['symbol'],
            request_payload=json.dumps(log_data.get('request_payload')) if log_data.get('request_payload') else None,
            response_payload=json.dumps(log_data.get('response_payload')) if log_data.get('response_payload') else None,
            status=log_data['status'],
            error_message=log_data.get('error_message'),
            latency_ms=log_data.get('latency_ms'),
            retry_count=log_data.get('retry_count', 0)
        )
        
        db_session.add(log)
        await db_session.commit()
        logger.debug(f"📋 Execution logged: {log_data['action']} ({log_data['status']})")
    
    async def get_logs_by_trade(self, trade_id: str, db_session: AsyncSession) -> List[ExecutionLogs]:
        """Get all execution logs for a trade."""
        stmt = select(ExecutionLogs).where(
            ExecutionLogs.trade_id == trade_id
        ).order_by(ExecutionLogs.timestamp)
        result = await db_session.execute(stmt)
        return result.scalars().all()


class RiskEventRepository:
    """Repository for risk event operations."""
    
    async def record_risk_event(self, event_data: dict, db_session: AsyncSession):
        """Record a risk check or violation."""
        event_id = str(uuid.uuid4())
        
        event = RiskEvents(
            id=event_id,
            trade_id=event_data.get('trade_id'),
            event_type=event_data['event_type'],
            risk_level=event_data['risk_level'],
            description=event_data['description'],
            metrics_json=json.dumps(event_data.get('metrics')) if event_data.get('metrics') else None,
            action_taken=event_data.get('action_taken'),
            validator_version=event_data.get('validator_version')
        )
        
        db_session.add(event)
        await db_session.commit()
        logger.info(f"⚠️  Risk event recorded: {event_data['event_type']} ({event_data['risk_level']})")
    
    async def get_recent_violations(self, db_session: AsyncSession, hours: int = 24) -> List[RiskEvents]:
        """Get recent risk violations."""
        from datetime import datetime, timedelta
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        stmt = select(RiskEvents).where(
            (RiskEvents.risk_level.in_(['HIGH', 'CRITICAL'])) &
            (RiskEvents.timestamp >= cutoff)
        ).order_by(RiskEvents.timestamp.desc())
        result = await db_session.execute(stmt)
        return result.scalars().all()


class RecoveryEventRepository:
    """Repository for recovery event operations."""
    
    async def log_recovery(self, event_data: dict, db_session: AsyncSession):
        """Log a reconciliation/recovery action."""
        event_id = str(uuid.uuid4())
        
        event = RecoveryEvents(
            id=event_id,
            recovery_type=event_data['recovery_type'],
            symbol=event_data['symbol'],
            exchange=event_data['exchange'],
            description=event_data['description'],
            old_state=json.dumps(event_data.get('old_state')) if event_data.get('old_state') else None,
            new_state=json.dumps(event_data.get('new_state')) if event_data.get('new_state') else None,
            auto_repaired=event_data.get('auto_repaired', 0),
            requires_manual_review=event_data.get('requires_manual_review', 0),
            trade_id=event_data.get('trade_id')
        )
        
        db_session.add(event)
        await db_session.commit()
        logger.info(f"🔧 Recovery logged: {event_data['recovery_type']} for {event_data['symbol']}")
    
    async def get_pending_reviews(self, db_session: AsyncSession) -> List[RecoveryEvents]:
        """Get recovery events requiring manual review."""
        stmt = select(RecoveryEvents).where(
            RecoveryEvents.requires_manual_review == 1
        ).order_by(RecoveryEvents.timestamp.desc())
        result = await db_session.execute(stmt)
        return result.scalars().all()


class SignalRepository:
    """Repository for signal operations."""
    
    async def record_signal(self, signal_data: dict, db_session: AsyncSession):
        """Record a trading signal."""
        signal_id = str(uuid.uuid4())
        
        signal = Signals(
            id=signal_id,
            source=signal_data['source'],
            symbol=signal_data['symbol'],
            signal_type=signal_data['signal_type'],
            strength=signal_data['strength'],
            indicators_json=json.dumps(signal_data.get('indicators')) if signal_data.get('indicators') else None,
            regime=signal_data.get('regime'),
            confidence=signal_data.get('confidence'),
            trade_id=signal_data.get('trade_id'),
            processed=signal_data.get('processed', 0)
        )
        
        db_session.add(signal)
        await db_session.commit()
        logger.debug(f"📡 Signal recorded: {signal_data['signal_type']} for {signal_data['symbol']}")
    
    async def get_unprocessed_signals(self, db_session: AsyncSession) -> List[Signals]:
        """Get signals that haven't been processed yet."""
        stmt = select(Signals).where(
            Signals.processed == 0
        ).order_by(Signals.timestamp)
        result = await db_session.execute(stmt)
        return result.scalars().all()
