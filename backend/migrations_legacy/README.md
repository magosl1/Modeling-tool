# Legacy migrations

One-off SQL and Python scripts that predate Alembic versioning. They bring a
pre-Phase 0 database up to the current schema.

## Order

1. `migrate_phase0_entities.sql`          — creates `entities`, adds `entity_id` FKs
2. `migrate_phase0.py`                    — backfills default entities, populates `entity_id`
3. `migrate_phase0b_entity_constraints.sql` — additional entity constraints
4. `migrate_phase2.sql`                   — scenarios, debt, FX, project sharing
5. `migrate_phase3_consolidation.sql`     — intercompany eliminations, external curves

After running all five, stamp Alembic at the baseline revision:

```bash
cd backend
alembic stamp 0001_baseline
```

All future schema changes must go through `alembic revision --autogenerate`.
Do not add new scripts to this folder.
