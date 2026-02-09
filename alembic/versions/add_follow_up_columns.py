"""Add follow-up columns to sankalps table.

Revision ID: add_follow_up_columns
Revises: add_ritual_lifecycle
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_follow_up_columns'
down_revision = 'add_ritual_lifecycle'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add follow-up tracking columns to sankalps
    op.add_column('sankalps', sa.Column('follow_up_day', sa.Integer(), server_default='0', nullable=False))
    op.add_column('sankalps', sa.Column('next_follow_up_at', sa.DateTime(timezone=True), nullable=True))
    
    # Index for worker queries
    op.create_index('ix_sankalps_next_follow_up_at', 'sankalps', ['next_follow_up_at'])


def downgrade() -> None:
    op.drop_index('ix_sankalps_next_follow_up_at', table_name='sankalps')
    op.drop_column('sankalps', 'next_follow_up_at')
    op.drop_column('sankalps', 'follow_up_day')
