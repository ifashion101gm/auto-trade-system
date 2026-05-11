"""add_enhanced_trade_position_fields

Revision ID: ef11f40ce208
Revises: 002
Create Date: 2026-05-12 00:27:26.398545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef11f40ce208'
down_revision: Union[str, Sequence[str], None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add enhanced trade and position fields."""
    
    # Add filled_quantity and error_message to trades table
    op.add_column('trades', sa.Column('filled_quantity', sa.Float, nullable=True))
    op.add_column('trades', sa.Column('error_message', sa.Text, nullable=True))
    
    # Add realized_pnl and sync_source to positions table
    op.add_column('positions', sa.Column('realized_pnl', sa.Float, nullable=True))
    op.add_column('positions', sa.Column('sync_source', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    
    # Remove added columns from positions table
    op.drop_column('positions', 'sync_source')
    op.drop_column('positions', 'realized_pnl')
    
    # Remove added columns from trades table
    op.drop_column('trades', 'error_message')
    op.drop_column('trades', 'filled_quantity')
