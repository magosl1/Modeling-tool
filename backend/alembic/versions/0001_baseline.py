"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-18

Baseline revision. The schema at this point is whatever SQLAlchemy's
Base.metadata.create_all() produces from app.models plus the one-off SQL
scripts in backend/migrations_legacy/ (Phase 0, 2, 3).

Existing databases should be stamped to this revision:
    alembic stamp 0001_baseline

Fresh installs create tables via app.db.init_db.create_tables(), which also
stamps this revision automatically.

All future schema changes must go through `alembic revision --autogenerate`.
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentionally empty. See module docstring.
    pass


def downgrade() -> None:
    raise NotImplementedError("Baseline cannot be downgraded.")
