"""
Phase 0 data migration: Entity Architecture.

Run AFTER migrate_phase0_entities.sql has been applied.

What this script does:
1. For every existing project, creates one default Entity with the project's metadata.
2. Backfills entity_id on historical_data, projection_assumptions, projected_financials.
3. Verifies referential integrity.
4. Prints a summary report.

Usage:
    python migrate_phase0.py

Environment variables (or .env file in current directory):
    DATABASE_URL  e.g. postgresql://fm_user:fm_password@localhost:5432/financial_modeler
"""
import os
import sys
import uuid
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))
except ImportError:
    pass

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set.")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def run_migration():
    with engine.begin() as conn:
        # ------------------------------------------------------------------
        # 1. Load all existing projects
        # ------------------------------------------------------------------
        projects = conn.execute(text(
            "SELECT id, name, currency FROM projects ORDER BY created_at"
        )).fetchall()
        print(f"Found {len(projects)} existing projects.")

        created_entities = 0
        backfilled_historical = 0
        backfilled_assumptions = 0
        backfilled_projections = 0

        for project in projects:
            project_id = project.id
            project_name = project.name
            project_currency = project.currency

            # Check if a default entity already exists for this project
            existing = conn.execute(text(
                "SELECT id FROM entities WHERE project_id = :pid LIMIT 1"
            ), {"pid": project_id}).fetchone()

            if existing:
                entity_id = existing.id
                print(f"  Project '{project_name}': entity already exists ({entity_id})")
            else:
                # Create default entity
                entity_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(text("""
                    INSERT INTO entities
                        (id, project_id, parent_entity_id, name, entity_type, currency,
                         ownership_pct, consolidation_method, is_active, display_order,
                         created_at, updated_at)
                    VALUES
                        (:id, :project_id, NULL, :name, 'company_private', :currency,
                         100.0, 'full', TRUE, 0,
                         :created_at, :updated_at)
                """), {
                    "id": entity_id,
                    "project_id": project_id,
                    "name": project_name,
                    "currency": project_currency,
                    "created_at": now,
                    "updated_at": now,
                })
                created_entities += 1
                print(f"  Project '{project_name}': created entity {entity_id}")

            # ------------------------------------------------------------------
            # 2. Backfill entity_id on child tables
            # ------------------------------------------------------------------
            result = conn.execute(text("""
                UPDATE historical_data
                SET entity_id = :eid
                WHERE project_id = :pid AND entity_id IS NULL
            """), {"eid": entity_id, "pid": project_id})
            backfilled_historical += result.rowcount

            result = conn.execute(text("""
                UPDATE projection_assumptions
                SET entity_id = :eid
                WHERE project_id = :pid AND entity_id IS NULL
            """), {"eid": entity_id, "pid": project_id})
            backfilled_assumptions += result.rowcount

            result = conn.execute(text("""
                UPDATE projected_financials
                SET entity_id = :eid
                WHERE project_id = :pid AND entity_id IS NULL
            """), {"eid": entity_id, "pid": project_id})
            backfilled_projections += result.rowcount

        # ------------------------------------------------------------------
        # 3. Verification
        # ------------------------------------------------------------------
        null_hist = conn.execute(text(
            "SELECT COUNT(*) FROM historical_data WHERE entity_id IS NULL"
        )).scalar()
        null_assump = conn.execute(text(
            "SELECT COUNT(*) FROM projection_assumptions WHERE entity_id IS NULL"
        )).scalar()
        null_proj = conn.execute(text(
            "SELECT COUNT(*) FROM projected_financials WHERE entity_id IS NULL"
        )).scalar()

        # ------------------------------------------------------------------
        # 4. Summary
        # ------------------------------------------------------------------
        print("\n=== Migration Summary ===")
        print(f"  Projects processed:              {len(projects)}")
        print(f"  Entities created:                {created_entities}")
        print(f"  historical_data rows backfilled: {backfilled_historical}")
        print(f"  projection_assumptions backfilled: {backfilled_assumptions}")
        print(f"  projected_financials backfilled: {backfilled_projections}")
        print(f"\n  Rows still missing entity_id:")
        print(f"    historical_data:        {null_hist}")
        print(f"    projection_assumptions: {null_assump}")
        print(f"    projected_financials:   {null_proj}")

        if null_hist == 0 and null_assump == 0 and null_proj == 0:
            print("\n  All rows have entity_id. Migration successful!")
        else:
            print("\n  WARNING: Some rows still have NULL entity_id. Check data integrity.")

if __name__ == "__main__":
    run_migration()
