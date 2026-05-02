"""Add change_log table for global audit trail.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "change_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entity", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("before_json", sa.JSON, nullable=True),
        sa.Column("after_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_change_log_project_created", "change_log", ["project_id", "created_at"])
    op.create_index("ix_change_log_entity", "change_log", ["entity", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_change_log_entity", table_name="change_log")
    op.drop_index("ix_change_log_project_created", table_name="change_log")
    op.drop_table("change_log")
