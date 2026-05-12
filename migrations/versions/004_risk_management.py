"""Add risk_metrics and circuit_breaker_events tables

Revision ID: 004_risk_management
Revises: 003_order_execution
Create Date: 2026-05-12 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_risk_management'
down_revision: Union[str, None] = '003_order_execution'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add risk management tables."""
    
    # Create risk_metrics table
    op.create_table(
        'risk_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('date', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('starting_balance', sa.Float(), nullable=False),
        sa.Column('current_balance', sa.Float(), nullable=False),
        sa.Column('daily_pnl', sa.Float(), server_default='0', nullable=False),
        sa.Column('daily_pnl_pct', sa.Float(), server_default='0', nullable=False),
        sa.Column('max_drawdown_pct', sa.Float(), server_default='0', nullable=False),
        sa.Column('peak_balance', sa.Float(), nullable=False),
        sa.Column('trade_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('win_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('loss_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('consecutive_losses', sa.Integer(), server_default='0', nullable=False),
        sa.Column('updated_at', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_risk_metrics_user_date', 'risk_metrics', ['user_id', 'date'])
    
    # Create circuit_breaker_events table
    op.create_table(
        'circuit_breaker_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ts', sa.Text(), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('severity', sa.Text(), nullable=False),
        sa.Column('metrics_snapshot', sa.Text(), nullable=True),
        sa.Column('action_taken', sa.Text(), nullable=False),
        sa.Column('resolved_at', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_cb_events_ts', 'circuit_breaker_events', ['ts'])
    op.create_index('idx_cb_events_type', 'circuit_breaker_events', ['event_type'])


def downgrade() -> None:
    """Downgrade schema - remove risk management tables."""
    op.drop_index('idx_cb_events_type', table_name='circuit_breaker_events')
    op.drop_index('idx_cb_events_ts', table_name='circuit_breaker_events')
    op.drop_table('circuit_breaker_events')
    
    op.drop_index('idx_risk_metrics_user_date', table_name='risk_metrics')
    op.drop_table('risk_metrics')
