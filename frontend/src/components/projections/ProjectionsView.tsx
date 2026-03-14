import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectionsApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Props { projectId: string; allModulesComplete: boolean }

const PNL_ITEMS = [
  'Revenue', 'Cost of Goods Sold', 'Gross Profit', 'SG&A', 'R&D', 'D&A',
  'Amortization of Intangibles', 'Other OpEx', 'EBIT', 'Interest Income',
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
  'Gross Profit', 'EBIT', 'EBT', 'Net Income',
  'Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow', 'Net Change in Cash',
])

function fmt(val: string | undefined) {
  if (val === undefined || val === null) return '—'
  const n = parseFloat(val)
  if (isNaN(n)) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

function FinancialTable({ title, items, data, years, projectedYears }: { title: string; items: string[]; data: Record<string, Record<string, string>>; years: number[]; projectedYears: Set<number> }) {
  return (
    <div className="mb-8">
      <h3 className="font-semibold text-gray-800 mb-3">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 pr-4 font-medium text-gray-600 w-64">Line Item</th>
              {years.map(y => (
                <th key={y} className={`text-right py-2 px-3 font-medium min-w-24 ${projectedYears.has(y) ? 'text-blue-600 bg-blue-50' : 'text-gray-600'}`}>{y}{projectedYears.has(y) ? 'P' : ''}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(item => {
              const isSubtotal = SUBTOTALS.has(item)
              return (
                <tr
                  key={item}
                  className={`border-b border-gray-100 ${isSubtotal ? 'font-semibold bg-gray-50' : ''}`}
                >
                  <td className="py-1.5 pr-4 text-gray-700">{item}</td>
                  {years.map(y => (
                    <td key={y} className={`py-1.5 px-3 text-right tabular-nums ${projectedYears.has(y) ? 'text-blue-900 bg-blue-50/50' : 'text-gray-900'}`}>
                      {fmt(data[item]?.[y])}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function ProjectionsView({ projectId, allModulesComplete }: Props) {
  const [activeTab, setActiveTab] = useState<'PNL' | 'BS' | 'CF'>('PNL')
  const qc = useQueryClient()

  const { data: projections, refetch } = useQuery({
    queryKey: ['projections', projectId],
    queryFn: () => projectionsApi.get(projectId).then(r => r.data),
  })

  const runMutation = useMutation({
    mutationFn: () => projectionsApi.run(projectId),
    onSuccess: (data) => {
      toast.success('Projections complete!')
      if (data.data.warnings?.length) {
        data.data.warnings.forEach((w: string) => toast(w, { icon: '⚠️' }))
      }
      refetch()
      qc.invalidateQueries({ queryKey: ['project', projectId] })
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      if (detail?.error?.details) {
        toast.error(detail.error.details.join('\n').slice(0, 200))
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
        ...Object.values(projections.PNL as Record<string, Record<string, string>> || {}).flatMap(v => Object.keys(v)).map(Number),
      ])].sort()
    : []

  const TABS = [
    { key: 'PNL', label: 'P&L', items: PNL_ITEMS },
    { key: 'BS', label: 'Balance Sheet', items: BS_ITEMS },
    { key: 'CF', label: 'Cash Flow', items: CF_ITEMS },
  ] as const

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Projected Financials</h2>
          <p className="text-sm text-gray-500 mt-1">All projected years shown in blue.</p>
        </div>
        <div className="flex gap-3">
          {hasProjections && (
            <button onClick={exportProjections} className="btn-secondary text-sm">
              ⬇ Export to Excel
            </button>
          )}
          <button
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending}
            className="btn-primary"
            title={!allModulesComplete ? 'Configure all modules first' : undefined}
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
            {TABS.filter(t => t.key === activeTab).map(tab => (
              <FinancialTable
                key={tab.key}
                title={tab.label}
                items={tab.items}
                data={projections[tab.key] || {}}
                years={years}
                projectedYears={projectedYearsSet}
              />
            ))}
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
