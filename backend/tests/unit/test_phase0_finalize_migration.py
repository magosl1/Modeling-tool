"""Integration-style test for the 0002_entity_id_not_null migration.

Spins up SQLite in-memory at the 0001_baseline schema (modeled by
create_all), inserts legacy-shape rows (entity_id IS NULL), runs the
migration via `_ensure_default_entity` + UPDATE logic, and verifies:
  - an Entity now exists per project that had orphan rows
  - all entity_id values are populated
  - a subsequent NOT NULL constraint would hold
"""
import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _load_migration():
    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0002_entity_id_not_null.py"
    spec = importlib.util.spec_from_file_location("mig_0002", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

from app.db.base import Base
from app.models.eliminations import IntercompanyTransaction  # noqa: F401
from app.models.entity import Entity  # noqa: F401
from app.models.project import (  # noqa: F401
    HistoricalData,
    Project,
    ProjectedFinancial,
    ProjectionAssumption,
)
from app.models.user import User


def _seed(session):
    """Insert one project + one legacy HistoricalData row with entity_id=NULL.

    Because the post-migration models have entity_id NOT NULL, we use raw
    SQL for the legacy insert to simulate pre-migration state.
    """
    user = User(
        id=str(uuid.uuid4()),
        email="u@x.com",
        password_hash="x",
        name="u",
        auth_provider="email",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    project = Project(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name="Legacy Co",
        currency="USD",
        scale="thousands",
        projection_years=5,
        status="draft",
    )
    session.add_all([user, project])
    session.commit()

    # Legacy row — bypass the model so we can insert NULL entity_id.
    session.execute(
        sa.text(
            "INSERT INTO historical_data "
            "(id, project_id, entity_id, statement_type, line_item, year, value) "
            "VALUES (:id, :pid, NULL, 'PNL', 'Revenue', 2024, 1000)"
        ),
        {"id": str(uuid.uuid4()), "pid": project.id},
    )
    session.commit()
    return project


def test_migration_backfills_and_tightens():
    mig = _load_migration()

    engine = create_engine("sqlite:///:memory:")
    # Build the tables with entity_id nullable so we can seed legacy state.
    # We temporarily drop the NOT NULL by creating a scoped copy of the table.
    Base.metadata.create_all(engine)
    # SQLite treats ALTER COLUMN ... DROP NOT NULL via batch mode, but the
    # simplest approach for this unit test is to re-create the table without
    # the constraint, mimicking the pre-migration schema.
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE historical_data"))
        conn.execute(sa.text(
            "CREATE TABLE historical_data ("
            "id VARCHAR(36) PRIMARY KEY, project_id VARCHAR(36) NOT NULL, "
            "entity_id VARCHAR(36) NULL, "
            "statement_type VARCHAR(10) NOT NULL, line_item VARCHAR(100) NOT NULL, "
            "bucket VARCHAR(50) NULL, year INTEGER NOT NULL, value NUMERIC(20,4) NOT NULL)"
        ))

    Session = sessionmaker(bind=engine)
    session = Session()
    project = _seed(session)

    # Before: NULL entity_id present.
    nulls_before = session.execute(
        sa.text("SELECT COUNT(*) FROM historical_data WHERE entity_id IS NULL")
    ).scalar()
    assert nulls_before == 1

    # Run the migration's data-backfill logic manually (no Alembic CLI needed).
    conn = session.connection()
    pids = [
        r[0]
        for r in conn.execute(
            sa.text("SELECT DISTINCT project_id FROM historical_data WHERE entity_id IS NULL")
        )
    ]
    for pid in pids:
        eid = mig._ensure_default_entity(conn, pid)
        conn.execute(
            sa.text("UPDATE historical_data SET entity_id = :eid WHERE project_id = :pid AND entity_id IS NULL"),
            {"eid": eid, "pid": pid},
        )
    session.commit()

    # After: no NULLs, and the project has a default entity.
    nulls_after = session.execute(
        sa.text("SELECT COUNT(*) FROM historical_data WHERE entity_id IS NULL")
    ).scalar()
    assert nulls_after == 0

    entities = session.query(Entity).filter(Entity.project_id == project.id).all()
    assert len(entities) == 1
    assert entities[0].name == "Legacy Co"
    assert entities[0].entity_type == "company_private"

    # The row is now attached to that entity.
    attached = session.execute(
        sa.text("SELECT entity_id FROM historical_data WHERE project_id = :pid"),
        {"pid": project.id},
    ).first()
    assert attached[0] == entities[0].id

    session.close()
