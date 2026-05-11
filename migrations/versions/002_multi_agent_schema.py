"""multi_agent_schema

Revision ID: 002
Revises: 001
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create multi-agent trading system tables."""
    
    # Create trades table (enhanced from paper_trades)
    op.create_table('trades',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('mode', sa.String(length=10), nullable=False),  # 'LIVE' or 'DEMO'
        sa.Column('exchange', sa.String(length=20), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('side', sa.String(length=10), nullable=False),  # 'LONG' or 'SHORT'
        sa.Column('status', sa.String(length=20), nullable=False),  # 'open', 'closed', 'cancelled'
        sa.Column('entry_price', sa.Float, nullable=False),
        sa.Column('current_price', sa.Float, nullable=False),
        sa.Column('exit_price', sa.Float, nullable=True),
        sa.Column('stop_loss', sa.Float, nullable=True),
        sa.Column('take_profit', sa.Float, nullable=True),
        sa.Column('leverage', sa.Integer, nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('pnl', sa.Float, nullable=True),
        sa.Column('pnl_pct', sa.Float, nullable=True),
        sa.Column('exchange_order_id', sa.String(length=100), nullable=True),
        sa.Column('strategy_name', sa.String(length=100), nullable=True),
        sa.Column('regime', sa.String(length=50), nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
        sa.Column('closed_at', sa.DateTime, nullable=True)
    )
    
    # Create positions table (real-time tracking)
    op.create_table('positions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('trade_id', sa.String(length=36), nullable=True),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('size', sa.Float, nullable=False),
        sa.Column('entry_price', sa.Float, nullable=False),
        sa.Column('current_price', sa.Float, nullable=False),
        sa.Column('unrealized_pnl', sa.Float, nullable=False),
        sa.Column('liquidation_price', sa.Float, nullable=True),
        sa.Column('leverage', sa.Integer, nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),  # 'open', 'closed'
        sa.Column('last_sync', sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(['trade_id'], ['trades.id'], )
    )
    
    # Create order_events table (event sourcing)
    op.create_table('order_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('trade_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['trade_id'], ['trades.id'], )
    )
    
    # Create sync_logs table (reconciliation tracking)
    op.create_table('sync_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('timestamp', sa.DateTime, server_default=sa.func.now()),
        sa.Column('source', sa.String(length=20), nullable=False),  # 'mexc_live', 'mexc_demo'
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('data', sa.JSON, nullable=False),
        sa.Column('processed', sa.Boolean, default=False)
    )
    
    # Create telegram_notifications table (notification history)
    op.create_table('telegram_notifications',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('timestamp', sa.DateTime, server_default=sa.func.now()),
        sa.Column('message_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('sent', sa.Boolean, default=False),
        sa.Column('error', sa.Text, nullable=True)
    )
    
    # Create indexes for performance
    op.create_index('idx_trades_status', 'trades', ['status'])
    op.create_index('idx_trades_symbol', 'trades', ['symbol'])
    op.create_index('idx_trades_created_at', 'trades', ['created_at'])
    op.create_index('idx_positions_status', 'positions', ['status'])
    op.create_index('idx_positions_symbol', 'positions', ['symbol'])
    op.create_index('idx_order_events_trade_id', 'order_events', ['trade_id'])
    op.create_index('idx_order_events_type', 'order_events', ['event_type'])
    op.create_index('idx_sync_logs_timestamp', 'sync_logs', ['timestamp'])


def downgrade() -> None:
    """Drop multi-agent trading system tables."""
    op.drop_index('idx_sync_logs_timestamp', table_name='sync_logs')
    op.drop_index('idx_order_events_type', table_name='order_events')
    op.drop_index('idx_order_events_trade_id', table_name='order_events')
    op.drop_index('idx_positions_symbol', table_name='positions')
    op.drop_index('idx_positions_status', table_name='positions')
    op.drop_index('idx_trades_created_at', table_name='trades')
    op.drop_index('idx_trades_symbol', table_name='trades')
    op.drop_index('idx_trades_status', table_name='trades')
    
    op.drop_table('telegram_notifications')
    op.drop_table('sync_logs')
    op.drop_table('order_events')
    op.drop_table('positions')
    op.drop_table('trades')
