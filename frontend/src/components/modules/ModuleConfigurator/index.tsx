/**
 * Tree-based module configurator.
 * Each line item: pick a method → sub-fields appear.
 * Shows historical context (last N years) inline + per-item notes/source.
 */
import { useEffect, useState } from 'react'

import { useFormatNumber } from '../../../utils/formatters'
import HistoricalContext from './HistoricalContext'
import ParamFields from './ParamFields'
import PxQForm from './PxQForm'
import {
  AssumptionItem,
  HistoricalData,
  METHOD_LABELS,
  METHOD_PARAMS,
  MODULE_DEFAULTS,
  MODULE_METHODS,
  MODULE_STATEMENT,
} from './constants'

interface Props {
  module: string
  initialData: AssumptionItem[]
  projectionYears?: number[]
  historicalData?: HistoricalData
  onSave: (data: AssumptionItem[]) => void
  isSaving: boolean
}

export default function ModuleConfigurator({
  module,
  initialData,
  projectionYears = [],
  historicalData,
  onSave,
  isSaving,
}: Props) {
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
    setItems(prev =>
      prev.map((item, i) => {
        if (i !== idx) return item
        const updated = { ...item, ...changes }
        if (changes.projection_method && changes.projection_method !== item.projection_method) {
          const paramDefs = METHOD_PARAMS[changes.projection_method] || []
          updated.params = paramDefs.map(p => ({ param_key: p.key, year: null, value: '' }))
        }
        return updated
      })
    )
  }

  const updateParam = (itemIdx: number, paramKey: string, value: string) => {
    setItems(prev =>
      prev.map((item, i) => {
        if (i !== itemIdx) return item
        const existing = item.params.find(p => p.param_key === paramKey && p.year === null)
        if (existing) {
          return {
            ...item,
            params: item.params.map(p =>
              p.param_key === paramKey && p.year === null ? { ...p, value } : p
            ),
          }
        }
        return { ...item, params: [...item.params, { param_key: paramKey, year: null, value }] }
      })
    )
  }

  const updatePerYearParam = (itemIdx: number, paramKey: string, year: number, value: string) => {
    setItems(prev =>
      prev.map((item, i) => {
        if (i !== itemIdx) return item
        const existing = item.params.find(p => p.param_key === paramKey && p.year === year)
        if (existing) {
          return {
            ...item,
            params: item.params.map(p =>
              p.param_key === paramKey && p.year === year ? { ...p, value } : p
            ),
          }
        }
        return { ...item, params: [...item.params, { param_key: paramKey, year, value }] }
      })
    )
  }

  const updatePxQ = (itemIdx: number, field: 'price' | 'quantity', subKey: string, val: any) => {
    setItems(prev =>
      prev.map((item, i) => {
        if (i !== itemIdx) return item
        const current = (item as any)[field] || {}
        if (subKey === 'method') {
          return { ...item, [field]: { ...current, method: val } }
        }
        if (subKey.startsWith('fixed_')) {
          const y = subKey.replace('fixed_', '')
          return {
            ...item,
            [field]: { ...current, fixed_values: { ...(current.fixed_values || {}), [y]: val } },
          }
        }
        return { ...item, [field]: { ...current, [subKey]: val } }
      })
    )
  }

  const updateNotes = (idx: number, notes: string) => {
    setItems(prev => prev.map((item, i) => (i !== idx ? item : { ...item, notes })))
  }

  const addItem = () => {
    setItems(prev => [
      ...prev,
      {
        line_item: `Item ${prev.length + 1}`,
        projection_method: methods[0],
        params: (METHOD_PARAMS[methods[0]] || []).map(p => ({
          param_key: p.key,
          year: null,
          value: '',
        })),
      },
    ])
  }

  const removeItem = (idx: number) => {
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  const isGrowthMethod = (method: string) => method === 'growth_flat' || method === 'growth_variable'

  return (
    <div className="space-y-4">
      {items.map((item, idx) => {
        const paramDefs = METHOD_PARAMS[item.projection_method] || []
        const isPxQ = item.projection_method === 'price_quantity'
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
                        <option key={m} value={m}>
                          {METHOD_LABELS[m] || m}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <HistoricalContext
                  lineItem={item.line_item}
                  statement={histStatement}
                  historicalData={historicalData}
                  fmt={fmt}
                />

                {isGrowthMethod(item.projection_method) && !historicalData && (
                  <p className="text-xs text-gray-400 italic bg-gray-50 rounded px-2 py-1">
                    ℹ️ Base = last uploaded historical year for "{item.line_item}". Falls back to total Revenue if not found.
                  </p>
                )}

                {isPxQ ? (
                  <PxQForm
                    item={item as any}
                    itemIdx={idx}
                    projectionYears={projectionYears}
                    updatePxQ={updatePxQ}
                  />
                ) : (
                  <ParamFields
                    item={item}
                    itemIdx={idx}
                    paramDefs={paramDefs}
                    projectionYears={projectionYears}
                    updateParam={updateParam}
                    updatePerYearParam={updatePerYearParam}
                  />
                )}

                {(item.projection_method === 'flat' || item.projection_method === 'zero') && (
                  <p className="text-sm text-gray-400 italic">
                    {item.projection_method === 'flat'
                      ? 'Carries forward the last historical value unchanged.'
                      : 'Set to zero for all projection years.'}
                  </p>
                )}

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
        <button onClick={() => onSave(items)} disabled={isSaving} className="btn-primary text-sm">
          {isSaving ? 'Saving...' : 'Save Assumptions'}
        </button>
      </div>
    </div>
  )
}
