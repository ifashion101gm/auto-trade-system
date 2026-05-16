"""Add regime column to paper_trades for AI edge tracking

Revision ID: 005_add_regime_column
Revises: 004_risk_management
Create Date: 2026-05-16
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_add_regime_column'
down_revision: Union[str, None] = '004_risk_management'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('paper_trades', sa.Column('regime', sa.Text(), nullable=True))
    op.add_column('paper_trades', sa.Column('base_confidence', sa.Float(), nullable=True))
    op.add_column('paper_trades', sa.Column('adjusted_confidence', sa.Float(), nullable=True))
    op.create_index('idx_paper_trades_regime', 'paper_trades', ['regime'])


def downgrade() -> None:
    op.drop_index('idx_paper_trades_regime', table_name='paper_trades')
    op.drop_column('paper_trades', 'adjusted_confidence')
    op.drop_column('paper_trades', 'base_confidence')
    op.drop_column('paper_trades', 'regime')
