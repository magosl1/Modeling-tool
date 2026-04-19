import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectionsApi, scenariosApi, projectsApi, assumptionsApi } from '../../services/api'
import type { ProjectionsResponse } from '../../types/api'
import { useFormatNumber } from '../../utils/formatters'
import RatiosView from './RatiosView'
import ScenarioManager from '../scenarios/ScenarioManager'
import ScenarioCompare from '../scenarios/ScenarioCompare'
import toast from 'react-hot-toast'

interface Props { projectId: string; allModulesComplete: boolean; project?: any }

const PNL_ITEMS = [
  'Revenue', 'Cost of Goods Sold', 'Gross Profit', 'SG&A', 'R&D', 'D&A',
  'Amortization of Intangibles', 'Other OpEx', 'EBIT', 'EBITDA', 'Interest Income',
  'Interest Expense', 'Other Non-Operating Income / (Expense)', 'EBT', 'Tax', 'Net Income',
]

const BS_ITEMS = [
  'PP&E Gross', 'Accumulated Depreciation', 'Net PP&E', 'Intangibles Gross',
  'Accumulated Amortization', 'Net Intangibles', 'Goodwill', 'Inventories',
  'Accounts Receivable', 'Prepaid Expenses & Other Current Assets', 'Accounts Payable',
  'Accrued Liabilities', 'Other Current Liabilities', 'Cash & Equivalents',
  'Non-Operating Assets', 'Short-Term Debt', 'Long-Term Debt', 'Share Capital',
  'Retained Earnings', 'Other Equity (AOCI, Treasury Stock, etc.)',
]

const CF_ITEMS = [
  'Net Income', 'D&A Add-back', 'Amortization of Intangibles Add-back',
  'Changes in Working Capital', 'Operating Cash Flow', 'Capex',
  'Acquisitions / Disposals', 'Investing Cash Flow', 'Debt Issuance / Repayment',
  'Dividends Paid', 'Share Issuance / Buyback', 'Financing Cash Flow', 'Net Change in Cash',
]

const SUBTOTALS = new Set([
  'Gross Profit', 'EBIT', 'EBITDA', 'EBT', 'Net Income',
  'Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow', 'Net Change in Cash',
])

// Lines that are costs — their projected values are stored positive but should display negative
const COST_LINES = new Set([
  'Cost of Goods Sold', 'SG&A', 'R&D', 'D&A', 'Amortization of Intangibles',
  'Other OpEx', 'Interest Expense', 'Tax',
])

// Format as (xxx) for negatives, professional finance style
function fmtVal(raw: string | number | undefined, fmt: (v: any) => string): { text: string; negative: boolean } {
  if (raw === undefined || raw === null || raw === '') return { text: '—', negative: false }
  const num = typeof raw === 'number' ? raw : parseFloat(String(raw))
  if (isNaN(num)) return { text: '—', negative: false }
  if (num < 0) {
    const pos = fmt(Math.abs(num))
    return { text: `(${pos})`, negative: true }
  }
  return { text: fmt(num), negative: false }
}

function growth(curr: string | undefined, prev: string | undefined): string {
  const nc = parseFloat(String(curr ?? '0'))
  const np = parseFloat(String(prev ?? '0'))
  if (!np || isNaN(nc) || isNaN(np)) return '—'
  const g = ((nc - np) / Math.abs(np)) * 100
  return (g >= 0 ? '+' : '') + g.toFixed(1) + '%'
}

function SubRow({ label, values, years, projectedYears }: {
  label: string
  values: Record<number, string>
  years: number[]
  projectedYears: Set<number>
}) {
  return (
    <tr className="border-b border-gray-100">
      <td className="py-1 pr-4 text-xs text-gray-400 pl-4 italic sticky left-0 z-10 bg-white shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] whitespace-nowrap">{label}</td>
      {years.map(y => (
        <td key={y} className={`py-1 px-3 text-right text-xs tabular-nums italic ${
          projectedYears.has(y) ? 'text-blue-400 bg-blue-50/30' : 'text-gray-400'
        }`}>
          {values[y] ?? '—'}
        </td>
      ))}
    </tr>
  )
}

function FinancialTable({ title, items, data, years, projectedYears, pnlData }: {
  title: string
  items: string[]
  data: Record<string, Record<string, string>>
  years: number[]
  projectedYears: Set<number>
  pnlData?: Record<string, Record<string, string>>
}) {
  const fmt = useFormatNumber()
  const isPNL = title === 'P&L'

  // Pre-compute Revenue growth and EBITDA margin
  const revenueGrowth: Record<number, string> = {}
  const ebitdaMargin: Record<number, string> = {}
  if (isPNL && pnlData) {
    years.forEach((y, idx) => {
      revenueGrowth[y] = idx === 0 ? '—' : growth(pnlData['Revenue']?.[y], pnlData['Revenue']?.[years[idx - 1]])
      const ebitda = parseFloat(String(pnlData['EBITDA']?.[y] ?? '0'))
      const rev = parseFloat(String(pnlData['Revenue']?.[y] ?? '0'))
      ebitdaMargin[y] = rev ? (ebitda / rev * 100).toFixed(1) + '%' : '—'
    })
  }

  return (
    <div className="mb-8">
      <h3 className="font-semibold text-gray-800 mb-3">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 pr-4 font-medium text-gray-600 w-64 sticky left-0 z-20 bg-white shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)]">Line Item</th>
              {years.map(y => (
                <th key={y} className={`text-right py-2 px-3 font-medium min-w-24 ${projectedYears.has(y) ? 'text-blue-600 bg-blue-50' : 'text-gray-600'}`}>
                  {y}{projectedYears.has(y) ? 'P' : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(item => {
              const isSubtotal = SUBTOTALS.has(item)
              const isCost = COST_LINES.has(item)
              return (
              <React.Fragment key={item}>
                  <tr
                    className={`border-b border-gray-100 ${isSubtotal ? 'font-semibold bg-gray-50' : ''}`}
                  >
                    <td className={`py-1.5 pr-4 text-gray-700 sticky left-0 z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] whitespace-nowrap ${isSubtotal ? 'bg-gray-50' : 'bg-white'}`}>{item}</td>
                    {years.map(y => {
                      const raw = data[item]?.[y]
                      // Cost lines: stored positive in engine, displayed negative
                      let displayRaw = raw
                      if (isCost && raw !== undefined && raw !== null && raw !== '') {
                        const n = parseFloat(String(raw))
                        if (!isNaN(n) && n > 0) displayRaw = String(-n)
                      }
                      const { text, negative } = fmtVal(displayRaw, fmt)
                      return (
                        <td key={y} className={`py-1.5 px-3 text-right tabular-nums ${
                          negative ? 'text-red-600' : projectedYears.has(y) ? 'text-blue-900' : 'text-gray-900'
                        } ${projectedYears.has(y) ? 'bg-blue-50/50' : ''}`}>
                          {text}
                        </td>
                      )
                    })}
                  </tr>
                  {isPNL && item === 'Revenue' && (
                    <SubRow label="↳ YoY Growth" values={revenueGrowth} years={years} projectedYears={projectedYears} />
                  )}
                  {isPNL && item === 'EBITDA' && (
                    <SubRow label="↳ EBITDA Margin" values={ebitdaMargin} years={years} projectedYears={projectedYears} />
                  )}
              </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function KeyMetricsStrip({ data, years, projectedYears, pnlData }: {
  data: Record<string, Record<string, string>>
  years: number[]
  projectedYears: Set<number>
  pnlData?: Record<string, Record<string, string>>
}) {
  const fmt = useFormatNumber()
  const metrics = years.map(y => {
    const stDebt = parseFloat(String(data['Short-Term Debt']?.[y] ?? '0'))
    const ltDebt = parseFloat(String(data['Long-Term Debt']?.[y] ?? '0'))
    const cash = parseFloat(String(data['Cash & Equivalents']?.[y] ?? '0'))
    const sc = parseFloat(String(data['Share Capital']?.[y] ?? '0'))
    const re = parseFloat(String(data['Retained Earnings']?.[y] ?? '0'))
    const oe = parseFloat(String(data['Other Equity (AOCI, Treasury Stock, etc.)']?.[y] ?? '0'))
    const netDebt = stDebt + ltDebt - cash
    const equity = sc + re + oe
    const ebitda = parseFloat(String(pnlData?.['EBITDA']?.[y] ?? '0'))
    return { y, netDebt, equity, ebitda }
  })

  const rows = [
    { label: 'Net Debt', values: metrics.map(m => ({ y: m.y, v: m.netDebt })), isRatio: false },
    { label: 'Net Debt / Equity', values: metrics.map(m => ({ y: m.y, v: m.equity ? m.netDebt / m.equity : NaN })), isRatio: true },
    { label: 'Net Debt / EBITDA', values: metrics.map(m => ({ y: m.y, v: m.ebitda ? m.netDebt / m.ebitda : NaN })), isRatio: true },
  ]

  return (
    <div className="mt-4 border-t border-gray-200 pt-4">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Key Metrics</p>
      <table className="w-full text-xs">
        <tbody>
          {rows.map(row => (
            <tr key={row.label} className="border-b border-gray-100">
              <td className="py-1 pr-4 font-medium text-gray-600 w-64 sticky left-0 z-10 bg-white shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] whitespace-nowrap">{row.label}</td>
              {row.values.map(({ y, v }) => {
                const isRatio = row.label.includes('/')
                const text = isNaN(v) ? '—' : isRatio ? v.toFixed(2) + 'x' : (v < 0 ? `(${fmt(Math.abs(v))})` : fmt(v))
                const neg = v < 0
                return (
                  <td key={y} className={`py-1 px-3 text-right tabular-nums min-w-24 ${neg ? 'text-red-600' : 'text-gray-700'} ${projectedYears.has(y) ? 'bg-blue-50/30' : ''}`}>
                    {text}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AssumptionsSummary({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const modules = ['revenue', 'cogs', 'opex', 'da', 'working_capital', 'capex', 'tax']
  const { data: assumptionsData } = useQuery({
    queryKey: ['assumptions-all', projectId],
    queryFn: async () => {
      const results: Record<string, any> = {}
      await Promise.all(modules.map(async m => {
        try {
          const r = await assumptionsApi.getModule(projectId, m)
          results[m] = r.data
        } catch { /* ok */ }
      }))
      return results
    },
    enabled: open,
  })

  const summaryRows: { label: string; value: string }[] = []
  if (assumptionsData) {
    const rev = assumptionsData['revenue']
    if (rev?.items?.[0]) summaryRows.push({ label: 'Revenue method', value: rev.items[0].projection_method ?? '—' })
    const cogs = assumptionsData['cogs']
    if (cogs?.items?.[0]?.params?.[0]) summaryRows.push({ label: 'COGS % revenue', value: cogs.items[0].params[0].value + '%' })
    const tax = assumptionsData['tax']
    if (tax?.items?.[0]?.params?.[0]) summaryRows.push({ label: 'Effective tax rate', value: tax.items[0].params[0].value + '%' })
    const capex = assumptionsData['capex']
    if (capex?.items?.[0]) summaryRows.push({ label: 'Capex method', value: capex.items[0].projection_method ?? '—' })
    const wc = assumptionsData['working_capital']
    if (wc?.items) {
      const ar = wc.items.find((i: any) => i.line_item === 'Accounts Receivable')
      if (ar?.params?.[0]) summaryRows.push({ label: 'DSO (AR days)', value: ar.params[0].value + ' days' })
    }
  }

  return (
    <div className="card mb-4">
      <button
        className="flex items-center justify-between w-full text-left"
        onClick={() => setOpen(o => !o)}
      >
        <span className="text-sm font-semibold text-gray-700">📋 Key Assumptions Summary</span>
        <span className="text-gray-400 text-xs">{open ? '▲ Hide' : '▼ Show'}</span>
      </button>
      {open && (
        <div className="mt-3 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {summaryRows.length > 0 ? summaryRows.map(r => (
            <div key={r.label} className="bg-gray-50 rounded p-2">
              <p className="text-xs text-gray-500">{r.label}</p>
              <p className="text-sm font-medium text-gray-800 truncate">{r.value}</p>
            </div>
          )) : (
            <p className="text-xs text-gray-400 col-span-5">Loading assumptions…</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function ProjectionsView({ projectId, allModulesComplete, project }: Props) {
  const [activeTab, setActiveTab] = useState<'PNL' | 'BS' | 'CF' | 'RATIOS' | 'COMPARE'>('PNL')
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null)
  const [projYears, setProjYears] = useState<number>(project?.projection_years ?? 5)
  const qc = useQueryClient()

  const { data: scenarios = [] } = useQuery({
    queryKey: ['scenarios', projectId],
    queryFn: () => scenariosApi.list(projectId).then(r => r.data),
  })

  const activeScenario = scenarios.find((s: any) => s.id === activeScenarioId)

  const { data: projections, refetch } = useQuery<ProjectionsResponse>({
    queryKey: ['projections', projectId],
    queryFn: () => projectionsApi.get(projectId).then(r => r.data),
  })

  const updateYearsMutation = useMutation({
    mutationFn: (years: number) => projectsApi.update(projectId, { projection_years: years }),
    onSuccess: () => {
      toast.success(`Projection years updated to ${projYears}`)
      qc.invalidateQueries({ queryKey: ['project', projectId] })
    },
    onError: () => toast.error('Failed to update projection years'),
  })

  const handleYearsChange = useCallback((val: number) => {
    setProjYears(val)
  }, [])

  const applyYears = useCallback(() => {
    updateYearsMutation.mutate(projYears)
  }, [projYears, updateYearsMutation])

  const runMutation = useMutation({
    mutationFn: () => projectionsApi.run(projectId),
    onSuccess: (data) => {
      toast.success('Projections complete!')
      if (data.data.warnings?.length) {
        data.data.warnings.forEach((w: string) => toast(w, { icon: '⚠️' }))
      }
      refetch()
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      qc.invalidateQueries({ queryKey: ['scenarios', projectId] })
    },
    onError: (err: unknown) => {
      const axiosErr = err as { response?: { data?: { detail?: { error?: { details?: string[] } } } } }
      const details = axiosErr.response?.data?.detail?.error?.details
      if (details) {
        toast.error(details.join('\n').slice(0, 200))
      } else {
        toast.error('Projection engine failed')
      }
    },
  })

  const exportProjections = async () => {
    try {
      const res = await projectionsApi.export(projectId)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = 'projections.xlsx'; a.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('Export failed') }
  }

  const hasProjections = projections && (projections.projected_years?.length > 0 || Object.keys(projections.PNL || {}).length > 0)
  const projectedYearsSet = new Set<number>((projections?.projected_years || []).map(Number))
  const years = hasProjections
    ? [...new Set([
        ...(projections.historical_years || []).map(Number),
        ...(projections.projected_years || []).map(Number),
        ...Object.values(projections.PNL || {}).flatMap(v => Object.keys(v)).map(Number),
      ])].sort()
    : []

  const TABS = [
    { key: 'PNL', label: 'P&L', items: PNL_ITEMS },
    { key: 'BS', label: 'Balance Sheet', items: BS_ITEMS },
    { key: 'CF', label: 'Cash Flow', items: CF_ITEMS },
    { key: 'RATIOS', label: 'Ratios', items: [] },
    { key: 'COMPARE', label: '🎭 Compare Scenarios', items: [] },
  ] as const

  return (
    <div className="space-y-6">
      {/* Scenario Manager */}
      <ScenarioManager
        projectId={projectId}
        activeScenarioId={activeScenarioId}
        onScenarioChange={setActiveScenarioId}
      />

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Projected Financials</h2>
          <p className="text-sm text-gray-500 mt-1">
            {activeScenario ? `Viewing scenario: ${activeScenario.name}` : 'Base scenario'} — projected years shown in blue.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {/* Projection years slider */}
          <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
            <span className="text-xs text-gray-500 whitespace-nowrap">Projection years:</span>
            <input
              type="range"
              min={1} max={15} step={1}
              value={projYears}
              onChange={e => handleYearsChange(Number(e.target.value))}
              className="w-24 accent-blue-600"
            />
            <span className="text-sm font-semibold text-gray-700 w-4 text-center">{projYears}</span>
            <button
              onClick={applyYears}
              disabled={updateYearsMutation.isPending || projYears === (project?.projection_years ?? 5)}
              className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-40"
            >
              Apply
            </button>
          </div>
          {hasProjections && (
            <button onClick={exportProjections} className="btn-secondary text-sm">
              ⬇ Export to Excel
            </button>
          )}
          <button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending}
            className="btn-primary"
            id="run-projections-btn"
          >
            {runMutation.isPending ? 'Running...' : '▶ Run Projections'}
          </button>
        </div>
      </div>

      {!allModulesComplete && (
        <div className="card bg-yellow-50 border-yellow-200">
          <p className="text-yellow-800 text-sm">
            ⚠ Not all modules are configured. Complete all modules (🟢) before running projections.
          </p>
        </div>
      )}

      {/* Assumptions summary panel — always visible once opened */}
      <AssumptionsSummary projectId={projectId} />

      {hasProjections && (
        <>
          <div className="flex gap-1 border-b border-gray-200">
            {TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="card">
            {activeTab === 'RATIOS' ? (
              <RatiosView projectId={projectId} />
            ) : activeTab === 'COMPARE' ? (
              <ScenarioCompare projectId={projectId} scenarios={scenarios} />
            ) : (
              TABS.filter(t => t.key === activeTab).map(tab => (
                <div key={tab.key}>
                  <FinancialTable
                    title={tab.label}
                    items={tab.items as string[]}
                    data={(projections as any)[tab.key] || {}}
                    years={years}
                    projectedYears={projectedYearsSet}
                    pnlData={tab.key === 'PNL' ? (projections as any)['PNL'] : undefined}
                  />
                  {tab.key === 'BS' && (
                    <KeyMetricsStrip
                      data={(projections as any)['BS'] || {}}
                      years={years}
                      projectedYears={projectedYearsSet}
                      pnlData={(projections as any)['PNL']}
                    />
                  )}
                </div>
              ))
            )}
          </div>
        </>
      )}

      {!hasProjections && (
        <div className="card text-center py-16">
          <p className="text-gray-500 mb-4">No data yet. Upload historical data and configure all modules, then run the engine.</p>
        </div>
      )}
    </div>
  )
}
