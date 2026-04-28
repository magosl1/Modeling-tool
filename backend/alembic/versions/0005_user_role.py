"""add role column to users

Revision ID: 0005_user_role
Revises: 0004_user_profile_fields
Create Date: 2026-04-27

Introduces the user role hierarchy: user | admin | master_admin.
- user         : default; only access their own data
- admin        : read-only access to /admin/* (stats, user list)
- master_admin : full /admin/* including role mutations and deactivation
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_user_role"
down_revision = "0004_user_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.Enum("user", "admin", "master_admin", name="user_role_enum"),
            nullable=False,
            server_default="user",
        ),
    )
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
