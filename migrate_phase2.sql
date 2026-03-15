-- Phase 2 migration: add scenarios table and scenario_id foreign keys

-- 1. Create scenarios table
CREATE TABLE IF NOT EXISTS scenarios (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    is_base BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_run_at TIMESTAMP
);

-- 2. Add scenario_id to existing tables (guarded)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='projection_assumptions' AND column_name='scenario_id') THEN
        ALTER TABLE projection_assumptions ADD COLUMN scenario_id VARCHAR(36) REFERENCES scenarios(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='revenue_streams' AND column_name='scenario_id') THEN
        ALTER TABLE revenue_streams ADD COLUMN scenario_id VARCHAR(36) REFERENCES scenarios(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='nol_balances' AND column_name='scenario_id') THEN
        ALTER TABLE nol_balances ADD COLUMN scenario_id VARCHAR(36) REFERENCES scenarios(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='projected_financials' AND column_name='scenario_id') THEN
        ALTER TABLE projected_financials ADD COLUMN scenario_id VARCHAR(36) REFERENCES scenarios(id) ON DELETE CASCADE;
    END IF;
END $$;

-- 3. Remove old UniqueConstraints that didn't include scenario_id so they can be recreated correctly
-- (SQLAlchemy will handle the new constraints on next create_all; these are safe no-ops if they don't exist)
-- Just drop old constraints if they block the new ones:
ALTER TABLE nol_balances DROP CONSTRAINT IF EXISTS nol_balances_project_id_year_key;
ALTER TABLE projected_financials DROP CONSTRAINT IF EXISTS projected_financials_project_id_statement_type_line_item_year_key;

-- 4. Add new unique constraints including scenario_id
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name='nol_balances_project_id_scenario_id_year_key') THEN
        ALTER TABLE nol_balances ADD CONSTRAINT nol_balances_project_id_scenario_id_year_key UNIQUE (project_id, scenario_id, year);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name='projected_financials_unique') THEN
        ALTER TABLE projected_financials ADD CONSTRAINT projected_financials_unique UNIQUE (project_id, scenario_id, statement_type, line_item, year);
    END IF;
END $$;

-- 5. Create new Phase 2 tables
CREATE TABLE IF NOT EXISTS revolver_configs (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scenario_id VARCHAR(36) REFERENCES scenarios(id) ON DELETE CASCADE,
    revolver_limit NUMERIC(20,4) DEFAULT 0,
    revolver_rate NUMERIC(10,6) DEFAULT 0,
    minimum_cash_balance NUMERIC(20,4) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS debt_tranches (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scenario_id VARCHAR(36) REFERENCES scenarios(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    principal NUMERIC(20,4) NOT NULL,
    rate NUMERIC(10,6) NOT NULL,
    maturity_year INTEGER NOT NULL,
    amortization_method VARCHAR(50) DEFAULT 'bullet',
    display_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fx_rates (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    fx_rate NUMERIC(20,8) NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_results (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scenario_id VARCHAR(36) REFERENCES scenarios(id) ON DELETE CASCADE,
    results_json JSONB,
    ran_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_shares (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    shared_with_user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'viewer',
    invited_at TIMESTAMP DEFAULT NOW()
);

SELECT 'Phase 2 migration complete' AS status;
