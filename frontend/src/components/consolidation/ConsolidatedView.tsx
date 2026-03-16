/**
 * ConsolidatedView — Phase 3
 *
 * Shows group-level consolidated financials derived from all active entities
 * in the project. Tabs:
 *   P&L | Balance Sheet | Cash Flow | Contribution Analysis | Eliminations
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { consolidatedApi } from '../../services/api'

interface Props {
  projectId: string
  entities: Array<{ id: string; name: string; ownership_pct: number; consolidation_method: string }>
}

type Tab = 'PNL' | 'BS' | 'CF' | 'contribution' | 'eliminations'

// ── Small helper components ────────────────────────────────────────────────

function StatementTable({ data }: { data: Record<string, Record<string, string>> }) {
  if (!Object.keys(data).length)
    return <p className="text-sm text-gray-400 py-4 text-center">No data available</p>

  const years = Array.from(
    new Set(Object.values(data).flatMap(v => Object.keys(v)))
  ).sort()

  const fmt = (v: string) => {
    const n = parseFloat(v)
    if (isNaN(n)) return v
    return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50">
            <th className="text-left px-3 py-2 font-semibold text-gray-700 w-64">Line Item</th>
            {years.map(y => (
              <th key={y} className="text-right px-3 py-2 font-semibold text-gray-700">{y}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(data).map(([item, yearVals]) => {
            const isSubtotal = ['Gross Profit', 'EBIT', 'EBT', 'Net Income',
              'Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow',
              'Net Change in Cash', 'Net PP&E', 'Net Intangibles',
              'Minority Interest', 'Minority Interest (Equity)',
              'Share of Associates (Equity Method)'].includes(item)
            return (
              <tr key={item} className={`border-t border-gray-100 ${isSubtotal ? 'bg-blue-50 font-medium' : 'hover:bg-gray-50'}`}>
                <td className="px-3 py-1.5 text-gray-700">{item}</td>
                {years.map(y => {
                  const v = yearVals[y]
                  const num = v ? parseFloat(v) : null
                  return (
                    <td key={y} className={`px-3 py-1.5 text-right tabular-nums ${num !== null && num < 0 ? 'text-red-600' : 'text-gray-900'}`}>
                      {v ? fmt(v) : '—'}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ContributionTable({ contribution }: { contribution: Array<Record<string, any>> }) {
  if (!contribution.length)
    return <p className="text-sm text-gray-400 py-4 text-center">No contribution data available</p>

  const years = Array.from(
    new Set(contribution.flatMap(c => Object.keys(c.revenue || {})))
  ).sort()

  const fmt = (v: string | undefined) => {
    if (!v) return '—'
    const n = parseFloat(v)
    return isNaN(n) ? v : n.toLocaleString('en-US', { maximumFractionDigits: 0 })
  }

  // Compute group totals for % calculation
  const totals: Record<string, number> = {}
  years.forEach(y => {
    totals[y] = contribution.reduce((s, c) => s + (parseFloat(c.revenue?.[y] ?? '0') || 0), 0)
  })

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50">
            <th className="text-left px-3 py-2 font-semibold text-gray-700">Entity</th>
            <th className="text-center px-3 py-2 font-semibold text-gray-700">Method</th>
            <th className="text-center px-3 py-2 font-semibold text-gray-700">Own %</th>
            {years.map(y => (
              <th key={y} className="text-right px-3 py-2 font-semibold text-gray-700">
                Revenue {y}
              </th>
            ))}
            {years.length > 0 && (
              <th className="text-right px-3 py-2 font-semibold text-gray-700">
                % of Group ({years[years.length - 1]})
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {contribution.map(c => {
            const lastYear = years[years.length - 1]
            const rev = parseFloat(c.revenue?.[lastYear] ?? '0') || 0
            const total = totals[lastYear] || 1
            const pct = ((rev / total) * 100).toFixed(1)
            return (
              <tr key={c.entity_id} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="px-3 py-1.5 font-medium text-gray-800">{c.entity_name}</td>
                <td className="px-3 py-1.5 text-center">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    c.consolidation_method === 'full' ? 'bg-blue-100 text-blue-700'
                    : c.consolidation_method === 'proportional' ? 'bg-yellow-100 text-yellow-700'
                    : c.consolidation_method === 'equity_method' ? 'bg-purple-100 text-purple-700'
                    : 'bg-gray-100 text-gray-600'
                  }`}>
                    {c.consolidation_method}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-center text-gray-600">{c.ownership_pct}%</td>
                {years.map(y => (
                  <td key={y} className="px-3 py-1.5 text-right tabular-nums text-gray-900">
                    {fmt(c.revenue?.[y])}
                  </td>
                ))}
                {years.length > 0 && (
                  <td className="px-3 py-1.5 text-right tabular-nums text-gray-600">{pct}%</td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function EliminationsEditor({
  projectId,
  entities,
}: {
  projectId: string
  entities: Props['entities']
}) {
  const qc = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({
    from_entity_id: '',
    to_entity_id: '',
    transaction_type: 'revenue_cost',
    description: '',
    amount_by_year: {} as Record<string, string>,
    newYear: '',
    newAmount: '',
  })

  const { data: eliminations = [] } = useQuery({
    queryKey: ['eliminations', projectId],
    queryFn: () => consolidatedApi.listEliminations(projectId).then(r => r.data),
  })

  const createMut = useMutation({
    mutationFn: (payload: any) => consolidatedApi.createElimination(projectId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['eliminations', projectId] })
      qc.invalidateQueries({ queryKey: ['consolidated', projectId] })
      toast.success('Elimination saved')
      setAdding(false)
      setForm(f => ({ ...f, from_entity_id: '', to_entity_id: '', description: '', amount_by_year: {}, newYear: '', newAmount: '' }))
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Save failed'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => consolidatedApi.deleteElimination(projectId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['eliminations', projectId] })
      qc.invalidateQueries({ queryKey: ['consolidated', projectId] })
      toast.success('Deleted')
    },
  })

  const addAmountRow = () => {
    if (!form.newYear || !form.newAmount) return
    setForm(f => ({
      ...f,
      amount_by_year: { ...f.amount_by_year, [f.newYear]: f.newAmount },
      newYear: '',
      newAmount: '',
    }))
  }

  const handleCreate = () => {
    const amounts = Object.fromEntries(
      Object.entries(form.amount_by_year).map(([y, v]) => [y, parseFloat(v)])
    )
    createMut.mutate({
      from_entity_id: form.from_entity_id,
      to_entity_id: form.to_entity_id,
      transaction_type: form.transaction_type,
      description: form.description,
      amount_by_year: amounts,
    })
  }

  const TX_TYPES = ['revenue_cost', 'management_fee', 'loan', 'dividend', 'asset_transfer']

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Define intercompany transactions to eliminate from consolidated statements.
        </p>
        {!adding && (
          <button className="btn-primary" onClick={() => setAdding(true)}>
            + Add Elimination
          </button>
        )}
      </div>

      {/* Add form */}
      {adding && (
        <div className="card border-blue-200 bg-blue-50 space-y-3">
          <h4 className="font-medium text-gray-900">New Intercompany Elimination</h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">From entity (seller / lender)</label>
              <select className="input" value={form.from_entity_id}
                onChange={e => setForm(f => ({ ...f, from_entity_id: e.target.value }))}>
                <option value="">Select…</option>
                {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">To entity (buyer / borrower)</label>
              <select className="input" value={form.to_entity_id}
                onChange={e => setForm(f => ({ ...f, to_entity_id: e.target.value }))}>
                <option value="">Select…</option>
                {entities.filter(e => e.id !== form.from_entity_id).map(e =>
                  <option key={e.id} value={e.id}>{e.name}</option>
                )}
              </select>
            </div>
            <div>
              <label className="label">Type</label>
              <select className="input" value={form.transaction_type}
                onChange={e => setForm(f => ({ ...f, transaction_type: e.target.value }))}>
                {TX_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Description</label>
              <input className="input" placeholder="e.g. Management fee HoldCo → Plants"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
          </div>

          <div>
            <label className="label">Amounts by year</label>
            <div className="flex gap-2 mb-2">
              <input className="input w-28" placeholder="Year" value={form.newYear}
                onChange={e => setForm(f => ({ ...f, newYear: e.target.value }))} />
              <input className="input w-40" placeholder="Amount" value={form.newAmount}
                onChange={e => setForm(f => ({ ...f, newAmount: e.target.value }))} />
              <button className="btn-secondary" onClick={addAmountRow}>Add</button>
            </div>
            {Object.keys(form.amount_by_year).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(form.amount_by_year).sort().map(([y, v]) => (
                  <span key={y} className="bg-white border border-gray-300 rounded px-2 py-1 text-xs">
                    {y}: {parseFloat(v).toLocaleString()}
                    <button className="ml-1 text-gray-400 hover:text-red-500"
                      onClick={() => setForm(f => {
                        const a = { ...f.amount_by_year }
                        delete a[y]
                        return { ...f, amount_by_year: a }
                      })}>✕</button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <button className="btn-secondary" onClick={() => setAdding(false)}>Cancel</button>
            <button className="btn-primary" onClick={handleCreate} disabled={createMut.isPending}>
              {createMut.isPending ? 'Saving…' : 'Save Elimination'}
            </button>
          </div>
        </div>
      )}

      {/* List */}
      {eliminations.length === 0 && !adding ? (
        <p className="text-sm text-gray-400 text-center py-6">
          No intercompany eliminations defined yet.
        </p>
      ) : (
        <div className="space-y-2">
          {(eliminations as any[]).map((el: any) => (
            <div key={el.id} className="card flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-gray-900 text-sm">
                  {el.from_entity_name} → {el.to_entity_name}
                  <span className="ml-2 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                    {el.transaction_type}
                  </span>
                </p>
                <p className="text-xs text-gray-500 mt-0.5">{el.description}</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {Object.entries(el.amount_by_year).sort().map(([y, v]) => (
                    <span key={y} className="text-xs text-gray-600">
                      {y}: {(v as number).toLocaleString()}
                    </span>
                  ))}
                </div>
              </div>
              <button
                className="text-gray-400 hover:text-red-500 transition-colors text-sm shrink-0"
                onClick={() => { if (window.confirm('Delete this elimination?')) deleteMut.mutate(el.id) }}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

export default function ConsolidatedView({ projectId, entities }: Props) {
  const [tab, setTab] = useState<Tab>('PNL')

  const { data, isLoading, error } = useQuery({
    queryKey: ['consolidated', projectId],
    queryFn: () => consolidatedApi.getProjections(projectId).then(r => r.data),
  })

  const TABS: Array<{ key: Tab; label: string }> = [
    { key: 'PNL', label: 'P&L' },
    { key: 'BS', label: 'Balance Sheet' },
    { key: 'CF', label: 'Cash Flow' },
    { key: 'contribution', label: 'Contribution' },
    { key: 'eliminations', label: 'Eliminations' },
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Consolidated View</h2>
          {data?.metadata && (
            <p className="text-sm text-gray-500 mt-0.5">
              {data.metadata.entities_with_data} of {data.metadata.entity_count} entities consolidated
              {data.metadata.has_minority_interest && ' · Minority interest included'}
              {data.metadata.has_eliminations && ' · Eliminations applied'}
            </p>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-1">
          {TABS.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t.key
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Content */}
      <div className="card">
        {isLoading && (
          <p className="text-gray-400 text-sm py-8 text-center">Loading consolidated data…</p>
        )}
        {error && (
          <p className="text-red-500 text-sm py-4">
            Failed to load consolidated data. Make sure entities have historical or projected data.
          </p>
        )}
        {data && !isLoading && (
          <>
            {tab === 'PNL' && <StatementTable data={data.PNL} />}
            {tab === 'BS' && <StatementTable data={data.BS} />}
            {tab === 'CF' && <StatementTable data={data.CF} />}
            {tab === 'contribution' && <ContributionTable contribution={data.contribution} />}
            {tab === 'eliminations' && (
              <EliminationsEditor projectId={projectId} entities={entities} />
            )}
          </>
        )}
        {!data && !isLoading && !error && tab === 'eliminations' && (
          <EliminationsEditor projectId={projectId} entities={entities} />
        )}
      </div>
    </div>
  )
}
