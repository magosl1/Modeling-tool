// ── Entity ───────────────────────────────────────────────

export type EntityType = 'company_listed' | 'company_private' | 'project' | 'division' | 'asset' | 'holdco'
export type ConsolidationMethod = 'full' | 'proportional' | 'equity_method' | 'none'

export interface Entity {
  id: string
  project_id: string
  parent_entity_id: string | null
  name: string
  entity_type: EntityType
  ticker: string | null
  exchange: string | null
  currency: string
  country: string | null
  sector: string | null
  description: string | null
  ownership_pct: number
  consolidation_method: ConsolidationMethod
  is_active: boolean
  start_date: string | null
  end_date: string | null
  display_order: number
  created_at: string
  updated_at: string
}

export interface EntityCreate {
  name: string
  entity_type?: EntityType
  currency?: string
  country?: string | null
  sector?: string | null
  description?: string | null
  ticker?: string | null
  exchange?: string | null
  ownership_pct?: number
  consolidation_method?: ConsolidationMethod
  parent_entity_id?: string | null
  start_date?: string | null
  end_date?: string | null
  display_order?: number
}

export interface EntityUpdate {
  name?: string
  entity_type?: EntityType
  currency?: string
  country?: string | null
  sector?: string | null
  description?: string | null
  ticker?: string | null
  exchange?: string | null
  ownership_pct?: number
  consolidation_method?: ConsolidationMethod
  parent_entity_id?: string | null
  start_date?: string | null
  end_date?: string | null
  is_active?: boolean
  display_order?: number
}

export type ProjectType = 'single_entity' | 'multi_entity' | 'project_finance'

// ── Project ──────────────────────────────────────────────

export interface Project {
  id: string
  name: string
  currency: string
  scale: string
  fiscal_year_end: string | null
  projection_years: number
  status: 'draft' | 'configured' | 'projected' | 'valued'
  project_type: ProjectType
  base_currency: string
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  currency?: string
  scale?: string
  fiscal_year_end?: string | null
  projection_years?: number
  project_type?: ProjectType
  base_currency?: string
}

export interface ProjectUpdate {
  name?: string
  currency?: string
  scale?: string
  fiscal_year_end?: string | null
  projection_years?: number
  project_type?: ProjectType
  base_currency?: string
}

// ── Historical ───────────────────────────────────────────

export type StatementType = 'PNL' | 'BS' | 'CF'

/** year → string value, e.g. { 2023: "1000.0000" } */
export type YearValues = Record<number, string>

/** line_item → year values */
export type StatementData = Record<string, YearValues>

export interface HistoricalResponse {
  PNL: StatementData
  BS: StatementData
  CF: StatementData
}

// ── Assumptions ──────────────────────────────────────────

export interface AssumptionParam {
  param_key: string
  year: number | null
  value: string
}

export interface AssumptionItem {
  id?: string
  line_item: string
  projection_method: string
  params: AssumptionParam[]
}

export type AllAssumptions = Record<string, AssumptionItem[]>

export interface ModuleStatus {
  module: string
  status: 'not_started' | 'configured' | 'complete' | 'error'
}

// ── Projections ──────────────────────────────────────────

export interface ProjectionsResponse {
  PNL: StatementData
  BS: StatementData
  CF: StatementData
  historical_years: number[]
  projected_years: number[]
}

export interface RunProjectionResponse {
  message: string
  projection_years: number[]
  warnings: string[]
}

// ── Valuation ────────────────────────────────────────────

export interface ValuationInputCreate {
  wacc: number
  terminal_growth_rate: number
  exit_multiple?: number | null
  discounting_convention: 'end_of_year' | 'mid_year'
  shares_outstanding?: number | null
}

export interface ValuationResult {
  enterprise_value: string
  net_debt: string
  equity_value: string
  value_per_share: string | null
  terminal_value: string
  pv_fcffs: string
  pv_terminal_value: string
  method_used: 'gordon_growth' | 'exit_multiple'
  fcff_by_year?: Record<string, string>
  sensitivity_table?: Record<string, Record<string, string>>
}

// ── Ratios ───────────────────────────────────────────────

export type RatioCategory = Record<string, YearValues>

export interface RatiosResponse {
  ratios: Record<string, RatioCategory>
  years: number[]
}

// ── Auth ─────────────────────────────────────────────────

export interface AuthTokens {
  access_token: string
  refresh_token: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  name: string
}
