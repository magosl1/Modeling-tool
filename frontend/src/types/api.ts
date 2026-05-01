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
  fcff_build_up?: Record<string, Record<string, string>>
  normalized_terminal_year?: number | null
  terminal_fcff_build_up?: Record<string, string>
  implied_multiples?: Record<string, Record<string, string | null>>
  sensitivity_table?: Record<string, Record<string, string>>
}

// ── Ratios ───────────────────────────────────────────────

export type RatioCategory = Record<string, YearValues>

export interface RatiosResponse {
  ratios: Record<string, RatioCategory>
  years: number[]
}

// ── Consolidation (Phase 3) ───────────────────────────────

/** line_item → { str(year) → str(value) } — string keys from backend JSON */
export type ConsolidatedStatementData = Record<string, Record<string, string>>

export interface ContributionEntry {
  entity_id: string
  entity_name: string
  ownership_pct: number
  consolidation_method: string
  revenue: Record<string, string>
  ebitda: Record<string, string>
  net_income: Record<string, string>
}

export interface ConsolidationMetadata {
  entity_count: number
  entities_with_data: number
  has_minority_interest: boolean
  has_eliminations: boolean
}

export interface ConsolidatedResponse {
  PNL: ConsolidatedStatementData
  BS: ConsolidatedStatementData
  CF: ConsolidatedStatementData
  contribution: ContributionEntry[]
  metadata: ConsolidationMetadata
}

export interface IntercompanyElimination {
  id: string
  from_entity_id: string
  from_entity_name: string | null
  to_entity_id: string
  to_entity_name: string | null
  transaction_type: 'revenue_cost' | 'management_fee' | 'loan' | 'dividend' | 'asset_transfer'
  description: string
  amount_by_year: Record<string, number>
  created_at: string
  updated_at: string
}

export interface EliminationCreate {
  from_entity_id: string
  to_entity_id: string
  transaction_type: IntercompanyElimination['transaction_type']
  description: string
  amount_by_year: Record<string, number>
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

// ── AI Settings ──────────────────────────────────────────

export type AIProvider = 'google' | 'anthropic' | 'openai'

export interface AISettingsUpdate {
  provider: AIProvider
  api_key: string
  cheap_model: string
  smart_model: string
}

export interface AISettingsOut {
  provider: string
  has_key: boolean
  key_last4: string
  cheap_model: string
  smart_model: string
  created_at: string
  updated_at: string
}

export interface AISettingsTestResult {
  success: boolean
  model: string
  message: string
  latency_ms: number | null
}

// ── AI Ingestion ─────────────────────────────────────────

export interface AIValidationMessage {
  tab: string
  line_item: string
  year: number
  message: string
}

export interface AIIngestionResponse {
  parsed: {
    PNL: Record<string, Record<string, number>>
    BS: Record<string, Record<string, number>>
    CF: Record<string, Record<string, number>>
  }
  mappings: Array<{
    sheet_name: string
    row_index: number
    original_name: string
    mapped_to: string
    confidence: number
  }>
  years: number[]
  validation_errors: AIValidationMessage[]
  ai_stats: {
    phase2_used: boolean
    reasons: string[]
    stats: Record<string, any>
  }
}

export interface UploadedDocument {
  id: string
  filename: string
  size: number
  status: 'pending' | 'validated' | 'rejected'
  is_ignored: boolean
  has_analysis: boolean
  missing_inputs: string[] | null
  entity_id: string | null
  ai_analysis: AIIngestionResponse | null
}
