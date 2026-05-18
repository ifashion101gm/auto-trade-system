"""add_risk_state_table

Revision ID: 006
Revises: ef11f40ce208
Create Date: 2026-05-18

Migration to add risk_state table for single-source-of-truth risk state management.
Replaces .risk_state.json file with PostgreSQL persistence.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = 'ef11f40ce208'
branch_labels = None
depends_on = None


def upgrade():
    """Add risk_state table for persistent risk engine state."""
    op.create_table(
        'risk_state',
        sa.Column('id', sa.Integer(), primary_key=True, server_default='1'),
        sa.Column('daily_loss_lock_active', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('drawdown_lock_active', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('daily_pnl', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('daily_pnl_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_balance', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('peak_balance', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('today_date', sa.String(length=10), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Insert initial row with defaults
    op.execute(
        "INSERT INTO risk_state (id, daily_loss_lock_active, drawdown_lock_active, "
        "daily_pnl, daily_pnl_pct, current_balance, peak_balance, today_date) "
        "VALUES (1, 0, 0, 0.0, 0.0, 0.0, 0.0, NULL) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade():
    """Remove risk_state table."""
    op.drop_table('risk_state')
