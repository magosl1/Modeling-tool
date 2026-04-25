-- =============================================================================
-- Phase 0: Entity Architecture Migration
-- Financial Modeling Tool → Universal Modeling Platform
-- =============================================================================
-- Run order: execute this SQL first, then run migrate_phase0.py for data migration

-- Step 1: Add project_type and base_currency to projects
ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_type VARCHAR(50) NOT NULL DEFAULT 'single_entity';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS base_currency VARCHAR(10) NOT NULL DEFAULT 'USD';

-- Populate base_currency from existing currency column
UPDATE projects SET base_currency = currency WHERE base_currency = 'USD' AND currency != 'USD';

-- Step 2: Create entities table
CREATE TABLE IF NOT EXISTS entities (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_entity_id VARCHAR(36) REFERENCES entities(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL DEFAULT 'company_private',
    ticker VARCHAR(20),
    exchange VARCHAR(20),
    currency VARCHAR(10) NOT NULL DEFAULT 'EUR',
    country VARCHAR(50),
    sector VARCHAR(100),
    description VARCHAR(1000),
    ownership_pct DOUBLE PRECISION NOT NULL DEFAULT 100.0,
    consolidation_method VARCHAR(20) NOT NULL DEFAULT 'full',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    start_date VARCHAR(10),
    end_date VARCHAR(10),
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_entities_project_id ON entities(project_id);

-- Step 3: Add entity_id columns to child tables (nullable for backward compat)
ALTER TABLE historical_data ADD COLUMN IF NOT EXISTS entity_id VARCHAR(36) REFERENCES entities(id) ON DELETE CASCADE;
ALTER TABLE projection_assumptions ADD COLUMN IF NOT EXISTS entity_id VARCHAR(36) REFERENCES entities(id) ON DELETE CASCADE;
ALTER TABLE projected_financials ADD COLUMN IF NOT EXISTS entity_id VARCHAR(36) REFERENCES entities(id) ON DELETE CASCADE;

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_historical_data_entity_id ON historical_data(entity_id);
CREATE INDEX IF NOT EXISTS ix_projection_assumptions_entity_id ON projection_assumptions(entity_id);
CREATE INDEX IF NOT EXISTS ix_projected_financials_entity_id ON projected_financials(entity_id);

-- =============================================================================
-- After running this SQL, run: python migrate_phase0.py
-- That script creates one Entity per existing project and backfills entity_id
-- =============================================================================
