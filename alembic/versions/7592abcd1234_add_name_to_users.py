"""add_name_to_users

Revision ID: 7592abcd1234
Revises: 62746616708a
Create Date: 2026-02-07 20:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7592abcd1234'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'name')
