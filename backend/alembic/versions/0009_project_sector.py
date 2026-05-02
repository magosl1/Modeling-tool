"""Add sector column to projects

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable on purpose — existing projects predate the sector catalog and
    # will fall through to the 'generic' defaults at read time.
    op.add_column('projects', sa.Column('sector', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'sector')
