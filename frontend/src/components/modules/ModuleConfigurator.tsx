/**
 * Tree-based module configurator.
 * Each line item: pick a method → sub-fields appear.
 * Shows historical context (last N years) inline.
 * Includes a notes/source field per item.
 */
import { useState, useEffect } from 'react'
import { useFormatNumber } from '../../utils/formatters'

interface Param {
  param_key: string
  year: number | null
  value: string
}

interface AssumptionItem {
  line_item: string
  projection_method: string
  params: Param[]
  notes?: string
}

interface Props {
  module: string
  initialData: AssumptionItem[]
  projectionYears?: number[]
  historicalData?: { PNL?: Record<string, Record<string, string>>; BS?: Record<string, Record<string, string>>; CF?: Record<string, Record<string, string>> }
  onSave: (data: AssumptionItem[]) => void
  isSaving: boolean
}

const MODULE_DEFAULTS: Record<string, AssumptionItem[]> = {
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

const METHOD_PARAMS: Record<string, Array<{ key: string; label: string; type?: string; perYear?: boolean; optional?: boolean }>> = {
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

const MODULE_METHODS: Record<string, string[]> = {
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

const METHOD_LABELS: Record<string, string> = {
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

// Map module → statement for historical lookup
const MODULE_STATEMENT: Record<string, 'PNL' | 'BS' | 'CF'> = {
  revenue: 'PNL', cogs: 'PNL', opex: 'PNL', da: 'PNL',
  working_capital: 'BS', capex: 'BS', debt: 'BS',
  tax: 'PNL', dividends: 'PNL', interest_income: 'PNL', non_operating: 'PNL',
}

// LINE_ITEM_ALIASES: maps configurator line_item names to historical data keys
const LINE_ITEM_HIST_KEY: Record<string, string> = {
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

/** Show last 3 historical years for a given line item */
function HistoricalContext({
  lineItem,
  statement,
  historicalData,
  fmt,
}: {
  lineItem: string
  statement: 'PNL' | 'BS' | 'CF'
  historicalData?: Props['historicalData']
  fmt: (v: any) => string
}) {
  if (!historicalData) return null
  const stmtData = historicalData[statement] || {}
  const histKey = LINE_ITEM_HIST_KEY[lineItem] || lineItem
  const yearVals = stmtData[histKey] || {}
  const years = Object.keys(yearVals).map(Number).sort().slice(-3) // last 3 years
  if (years.length === 0) return null

  return (
    <div className="flex items-center gap-3 flex-wrap mt-1 mb-2 px-2 py-1.5 bg-blue-50 rounded text-xs text-blue-700 border border-blue-100">
      <span className="font-medium text-blue-600">📊 Historical:</span>
      {years.map(y => (
        <span key={y} className="tabular-nums">
          <span className="text-blue-400">{y}: </span>
          <span className="font-medium">{fmt(yearVals[y.toString()])}</span>
        </span>
      ))}
      {(METHOD_LABELS['growth_flat'] || true) && (
        <span className="text-blue-400 italic ml-1">· Base = last year ({years[years.length - 1]})</span>
      )}
    </div>
  )
}

/** Custom PxQ sub-form */
function PxQForm({ item, itemIdx, projectionYears, updatePxQ }: {
  item: AssumptionItem & { price?: any; quantity?: any }
  itemIdx: number
  projectionYears: number[]
  updatePxQ: (idx: number, field: 'price' | 'quantity', sub: string, val: any) => void
}) {
  const price = (item as any).price || { method: 'growth_flat', growth_rate: 0 }
  const quantity = (item as any).quantity || { method: 'growth_flat', growth_rate: 0 }

  return (
    <div className="grid grid-cols-2 gap-4 bg-gray-50 rounded-lg p-3 mt-2">
      {/* Price sub-form */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-gray-600">Price</p>
        <div>
          <label className="label text-xs">Method</label>
          <select className="input text-sm" value={price.method || 'growth_flat'}
            onChange={e => updatePxQ(itemIdx, 'price', 'method', e.target.value)}>
            <option value="growth_flat">Flat Growth Rate</option>
            <option value="fixed">Fixed per Year</option>
          </select>
        </div>
        {price.method !== 'fixed' ? (
          <div>
            <label className="label text-xs">Annual Growth (%)</label>
            <input type="number" step="0.1" className="input text-sm"
              value={price.growth_rate ?? ''}
              onChange={e => updatePxQ(itemIdx, 'price', 'growth_rate', e.target.value)}
              placeholder="e.g. 3" />
          </div>
        ) : (
          <div className="space-y-1">
            <label className="label text-xs">Value per Year</label>
            {projectionYears.map(y => (
              <div key={y} className="flex gap-2 items-center">
                <span className="text-xs text-gray-500 w-10">{y}</span>
                <input type="number" step="0.01" className="input text-sm flex-1"
                  value={price.fixed_values?.[y] ?? ''}
                  onChange={e => updatePxQ(itemIdx, 'price', `fixed_${y}`, e.target.value)}
                  placeholder="Price" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quantity sub-form */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-gray-600">Quantity</p>
        <div>
          <label className="label text-xs">Method</label>
          <select className="input text-sm" value={quantity.method || 'growth_flat'}
            onChange={e => updatePxQ(itemIdx, 'quantity', 'method', e.target.value)}>
            <option value="growth_flat">Flat Growth Rate</option>
            <option value="fixed">Fixed per Year</option>
          </select>
        </div>
        {quantity.method !== 'fixed' ? (
          <div>
            <label className="label text-xs">Annual Growth (%)</label>
            <input type="number" step="0.1" className="input text-sm"
              value={quantity.growth_rate ?? ''}
              onChange={e => updatePxQ(itemIdx, 'quantity', 'growth_rate', e.target.value)}
              placeholder="e.g. 5" />
          </div>
        ) : (
          <div className="space-y-1">
            <label className="label text-xs">Value per Year</label>
            {projectionYears.map(y => (
              <div key={y} className="flex gap-2 items-center">
                <span className="text-xs text-gray-500 w-10">{y}</span>
                <input type="number" step="0.01" className="input text-sm flex-1"
                  value={quantity.fixed_values?.[y] ?? ''}
                  onChange={e => updatePxQ(itemIdx, 'quantity', `fixed_${y}`, e.target.value)}
                  placeholder="Qty" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ModuleConfigurator({ module, initialData, projectionYears = [], historicalData, onSave, isSaving }: Props) {
  const defaults = MODULE_DEFAULTS[module] || []
  const [items, setItems] = useState<AssumptionItem[]>(
    initialData.length > 0 ? initialData : defaults
  )
  const fmt = useFormatNumber()

  useEffect(() => {
    setItems(initialData.length > 0 ? initialData : MODULE_DEFAULTS[module] || [])
  }, [module, initialData])

  const methods = MODULE_METHODS[module] || ['growth_flat', 'fixed', 'flat']
  const histStatement = MODULE_STATEMENT[module] || 'PNL'

  const updateItem = (idx: number, changes: Partial<AssumptionItem>) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const updated = { ...item, ...changes }
      if (changes.projection_method && changes.projection_method !== item.projection_method) {
        const paramDefs = METHOD_PARAMS[changes.projection_method] || []
        updated.params = paramDefs.map(p => ({ param_key: p.key, year: null, value: '' }))
      }
      return updated
    }))
  }

  const updateParam = (itemIdx: number, paramKey: string, value: string) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== itemIdx) return item
      const existingParam = item.params.find(p => p.param_key === paramKey && p.year === null)
      if (existingParam) {
        return { ...item, params: item.params.map(p => p.param_key === paramKey && p.year === null ? { ...p, value } : p) }
      }
      return { ...item, params: [...item.params, { param_key: paramKey, year: null, value }] }
    }))
  }

  const updatePerYearParam = (itemIdx: number, paramKey: string, year: number, value: string) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== itemIdx) return item
      const existingParam = item.params.find(p => p.param_key === paramKey && p.year === year)
      if (existingParam) {
        return { ...item, params: item.params.map(p => p.param_key === paramKey && p.year === year ? { ...p, value } : p) }
      }
      return { ...item, params: [...item.params, { param_key: paramKey, year, value }] }
    }))
  }

  const updatePxQ = (itemIdx: number, field: 'price' | 'quantity', subKey: string, val: any) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== itemIdx) return item
      const current = (item as any)[field] || {}
      if (subKey === 'method') {
        return { ...item, [field]: { ...current, method: val } }
      }
      if (subKey.startsWith('fixed_')) {
        const y = subKey.replace('fixed_', '')
        return { ...item, [field]: { ...current, fixed_values: { ...(current.fixed_values || {}), [y]: val } } }
      }
      return { ...item, [field]: { ...current, [subKey]: val } }
    }))
  }

  const updateNotes = (idx: number, notes: string) => {
    setItems(prev => prev.map((item, i) => i !== idx ? item : { ...item, notes }))
  }

  const addItem = () => {
    setItems(prev => [...prev, {
      line_item: `Item ${prev.length + 1}`,
      projection_method: methods[0],
      params: (METHOD_PARAMS[methods[0]] || []).map(p => ({ param_key: p.key, year: null, value: '' })),
    }])
  }

  const removeItem = (idx: number) => {
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  const showGrowthBaseNote = (method: string) =>
    method === 'growth_flat' || method === 'growth_variable'

  return (
    <div className="space-y-4">
      {items.map((item, idx) => {
        const paramDefs = METHOD_PARAMS[item.projection_method] || []
        const isPxQ = item.projection_method === 'price_quantity'
        return (
          <div key={idx} className="card">
            <div className="flex items-start gap-4">
              <div className="flex-1 space-y-3">
                {/* Line item name + method selector */}
                <div className="flex gap-3 items-center">
                  <div className="flex-1">
                    <label className="label">Line Item</label>
                    <input
                      className="input"
                      value={item.line_item}
                      onChange={e => updateItem(idx, { line_item: e.target.value })}
                    />
                  </div>
                  <div className="flex-1">
                    <label className="label">Projection Method</label>
                    <select
                      className="input"
                      value={item.projection_method}
                      onChange={e => updateItem(idx, { projection_method: e.target.value })}
                    >
                      {methods.map(m => (
                        <option key={m} value={m}>{METHOD_LABELS[m] || m}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Historical context */}
                <HistoricalContext
                  lineItem={item.line_item}
                  statement={histStatement}
                  historicalData={historicalData}
                  fmt={fmt}
                />

                {/* Base note for growth methods */}
                {showGrowthBaseNote(item.projection_method) && !historicalData && (
                  <p className="text-xs text-gray-400 italic bg-gray-50 rounded px-2 py-1">
                    ℹ️ Base = last uploaded historical year for "{item.line_item}". Falls back to total Revenue if not found.
                  </p>
                )}

                {/* PxQ custom form */}
                {isPxQ && (
                  <PxQForm
                    item={item as any}
                    itemIdx={idx}
                    projectionYears={projectionYears}
                    updatePxQ={updatePxQ}
                  />
                )}

                {/* Standard param fields */}
                {!isPxQ && paramDefs.length > 0 && (
                  <div className="grid grid-cols-2 gap-3 bg-gray-50 rounded-lg p-3">
                    {paramDefs.map(pd => {
                      if (pd.optional && pd.key === 'base_value') {
                        // Show base_value only if user explicitly expanded
                        const param = item.params.find(p => p.param_key === pd.key && p.year === null)
                        return (
                          <div key={pd.key}>
                            <label className="label text-xs text-gray-400">{pd.label}</label>
                            <input
                              type={pd.type || 'text'}
                              className="input text-sm"
                              value={param?.value || ''}
                              onChange={e => updateParam(idx, pd.key, e.target.value)}
                              placeholder="Leave blank to use historical"
                            />
                          </div>
                        )
                      }
                      if (pd.perYear && projectionYears.length > 0) {
                        return (
                          <div key={pd.key} className="col-span-2 space-y-2">
                            <label className="label text-xs">{pd.label}</label>
                            <div className="grid grid-cols-5 gap-2">
                              {projectionYears.map(year => {
                                const param = item.params.find(p => p.param_key === pd.key && p.year === year)
                                return (
                                  <div key={year}>
                                    <label className="text-[10px] text-gray-500 mb-1 block">{year}</label>
                                    <input
                                      type={pd.type || 'text'}
                                      className="input text-sm p-1.5"
                                      value={param?.value || ''}
                                      onChange={e => updatePerYearParam(idx, pd.key, year, e.target.value)}
                                      placeholder="---"
                                    />
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )
                      } else {
                        const param = item.params.find(p => p.param_key === pd.key && p.year === null)
                        return (
                          <div key={pd.key}>
                            <label className="label text-xs">{pd.label}</label>
                            <input
                              type={pd.type || 'text'}
                              className="input text-sm"
                              value={param?.value || ''}
                              onChange={e => updateParam(idx, pd.key, e.target.value)}
                              placeholder="Enter value"
                            />
                          </div>
                        )
                      }
                    })}
                  </div>
                )}

                {(item.projection_method === 'flat' || item.projection_method === 'zero') && (
                  <p className="text-sm text-gray-400 italic">
                    {item.projection_method === 'flat'
                      ? 'Carries forward the last historical value unchanged.'
                      : 'Set to zero for all projection years.'}
                  </p>
                )}

                {/* Notes / Source field */}
                <div>
                  <label className="label text-xs text-gray-400">📝 Notes / Source</label>
                  <input
                    type="text"
                    className="input text-sm text-gray-500 italic"
                    value={item.notes || ''}
                    onChange={e => updateNotes(idx, e.target.value)}
                    placeholder="e.g. Management guidance Q4 2024; IMF WEO forecast"
                  />
                </div>
              </div>

              {['revenue', 'opex'].includes(module) && (
                <button
                  onClick={() => removeItem(idx)}
                  className="text-red-400 hover:text-red-600 mt-6 text-sm"
                >
                  ✕
                </button>
              )}
            </div>
          </div>
        )
      })}

      <div className="flex gap-3">
        {['revenue', 'opex'].includes(module) && (
          <button onClick={addItem} className="btn-secondary text-sm">
            + Add Line Item
          </button>
        )}
        <button
          onClick={() => onSave(items)}
          disabled={isSaving}
          className="btn-primary text-sm"
        >
          {isSaving ? 'Saving...' : 'Save Assumptions'}
        </button>
      </div>
    </div>
  )
}
