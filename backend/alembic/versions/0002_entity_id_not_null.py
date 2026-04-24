"""phase 0 finalize — make entity_id NOT NULL on historical/assumption/projected tables

Revision ID: 0002_entity_id_not_null
Revises: 0001_baseline
Create Date: 2026-04-19

Closes the Phase 0 transition. Before this migration, `entity_id` was
nullable on `historical_data`, `projection_assumptions`, and
`projected_financials` so rows created before Phase 0 could coexist with
Phase 0-aware rows.

Steps:
    1. For every project that has rows with entity_id IS NULL, ensure an
       Entity exists (create a default one named after the project).
    2. Update NULL entity_ids to that project's default entity.
    3. ALTER the column to NOT NULL on the three affected tables.

After this runs, every row is attributable to a specific entity, and
the "legacy single-entity" branches in the application code become
dead code (see the route-layer cleanup in the same PR).
"""
from __future__ import annotations

import uuid

import sqlalchemy as sa

from alembic import op

revision = "0002_entity_id_not_null"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


TABLES = ("historical_data", "projection_assumptions", "projected_financials")


def _ensure_default_entity(conn, project_id: str) -> str:
    """Return an entity_id owned by `project_id`, creating a default one if needed."""
    row = conn.execute(
        sa.text("SELECT id FROM entities WHERE project_id = :pid ORDER BY display_order LIMIT 1"),
        {"pid": project_id},
    ).first()
    if row:
        return row[0]

    # Pull a few project fields needed to seed the entity.
    proj = conn.execute(
        sa.text("SELECT name, currency FROM projects WHERE id = :pid"),
        {"pid": project_id},
    ).first()
    if not proj:
        # Orphan rows — should not happen thanks to FK, but guard anyway.
        raise RuntimeError(f"Cannot backfill: project {project_id} missing")

    entity_id = str(uuid.uuid4())
    conn.execute(
        sa.text(
            """
            INSERT INTO entities (
                id, project_id, parent_entity_id, name, entity_type,
                currency, ownership_pct, consolidation_method,
                is_active, display_order, created_at, updated_at
            ) VALUES (
                :id, :pid, NULL, :name, 'company_private',
                :currency, 100.0, 'full',
                TRUE, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        ),
        {"id": entity_id, "pid": project_id, "name": proj[0], "currency": proj[1]},
    )
    return entity_id


def upgrade() -> None:
    conn = op.get_bind()

    # 1 + 2: backfill NULL entity_ids, grouped by project_id.
    for table in TABLES:
        project_ids = [
            r[0]
            for r in conn.execute(
                sa.text(
                    f"SELECT DISTINCT project_id FROM {table} WHERE entity_id IS NULL"
                )
            )
        ]
        for pid in project_ids:
            entity_id = _ensure_default_entity(conn, pid)
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET entity_id = :eid "
                    f"WHERE project_id = :pid AND entity_id IS NULL"
                ),
                {"eid": entity_id, "pid": pid},
            )

    # 3: ALTER the columns to NOT NULL.
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("entity_id", existing_type=sa.String(length=36), nullable=False)


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("entity_id", existing_type=sa.String(length=36), nullable=True)
