"""Add rationale column to projection_assumptions

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-02 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'projection_assumptions',
        sa.Column('rationale', sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('projection_assumptions', 'rationale')
