/**
 * Static configuration maps for ModuleConfigurator.
 *
 * Kept separate from the components so tweaking methods/labels doesn't
 * re-render anything that doesn't use them.
 */

export interface Param {
  param_key: string
  year: number | null
  value: string
}

export interface AssumptionItem {
  line_item: string
  projection_method: string
  params: Param[]
  notes?: string
}

export interface ParamDef {
  key: string
  label: string
  type?: string
  perYear?: boolean
  optional?: boolean
}

export const MODULE_DEFAULTS: Record<string, AssumptionItem[]> = {
  revenue: [{ line_item: 'Revenue Stream 1', projection_method: 'growth_flat', params: [{ param_key: 'growth_rate', year: null, value: '5' }] }],
  cogs: [{ line_item: 'Cost of Goods Sold', projection_method: 'pct_revenue', params: [{ param_key: 'pct', year: null, value: '60' }] }],
  opex: [
    { line_item: 'SG&A', projection_method: 'pct_revenue', params: [{ param_key: 'pct', year: null, value: '15' }] },
    { line_item: 'R&D', projection_method: 'pct_revenue', params: [{ param_key: 'pct', year: null, value: '8' }] },
    { line_item: 'Other OpEx', projection_method: 'pct_revenue', params: [{ param_key: 'pct', year: null, value: '3' }] },
  ],
  da: [
    { line_item: 'Depreciation', projection_method: 'pct_gross_ppe', params: [{ param_key: 'pct', year: null, value: '10' }] },
    { line_item: 'Amortization of Intangibles', projection_method: 'pct_gross', params: [{ param_key: 'pct', year: null, value: '20' }] },
  ],
  working_capital: [
    { line_item: 'Inventories', projection_method: 'dio', params: [{ param_key: 'days', year: null, value: '45' }] },
    { line_item: 'Accounts Receivable', projection_method: 'dso', params: [{ param_key: 'days', year: null, value: '30' }] },
    { line_item: 'Prepaid Expenses & Other Current Assets', projection_method: 'pct_revenue', params: [{ param_key: 'pct', year: null, value: '2' }] },
    { line_item: 'Accounts Payable', projection_method: 'dpo', params: [{ param_key: 'days', year: null, value: '30' }] },
    { line_item: 'Accrued Liabilities', projection_method: 'pct_revenue', params: [{ param_key: 'pct', year: null, value: '5' }] },
    { line_item: 'Other Current Liabilities', projection_method: 'flat', params: [] },
  ],
  capex: [{ line_item: 'Total Capex', projection_method: 'pct_revenue', params: [{ param_key: 'pct', year: null, value: '3' }] }],
  debt: [{ line_item: 'Debt', projection_method: 'flat_repayment', params: [{ param_key: 'repayment', year: null, value: '0' }] }],
  tax: [{ line_item: 'Tax', projection_method: 'single_rate', params: [{ param_key: 'rate', year: null, value: '21' }] }],
  dividends: [{ line_item: 'Dividends', projection_method: 'zero', params: [] }],
  interest_income: [{ line_item: 'Interest Income', projection_method: 'zero', params: [] }],
  non_operating: [
    { line_item: 'Non-Operating Assets', projection_method: 'flat', params: [] },
    { line_item: 'Goodwill', projection_method: 'flat', params: [] },
    { line_item: 'Other Non-Operating Income / (Expense)', projection_method: 'zero', params: [] },
  ],
}

export const METHOD_PARAMS: Record<string, ParamDef[]> = {
  growth_flat: [
    { key: 'growth_rate', label: 'Annual Growth Rate (%)', type: 'number' },
    { key: 'base_value', label: 'Base Value Override (optional)', type: 'number', optional: true },
  ],
  growth_variable: [
    { key: 'growth_rate', label: 'Growth Rate (%)', type: 'number', perYear: true },
    { key: 'base_value', label: 'Base Value Override (optional)', type: 'number', optional: true },
  ],
  pct_revenue: [{ key: 'pct', label: '% of Revenue', type: 'number' }],
  pct_cogs: [{ key: 'pct', label: '% of COGS', type: 'number' }],
  pct_gross_ppe: [{ key: 'pct', label: '% of Gross PP&E', type: 'number' }],
  pct_gross: [{ key: 'pct', label: '% of Gross Intangibles', type: 'number' }],
  pct_net_ppe: [{ key: 'pct', label: '% of Net PP&E', type: 'number' }],
  gross_margin_pct: [{ key: 'gm_pct', label: 'Target Gross Margin (%)', type: 'number' }],
  fixed: [{ key: 'value', label: 'Fixed Value', type: 'number' }],
  flat: [],
  zero: [],
  dio: [{ key: 'days', label: 'Days Inventory Outstanding', type: 'number' }],
  dso: [{ key: 'days', label: 'Days Sales Outstanding', type: 'number' }],
  dpo: [{ key: 'days', label: 'Days Payable Outstanding', type: 'number' }],
  single_rate: [{ key: 'rate', label: 'Effective Tax Rate (%)', type: 'number' }],
  variable_rate: [{ key: 'rate', label: 'Tax Rate (%)', type: 'number', perYear: true }],
  payout_ratio: [{ key: 'payout_ratio', label: 'Payout Ratio (% of Net Income)', type: 'number' }],
  yield_on_cash: [{ key: 'yield_pct', label: 'Yield on Cash (%)', type: 'number' }],
  flat_repayment: [{ key: 'repayment', label: 'Annual Repayment', type: 'number' }],
  straight_line: [{ key: 'useful_life_years', label: 'Useful Life (years)', type: 'number' }],
  headcount: [
    { key: 'headcount', label: 'Headcount', type: 'number' },
    { key: 'avg_cost', label: 'Avg. Cost per Head', type: 'number' },
  ],
  price_quantity: [], // handled by custom render
  external_curve: [{ key: 'value', label: 'Index Value', type: 'number', perYear: true }],
  maintenance_growth: [
    { key: 'maintenance_pct', label: 'Maintenance Capex (% Revenue)', type: 'number' },
    { key: 'growth_value', label: 'Growth Capex (fixed amount)', type: 'number' },
  ],
}

export const MODULE_METHODS: Record<string, string[]> = {
  revenue: ['growth_flat', 'growth_variable', 'price_quantity', 'external_curve', 'fixed'],
  cogs: ['pct_revenue', 'gross_margin_pct', 'fixed', 'price_quantity'],
  opex: ['pct_revenue', 'pct_cogs', 'growth_flat', 'growth_variable', 'fixed', 'flat', 'headcount'],
  da: ['pct_gross_ppe', 'pct_gross', 'pct_net_ppe', 'fixed', 'straight_line'],
  working_capital: ['dio', 'dso', 'dpo', 'pct_revenue', 'pct_cogs', 'fixed', 'flat'],
  capex: ['pct_revenue', 'pct_net_ppe', 'fixed', 'maintenance_growth'],
  debt: ['flat_repayment', 'fixed'],
  tax: ['single_rate', 'variable_rate'],
  dividends: ['zero', 'payout_ratio', 'fixed'],
  interest_income: ['zero', 'yield_on_cash', 'fixed'],
  non_operating: ['flat', 'fixed', 'growth_flat', 'zero'],
}

export const METHOD_LABELS: Record<string, string> = {
  growth_flat: 'Historical + Flat Growth Rate',
  growth_variable: 'Historical + Variable Growth Rate (per year)',
  price_quantity: 'Price × Quantity (PxQ)',
  external_curve: 'External Index / Curve',
  pct_revenue: '% of Revenue',
  pct_cogs: '% of COGS',
  pct_gross_ppe: '% of Gross PP&E',
  pct_gross: '% of Gross Intangibles',
  pct_net_ppe: '% of Net PP&E',
  gross_margin_pct: 'Gross Margin %',
  fixed: 'Fixed Value',
  flat: 'Flat (hold last historical)',
  zero: 'Zero',
  dio: 'Days Inventory Outstanding (DIO)',
  dso: 'Days Sales Outstanding (DSO)',
  dpo: 'Days Payable Outstanding (DPO)',
  single_rate: 'Single Rate (all years)',
  variable_rate: 'Variable Rate (per year)',
  payout_ratio: 'Payout Ratio (% of Net Income)',
  yield_on_cash: 'Yield on Cash',
  flat_repayment: 'Flat Annual Repayment',
  straight_line: 'Straight-Line over Useful Life',
  headcount: 'Headcount × Avg. Cost',
  maintenance_growth: 'Maintenance % + Growth Capex',
}

export const MODULE_STATEMENT: Record<string, 'PNL' | 'BS' | 'CF'> = {
  revenue: 'PNL', cogs: 'PNL', opex: 'PNL', da: 'PNL',
  working_capital: 'BS', capex: 'BS', debt: 'BS',
  tax: 'PNL', dividends: 'PNL', interest_income: 'PNL', non_operating: 'PNL',
}

/** Maps configurator line_item names to their historical-data key. */
export const LINE_ITEM_HIST_KEY: Record<string, string> = {
  'Cost of Goods Sold': 'Cost of Goods Sold',
  'SG&A': 'SG&A',
  'R&D': 'R&D',
  'Other OpEx': 'Other OpEx',
  'Depreciation': 'D&A',
  'Amortization of Intangibles': 'Amortization of Intangibles',
  'Total Capex': 'Capex',
  'Interest Income': 'Interest Income',
  'Interest Expense': 'Interest Expense',
  'Tax': 'Tax',
}

export type HistoricalData = {
  PNL?: Record<string, Record<string, string>>
  BS?: Record<string, Record<string, string>>
  CF?: Record<string, Record<string, string>>
}
