import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { scenariosApi } from '../../services/api'
import { useFormatNumber } from '../../utils/formatters'

interface Scenario {
  id: string
  name: string
  is_base: boolean
}

interface Props {
  projectId: string
  scenarios: Scenario[]
}

const COMPARE_ITEMS: Record<string, string[]> = {
  'P&L': ['Revenue', 'Gross Profit', 'EBIT', 'Net Income'],
  'Balance Sheet': ['Cash & Equivalents', 'Long-Term Debt', 'Retained Earnings'],
  'Cash Flow': ['Operating Cash Flow', 'Net Change in Cash'],
}

export default function ScenarioCompare({ projectId, scenarios }: Props) {
  const [selected, setSelected] = useState<string[]>(scenarios.slice(0, 3).map(s => s.id))
  const fmt = useFormatNumber()

  const { data, isFetching } = useQuery({
    queryKey: ['scenario-compare', projectId, selected],
    queryFn: () => scenariosApi.compare(projectId, selected).then(r => r.data),
    enabled: selected.length >= 2,
  })

  const years: number[] = data
    ? [...new Set(Object.values(data as Record<string, any>).flatMap(s => s.years || []))].sort()
    : []

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs text-gray-500 font-medium">Compare:</span>
        {scenarios.map(s => (
          <label key={s.id} className="flex items-center gap-1 cursor-pointer text-xs">
            <input
              type="checkbox"
              checked={selected.includes(s.id)}
              onChange={e => {
                if (e.target.checked) setSelected(prev => [...prev, s.id])
                else setSelected(prev => prev.filter(id => id !== s.id))
              }}
            />
            <span className={s.is_base ? 'font-semibold' : ''}>{s.name}</span>
          </label>
        ))}
      </div>

      {selected.length < 2 && (
        <p className="text-gray-400 text-sm text-center py-4">Select at least 2 scenarios to compare</p>
      )}

      {isFetching && <p className="text-gray-400 text-sm text-center py-4">Loading...</p>}

      {data && !isFetching && selected.length >= 2 && (
        <div className="overflow-x-auto">
          {Object.entries(COMPARE_ITEMS).map(([section, items]) => (
            <div key={section} className="mb-6">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">{section}</h4>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-1 pr-4 text-gray-500 w-48">Line Item</th>
                    {selected.map(id => {
                      const s = scenarios.find(sc => sc.id === id)
                      return years.map(y => (
                        <th key={`${id}-${y}`} className="text-right px-2 text-gray-600 min-w-20">
                          {s?.name} {y}
                        </th>
                      ))
                    })}
                  </tr>
                </thead>
                <tbody>
                  {items.map(item => (
                    <tr key={item} className="border-b border-gray-100">
                      <td className="py-1 pr-4 text-gray-700">{item}</td>
                      {selected.map(id => {
                        const sData = (data as any)[id]
                        return years.map(y => {
                          const stmtKey = section === 'P&L' ? 'PNL'
                            : section === 'Balance Sheet' ? 'BS' : 'CF'
                          const val = sData?.[stmtKey]?.[item]?.[y]
                          return (
                            <td key={`${id}-${y}`} className="py-1 px-2 text-right tabular-nums text-gray-900">
                              {val != null ? fmt(val) : '—'}
                            </td>
                          )
                        })
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      {data && !isFetching && selected.length >= 2 && Object.keys(data).some(id => !(data as any)[id]?.years?.length) && (
        <p className="text-yellow-700 text-xs bg-yellow-50 rounded px-3 py-2">
          ⚠ Some selected scenarios have not been run yet. Click ▶ on the scenario pill above to run them.
        </p>
      )}
    </div>
  )
}
