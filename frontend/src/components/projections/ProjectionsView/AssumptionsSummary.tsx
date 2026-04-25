import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { assumptionsApi } from '../../../services/api'

const MODULES = ['revenue', 'cogs', 'opex', 'da', 'working_capital', 'capex', 'tax']

/** Collapsible "Key Assumptions Summary" chip under the projections header. */
export default function AssumptionsSummary({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const { data: assumptionsData } = useQuery({
    queryKey: ['assumptions-all', projectId],
    queryFn: async () => {
      const results: Record<string, any> = {}
      await Promise.all(
        MODULES.map(async m => {
          try {
            const r = await assumptionsApi.getModule(projectId, m)
            results[m] = r.data
          } catch {
            /* ok */
          }
        })
      )
      return results
    },
    enabled: open,
  })

  const summaryRows: { label: string; value: string }[] = []
  if (assumptionsData) {
    const rev = assumptionsData['revenue']
    if (rev?.items?.[0]) summaryRows.push({ label: 'Revenue method', value: rev.items[0].projection_method ?? '—' })
    const cogs = assumptionsData['cogs']
    if (cogs?.items?.[0]?.params?.[0])
      summaryRows.push({ label: 'COGS % revenue', value: cogs.items[0].params[0].value + '%' })
    const tax = assumptionsData['tax']
    if (tax?.items?.[0]?.params?.[0])
      summaryRows.push({ label: 'Effective tax rate', value: tax.items[0].params[0].value + '%' })
    const capex = assumptionsData['capex']
    if (capex?.items?.[0])
      summaryRows.push({ label: 'Capex method', value: capex.items[0].projection_method ?? '—' })
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
          {summaryRows.length > 0 ? (
            summaryRows.map(r => (
              <div key={r.label} className="bg-gray-50 rounded p-2">
                <p className="text-xs text-gray-500">{r.label}</p>
                <p className="text-sm font-medium text-gray-800 truncate">{r.value}</p>
              </div>
            ))
          ) : (
            <p className="text-xs text-gray-400 col-span-5">Loading assumptions…</p>
          )}
        </div>
      )}
    </div>
  )
}
