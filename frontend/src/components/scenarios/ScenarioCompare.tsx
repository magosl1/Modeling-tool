import { useMemo, useState } from 'react'
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

// KPI definitions use regex matchers because the projection engine emits
// line-item names that vary by language/historical chart of accounts (e.g.
// "Revenue" vs "Total Revenue" vs "Importe neto de cifra de negocios"). A
// hardcoded string list missed most rows on real projects.
type KpiDef = { label: string; statement: 'PNL' | 'BS' | 'CF'; match: RegExp; isHeadline?: boolean }

const KPIS: KpiDef[] = [
  { label: 'Revenue',         statement: 'PNL', match: /^(total\s+)?revenue|^sales|importe.*cifra/i, isHeadline: true },
  { label: 'Gross Profit',    statement: 'PNL', match: /gross\s*profit|margen\s*bruto/i },
  { label: 'EBITDA',          statement: 'PNL', match: /^ebitda$/i, isHeadline: true },
  { label: 'EBIT',            statement: 'PNL', match: /^ebit$|operating\s*income/i },
  { label: 'Net Income',      statement: 'PNL', match: /^net\s*income|resultado\s*neto/i, isHeadline: true },
  { label: 'Cash',            statement: 'BS',  match: /cash\s*&|cash\s*and|caja|tesorer/i },
  { label: 'Total Debt',      statement: 'BS',  match: /(long.?term|short.?term|total)\s*debt|deuda/i },
  { label: 'Equity',          statement: 'BS',  match: /total\s*equity|patrimonio/i },
  { label: 'Operating CF',    statement: 'CF',  match: /operating\s*cash\s*flow|cash\s*from\s*operations/i },
  { label: 'Free Cash Flow',  statement: 'CF',  match: /free\s*cash\s*flow|^fcf$|^fcff$/i },
]

type ScenarioPayload = {
  name: string
  is_base: boolean
  PNL: Record<string, Record<number, string>>
  BS: Record<string, Record<number, string>>
  CF: Record<string, Record<number, string>>
  years: number[]
}

function findValue(payload: ScenarioPayload | undefined, kpi: KpiDef, year: number): number | null {
  if (!payload) return null
  const stmt = payload[kpi.statement]
  if (!stmt) return null
  const key = Object.keys(stmt).find(k => kpi.match.test(k))
  if (!key) return null
  const raw = stmt[key]?.[year]
  if (raw == null) return null
  const n = parseFloat(raw)
  return isFinite(n) ? n : null
}

export default function ScenarioCompare({ projectId, scenarios }: Props) {
  const [selected, setSelected] = useState<string[]>(scenarios.slice(0, 3).map(s => s.id))
  const [showDelta, setShowDelta] = useState(false)
  const fmt = useFormatNumber()

  const { data, isFetching } = useQuery({
    queryKey: ['scenario-compare', projectId, selected],
    queryFn: () => scenariosApi.compare(projectId, selected).then(r => r.data),
    enabled: selected.length >= 2,
  })

  const years: number[] = useMemo(() => {
    if (!data) return []
    return [...new Set(Object.values(data as Record<string, ScenarioPayload>).flatMap(s => s.years || []))].sort()
  }, [data])

  // Pick the base scenario for delta math. If the user didn't include the
  // project's base in the selection, fall back to the first selected scenario
  // so deltas remain meaningful instead of silently rendering as zeros.
  const baseId = useMemo(() => {
    if (!data) return null
    const realBase = selected.find(id => (data as any)[id]?.is_base)
    return realBase ?? selected[0] ?? null
  }, [data, selected])

  const renderCell = (kpi: KpiDef, year: number, scenarioId: string) => {
    const payload = (data as any)?.[scenarioId] as ScenarioPayload | undefined
    const v = findValue(payload, kpi, year)
    if (v == null) return <span className="text-gray-300">—</span>
    if (showDelta && baseId && scenarioId !== baseId) {
      const baseV = findValue((data as any)?.[baseId] as ScenarioPayload | undefined, kpi, year)
      if (baseV == null || baseV === 0) return <span className="text-gray-400">{fmt(v)}</span>
      const delta = v - baseV
      const pct = (delta / Math.abs(baseV)) * 100
      const color = delta > 0 ? 'text-emerald-600' : delta < 0 ? 'text-rose-600' : 'text-gray-500'
      const sign = delta > 0 ? '+' : ''
      return (
        <span className={`tabular-nums ${color}`} title={`Absolute: ${fmt(v)}`}>
          {sign}{pct.toFixed(1)}%
        </span>
      )
    }
    return <span className="tabular-nums text-gray-900">{fmt(v)}</span>
  }

  const headlineKpis = KPIS.filter(k => k.isHeadline)
  const terminalYear = years[years.length - 1]

  const missingScenarios = data
    ? selected.filter(id => !((data as any)[id]?.years?.length))
    : []

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 justify-between">
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
        <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={showDelta}
            onChange={e => setShowDelta(e.target.checked)}
          />
          Show Δ vs base (%)
        </label>
      </div>

      {selected.length < 2 && (
        <p className="text-gray-400 text-sm text-center py-4">Select at least 2 scenarios to compare</p>
      )}

      {isFetching && <p className="text-gray-400 text-sm text-center py-4">Loading…</p>}

      {missingScenarios.length > 0 && !isFetching && (
        <p className="text-yellow-700 text-xs bg-yellow-50 rounded px-3 py-2">
          ⚠ {missingScenarios.length} selected scenario(s) have no projections yet — run them from the pills above.
        </p>
      )}

      {data && !isFetching && selected.length >= 2 && terminalYear && (
        <>
          {/* Terminal-year KPI summary: at-a-glance card per scenario for the
              metrics analysts ask about first (Revenue / EBITDA / NI in the
              final projected year). */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {headlineKpis.map(kpi => (
              <div key={kpi.label} className="border border-gray-200 rounded-lg p-3 bg-white">
                <div className="text-xs text-gray-500 mb-2">
                  {kpi.label} <span className="text-gray-400">(FY {terminalYear})</span>
                </div>
                <div className="space-y-1">
                  {selected.map(id => {
                    const s = (data as any)[id] as ScenarioPayload | undefined
                    const v = findValue(s, kpi, terminalYear)
                    const baseV = baseId ? findValue((data as any)[baseId], kpi, terminalYear) : null
                    const delta = v != null && baseV != null && baseV !== 0 ? ((v - baseV) / Math.abs(baseV)) * 100 : null
                    const isBase = id === baseId
                    return (
                      <div key={id} className="flex items-center justify-between text-sm">
                        <span className={`truncate ${isBase ? 'font-semibold text-gray-700' : 'text-gray-600'}`}>
                          {s?.name ?? '—'}
                        </span>
                        <span className="flex items-baseline gap-2">
                          <span className="tabular-nums text-gray-900">{v != null ? fmt(v) : '—'}</span>
                          {delta != null && !isBase && (
                            <span className={`text-xs tabular-nums ${delta > 0 ? 'text-emerald-600' : delta < 0 ? 'text-rose-600' : 'text-gray-400'}`}>
                              {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                            </span>
                          )}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Detail table: years are the outer column group, scenarios nest
              within each year. This stays readable even with 5 scenarios ×
              10 years because the eye scans one year-block at a time. */}
          <div className="overflow-x-auto border border-gray-200 rounded-lg bg-white">
            <table className="w-full text-xs">
              <thead className="bg-gray-50">
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3 text-gray-500 sticky left-0 bg-gray-50 w-44">Line Item</th>
                  {years.map(y => (
                    <th
                      key={y}
                      colSpan={selected.length}
                      className="text-center px-2 py-2 text-gray-600 border-l border-gray-200"
                    >
                      FY {y}
                    </th>
                  ))}
                </tr>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="sticky left-0 bg-gray-50"></th>
                  {years.flatMap(y => selected.map(id => {
                    const s = scenarios.find(sc => sc.id === id)
                    return (
                      <th
                        key={`${y}-${id}`}
                        className={`text-right px-2 py-1 text-[10px] font-normal text-gray-500 ${id === baseId ? 'text-gray-700 font-semibold' : ''}`}
                      >
                        {s?.name ?? '—'}
                      </th>
                    )
                  }))}
                </tr>
              </thead>
              <tbody>
                {KPIS.map(kpi => (
                  <tr key={kpi.label} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-1.5 px-3 text-gray-700 sticky left-0 bg-white">{kpi.label}</td>
                    {years.flatMap(y => selected.map(id => (
                      <td key={`${kpi.label}-${y}-${id}`} className="py-1.5 px-2 text-right border-l border-gray-100">
                        {renderCell(kpi, y, id)}
                      </td>
                    )))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
