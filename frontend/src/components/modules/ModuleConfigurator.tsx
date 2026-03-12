/**
 * Tree-based module configurator.
 * Each line item: pick a method → sub-fields appear.
 */
import { useState } from 'react'

interface Param {
  param_key: string
  year: number | null
  value: string
}

interface AssumptionItem {
  line_item: string
  projection_method: string
  params: Param[]
}

interface Props {
  module: string
  initialData: AssumptionItem[]
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

const METHOD_PARAMS: Record<string, Array<{ key: string; label: string; type?: string }>> = {
  growth_flat: [{ key: 'growth_rate', label: 'Annual Growth Rate (%)', type: 'number' }],
  growth_variable: [{ key: 'growth_rate', label: 'Growth Rate (%) — same for all years', type: 'number' }],
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
  variable_rate: [{ key: 'rate', label: 'Tax Rate (%) — same for all years', type: 'number' }],
  payout_ratio: [{ key: 'payout_ratio', label: 'Payout Ratio (% of Net Income)', type: 'number' }],
  yield_on_cash: [{ key: 'yield_pct', label: 'Yield on Cash (%)', type: 'number' }],
  flat_repayment: [{ key: 'repayment', label: 'Annual Repayment', type: 'number' }],
  straight_line: [{ key: 'useful_life_years', label: 'Useful Life (years)', type: 'number' }],
  headcount: [
    { key: 'headcount', label: 'Headcount', type: 'number' },
    { key: 'avg_cost', label: 'Avg. Cost per Head', type: 'number' },
  ],
}

const MODULE_METHODS: Record<string, string[]> = {
  revenue: ['growth_flat', 'growth_variable', 'fixed'],
  cogs: ['pct_revenue', 'gross_margin_pct', 'fixed'],
  opex: ['pct_revenue', 'pct_cogs', 'growth_flat', 'fixed', 'flat', 'headcount'],
  da: ['pct_gross_ppe', 'pct_gross', 'pct_net_ppe', 'fixed', 'straight_line'],
  working_capital: ['dio', 'dso', 'dpo', 'pct_revenue', 'pct_cogs', 'fixed', 'flat'],
  capex: ['pct_revenue', 'pct_net_ppe', 'fixed'],
  debt: ['flat_repayment', 'fixed'],
  tax: ['single_rate', 'variable_rate'],
  dividends: ['zero', 'payout_ratio', 'fixed'],
  interest_income: ['zero', 'yield_on_cash', 'fixed'],
  non_operating: ['flat', 'fixed', 'growth_flat', 'zero'],
}

const METHOD_LABELS: Record<string, string> = {
  growth_flat: 'Historical + Flat Growth Rate',
  growth_variable: 'Historical + Variable Growth Rate',
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
}

export default function ModuleConfigurator({ module, initialData, onSave, isSaving }: Props) {
  const defaults = MODULE_DEFAULTS[module] || []
  const [items, setItems] = useState<AssumptionItem[]>(
    initialData.length > 0 ? initialData : defaults
  )

  const methods = MODULE_METHODS[module] || ['growth_flat', 'fixed', 'flat']

  const updateItem = (idx: number, changes: Partial<AssumptionItem>) => {
    setItems(prev => prev.map((item, i) => {
      if (i !== idx) return item
      const updated = { ...item, ...changes }
      // Reset params when method changes
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

  return (
    <div className="space-y-4">
      {items.map((item, idx) => {
        const paramDefs = METHOD_PARAMS[item.projection_method] || []
        return (
          <div key={idx} className="card">
            <div className="flex items-start gap-4">
              <div className="flex-1 space-y-3">
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

                {paramDefs.length > 0 && (
                  <div className="grid grid-cols-2 gap-3 bg-gray-50 rounded-lg p-3">
                    {paramDefs.map(pd => {
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
