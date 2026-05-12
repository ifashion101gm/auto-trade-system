"""Add order execution engine tables.

Revision ID: 003_order_execution
Revises: ef11f40ce208
Create Date: 2026-05-12

Adds:
- orders: Individual order lifecycle tracking
- execution_logs: Detailed execution attempt logs
- risk_events: Risk check records
- recovery_events: Reconciliation action logs
- signals: Trade input signals
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_order_execution'
down_revision = 'ef11f40ce208'
branch_labels = None
depends_on = None


def upgrade():
    """Create order execution engine tables."""
    
    # Table: orders
    op.create_table(
        'orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('client_order_id', sa.String(100), nullable=False, unique=True),
        sa.Column('trade_id', sa.String(36), sa.ForeignKey('trades.id'), nullable=True),
        sa.Column('exchange', sa.String(20), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('quantity', sa.Float, nullable=False),
        sa.Column('filled_quantity', sa.Float, nullable=False, server_default='0'),
        sa.Column('remaining_quantity', sa.Float, nullable=False, server_default='0'),
        sa.Column('price', sa.Float, nullable=True),
        sa.Column('average_fill_price', sa.Float, nullable=True),
        sa.Column('stop_loss', sa.Float, nullable=True),
        sa.Column('take_profit', sa.Float, nullable=True),
        sa.Column('leverage', sa.Integer, nullable=True),
        sa.Column('reduce_only', sa.Integer, nullable=False, server_default='0'),
        sa.Column('time_in_force', sa.String(20), nullable=True, server_default='GTC'),
        sa.Column('exchange_order_id', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=True, onupdate=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime, nullable=True),
        sa.Column('filled_at', sa.DateTime, nullable=True),
        sa.Column('canceled_at', sa.DateTime, nullable=True),
    )
    
    op.create_index('idx_orders_client_order_id', 'orders', ['client_order_id'])
    op.create_index('idx_orders_trade_id', 'orders', ['trade_id'])
    op.create_index('idx_orders_exchange_symbol', 'orders', ['exchange', 'symbol'])
    op.create_index('idx_orders_status_created', 'orders', ['status', 'created_at'])
    
    # Table: execution_logs
    op.create_table(
        'execution_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('trade_id', sa.String(36), sa.ForeignKey('trades.id'), nullable=True),
        sa.Column('order_id', sa.String(36), sa.ForeignKey('orders.id'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('exchange', sa.String(20), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('request_payload', sa.Text, nullable=True),
        sa.Column('response_payload', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('latency_ms', sa.Float, nullable=True),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
    )
    
    op.create_index('idx_execution_logs_trade', 'execution_logs', ['trade_id'])
    op.create_index('idx_execution_logs_timestamp', 'execution_logs', ['timestamp'])
    
    # Table: risk_events
    op.create_table(
        'risk_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('trade_id', sa.String(36), sa.ForeignKey('trades.id'), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('risk_level', sa.String(20), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('metrics_json', sa.Text, nullable=True),
        sa.Column('action_taken', sa.String(100), nullable=True),
        sa.Column('validator_version', sa.String(20), nullable=True),
    )
    
    op.create_index('idx_risk_events_trade', 'risk_events', ['trade_id'])
    op.create_index('idx_risk_events_type', 'risk_events', ['event_type'])
    
    # Table: recovery_events
    op.create_table(
        'recovery_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('recovery_type', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('exchange', sa.String(20), nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('old_state', sa.Text, nullable=True),
        sa.Column('new_state', sa.Text, nullable=True),
        sa.Column('auto_repaired', sa.Integer, nullable=False, server_default='0'),
        sa.Column('requires_manual_review', sa.Integer, nullable=False, server_default='0'),
        sa.Column('trade_id', sa.String(36), sa.ForeignKey('trades.id'), nullable=True),
    )
    
    op.create_index('idx_recovery_events_type', 'recovery_events', ['recovery_type'])
    op.create_index('idx_recovery_events_timestamp', 'recovery_events', ['timestamp'])
    
    # Table: signals
    op.create_table(
        'signals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('signal_type', sa.String(20), nullable=False),
        sa.Column('strength', sa.Float, nullable=False),
        sa.Column('indicators_json', sa.Text, nullable=True),
        sa.Column('regime', sa.String(50), nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('trade_id', sa.String(36), sa.ForeignKey('trades.id'), nullable=True),
        sa.Column('processed', sa.Integer, nullable=False, server_default='0'),
    )
    
    op.create_index('idx_signals_symbol_time', 'signals', ['symbol', 'timestamp'])
    op.create_index('idx_signals_trade', 'signals', ['trade_id'])


def downgrade():
    """Drop order execution engine tables."""
    op.drop_index('idx_signals_trade', table_name='signals')
    op.drop_index('idx_signals_symbol_time', table_name='signals')
    op.drop_table('signals')
    
    op.drop_index('idx_recovery_events_timestamp', table_name='recovery_events')
    op.drop_index('idx_recovery_events_type', table_name='recovery_events')
    op.drop_table('recovery_events')
    
    op.drop_index('idx_risk_events_type', table_name='risk_events')
    op.drop_index('idx_risk_events_trade', table_name='risk_events')
    op.drop_table('risk_events')
    
    op.drop_index('idx_execution_logs_timestamp', table_name='execution_logs')
    op.drop_index('idx_execution_logs_trade', table_name='execution_logs')
    op.drop_table('execution_logs')
    
    op.drop_index('idx_orders_status_created', table_name='orders')
    op.drop_index('idx_orders_exchange_symbol', table_name='orders')
    op.drop_index('idx_orders_trade_id', table_name='orders')
    op.drop_index('idx_orders_client_order_id', table_name='orders')
    op.drop_table('orders')
