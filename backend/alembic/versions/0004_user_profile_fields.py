"""add password_changed_at and deleted_at to users

Revision ID: 0004_user_profile_fields
Revises: 0003_user_ai_settings
Create Date: 2026-04-27

Supports the user profile feature:
- password_changed_at: bumped on password change so old JWTs are rejected
- deleted_at: soft-delete flag; deleted users cannot authenticate
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_user_profile_fields"
down_revision = "0003_user_ai_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "password_changed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_users_deleted_at",
        "users",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "password_changed_at")
