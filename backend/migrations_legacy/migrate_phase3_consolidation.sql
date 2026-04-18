-- =============================================================================
-- Phase 3: Consolidation Engine migration
--
-- 1. Creates the intercompany_transactions table
-- 2. Adds probability, color, overrides columns to scenarios
-- =============================================================================

-- ── 1. intercompany_transactions ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS intercompany_transactions (
    id              VARCHAR(36) PRIMARY KEY,
    project_id      VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_entity_id  VARCHAR(36) NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity_id    VARCHAR(36) NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    transaction_type VARCHAR(30) NOT NULL DEFAULT 'revenue_cost',
    description     VARCHAR(500) NOT NULL,
    amount_by_year  JSON NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_intercompany_transactions_project_id
    ON intercompany_transactions (project_id);

-- ── 2. Scenario new columns ───────────────────────────────────────────────────
-- Add probability, color, and overrides to the scenarios table.
-- Use IF NOT EXISTS-equivalent pattern (DO block) for idempotency.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scenarios' AND column_name = 'probability'
    ) THEN
        ALTER TABLE scenarios ADD COLUMN probability DOUBLE PRECISION;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scenarios' AND column_name = 'color'
    ) THEN
        ALTER TABLE scenarios ADD COLUMN color VARCHAR(20) DEFAULT '#4472C4';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'scenarios' AND column_name = 'overrides'
    ) THEN
        ALTER TABLE scenarios ADD COLUMN overrides JSON;
    END IF;
END $$;
