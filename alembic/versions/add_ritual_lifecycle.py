"""Add ritual lifecycle columns to users and create ritual_events table.

Revision ID: add_ritual_lifecycle
Revises: add_seva_executions
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_ritual_lifecycle'
down_revision = 'add_seva_executions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ritual columns to users table
    op.add_column('users', sa.Column('ritual_cycle_day', sa.Integer(), server_default='1', nullable=False))
    op.add_column('users', sa.Column('ritual_cycle_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('last_sankalp_prompt_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('ritual_phase', sa.String(20), server_default='INITIATION', nullable=False))
    op.add_column('users', sa.Column('ritual_intensity_score', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('last_chinta_category', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('total_sankalps_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('sankalp_prompts_this_month', sa.Integer(), server_default='0', nullable=False))
    
    # Create ritual_events analytics table
    op.create_table(
        'ritual_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('ritual_phase', sa.String(20), nullable=True),
        sa.Column('conversion_flag', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Index for analytics queries
    op.create_index('ix_ritual_events_event_type', 'ritual_events', ['event_type'])
    op.create_index('ix_ritual_events_created_at', 'ritual_events', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ritual_events_created_at', table_name='ritual_events')
    op.drop_index('ix_ritual_events_event_type', table_name='ritual_events')
    op.drop_table('ritual_events')
    
    op.drop_column('users', 'sankalp_prompts_this_month')
    op.drop_column('users', 'total_sankalps_count')
    op.drop_column('users', 'last_chinta_category')
    op.drop_column('users', 'ritual_intensity_score')
    op.drop_column('users', 'ritual_phase')
    op.drop_column('users', 'last_sankalp_prompt_at')
    op.drop_column('users', 'ritual_cycle_started_at')
    op.drop_column('users', 'ritual_cycle_day')
