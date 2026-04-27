"""add user_ai_settings table

Revision ID: 0003_user_ai_settings
Revises: 0002_entity_id_not_null
Create Date: 2026-04-25

Stores encrypted API keys and model preferences per user for the
AI-powered historical data ingestion pipeline.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_user_ai_settings"
down_revision = "0002_entity_id_not_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_ai_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "provider",
            sa.Enum("google", "anthropic", "openai", name="ai_provider_enum"),
            nullable=False,
            server_default="google",
        ),
        sa.Column("api_key_encrypted", sa.Text, nullable=False),
        sa.Column("cheap_model", sa.String(100), nullable=False, server_default="gemini-2.5-flash"),
        sa.Column("smart_model", sa.String(100), nullable=False, server_default="gemini-2.5-pro"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_ai_settings_user_id", "user_ai_settings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_ai_settings_user_id", table_name="user_ai_settings")
    op.drop_table("user_ai_settings")
    # Clean up the enum type (PostgreSQL-specific).
    op.execute("DROP TYPE IF EXISTS ai_provider_enum")
