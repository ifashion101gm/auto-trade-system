"""add_signal_tracking_indexes

Revision ID: 003
Revises: ef11f40ce208
Create Date: 2026-05-13

Add indexes for webhook signal tracking
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, Sequence[str], None] = 'ef11f40ce208'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add signal tracking indexes."""
    
    # Add index on source for filtering external signals
    op.create_index('idx_signals_source', 'signals', ['source'])
    
    # Add index on processed status for finding unprocessed signals
    op.create_index('idx_signals_processed', 'signals', ['processed'])
    
    # Add notes column if not exists (for storing webhook metadata)
    # Note: Check if column exists first in production
    try:
        op.add_column('signals', sa.Column('notes', sa.Text, nullable=True))
    except Exception:
        pass  # Column already exists


def downgrade() -> None:
    """Downgrade schema."""
    
    op.drop_index('idx_signals_processed', table_name='signals')
    op.drop_index('idx_signals_source', table_name='signals')
    op.drop_column('signals', 'notes')
