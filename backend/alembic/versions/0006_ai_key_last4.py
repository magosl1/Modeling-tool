"""add api_key_last4 to user_ai_settings

Revision ID: 0006_ai_key_last4
Revises: 0005_user_role
Create Date: 2026-04-29

Stores the last 4 characters of the API key so masked previews can be
rendered without ever decrypting the ciphertext on a read path. Closes the
side channel that surfaced the plain key on PUT responses.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_ai_key_last4"
down_revision = "0005_user_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_ai_settings",
        sa.Column("api_key_last4", sa.String(4), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("user_ai_settings", "api_key_last4")
