"""Add seva_executions table for impact tracking.

Revision ID: add_seva_executions
Revises: dfeaf6951efe
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_seva_executions'
down_revision = 'dfeaf6951efe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM type for seva execution status
    seva_status = postgresql.ENUM(
        'pending', 'executed', 'verified',
        name='seva_execution_status',
        create_type=True
    )
    seva_status.create(op.get_bind(), checkfirst=True)
    
    op.create_table(
        'seva_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('sankalp_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('sankalps.id', ondelete='CASCADE'), 
                  nullable=False, index=True),
        sa.Column('temple_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('temples.id', ondelete='SET NULL'),
                  nullable=True, index=True),
        sa.Column('meals_served', sa.Integer(), nullable=False, default=0),
        sa.Column('status', seva_status, nullable=False, server_default='pending'),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('photo_url', sa.Text(), nullable=True),
        sa.Column('verified_by', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        # Future scalability: batch processing
        sa.Column('batch_id', sa.String(100), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Index for impact aggregation queries
    op.create_index(
        'ix_seva_executions_verified_at',
        'seva_executions',
        ['verified_at'],
        postgresql_where=sa.text("status = 'verified'")
    )


def downgrade() -> None:
    op.drop_index('ix_seva_executions_verified_at', table_name='seva_executions')
    op.drop_table('seva_executions')
    
    # Drop ENUM type
    seva_status = postgresql.ENUM(name='seva_execution_status')
    seva_status.drop(op.get_bind(), checkfirst=True)
