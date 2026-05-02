import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { valuationApi, whatIfApi } from '../../services/api'
import type { WhatIfResponse } from '../../services/api'
import { useFormatNumber } from '../../utils/formatters'
import { useActiveScenarioId } from '../../store/scenarioStore'

interface Props {
  projectId: string
}

interface SliderState {
  revenue_growth_pp_delta: number
  cogs_growth_pp_delta: number
  opex_growth_pp_delta: number
  capex_pct_pp_delta: number
  wacc_pct: number
  terminal_growth_pct: number
}

const DEFAULT_WACC = 9
const DEFAULT_TG = 2

/**
 * Sliders panel: drag → debounced POST to /whatif → headline metrics + equity
 * value update without ever mutating persisted assumptions.
 *
 * Designed for the non-expert user — the four delta sliders are pp shifts on
 * the active scenario's assumptions, the two valuation sliders are absolute
 * (analysts intuitively *set* WACC and terminal growth, not nudge them).
 */
export default function WhatIfPanel({ projectId }: Props) {
  const fmt = useFormatNumber()
  const activeScenarioId = useActiveScenarioId(projectId)

  // Seed valuation sliders from saved inputs so the user starts where they
  // left off, not at arbitrary defaults that would jolt the equity value.
  const { data: savedVal } = useQuery({
    queryKey: ['valuation', projectId],
    queryFn: () => valuationApi.get(projectId).then(r => r.data).catch(() => null),
    staleTime: 30_000,
  })

  const initial: SliderState = useMemo(() => ({
    revenue_growth_pp_delta: 0,
    cogs_growth_pp_delta: 0,
    opex_growth_pp_delta: 0,
    capex_pct_pp_delta: 0,
    wacc_pct: savedVal?.wacc ? Number(savedVal.wacc) : DEFAULT_WACC,
    terminal_growth_pct: savedVal?.terminal_growth_rate ? Number(savedVal.terminal_growth_rate) : DEFAULT_TG,
  }), [savedVal])

  const [state, setState] = useState<SliderState>(initial)
  // Reset when saved valuation arrives (only on first load).
  useEffect(() => {
    setState(initial)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedVal?.wacc, savedVal?.terminal_growth_rate])

  // Debounce the slider drag → API. 300ms feels live without flooding the
  // backend (each call runs the projection engine + DCF).
  const [result, setResult] = useState<WhatIfResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const reqIdRef = useRef(0)

  useEffect(() => {
    const t = setTimeout(async () => {
      const myId = ++reqIdRef.current
      setLoading(true)
      setError(null)
      try {
        const res = await whatIfApi.run(projectId, {
          scenario_id: activeScenarioId,
          ...state,
        })
        // Drop stale responses (user kept dragging while a request was in flight).
        if (myId === reqIdRef.current) setResult(res.data)
      } catch (e: any) {
        if (myId === reqIdRef.current) {
          setError(e.response?.data?.detail || 'What-if failed')
          setResult(null)
        }
      } finally {
        if (myId === reqIdRef.current) setLoading(false)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [projectId, activeScenarioId, state])

  const baselineEquity = result?.valuation?.equity_value
  const allDeltasZero =
    state.revenue_growth_pp_delta === 0 &&
    state.cogs_growth_pp_delta === 0 &&
    state.opex_growth_pp_delta === 0 &&
    state.capex_pct_pp_delta === 0 &&
    state.wacc_pct === initial.wacc_pct &&
    state.terminal_growth_pct === initial.terminal_growth_pct

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-800">🎚️ What-If Sliders</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Live re-projection — never modifies your saved assumptions.
            {activeScenarioId ? ' Anchored to the active scenario.' : ' Anchored to the base scenario.'}
          </p>
        </div>
        <button
          className="text-xs text-gray-500 hover:text-gray-800 underline"
          onClick={() => setState(initial)}
          disabled={allDeltasZero}
        >
          Reset
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
        <Slider
          label="Revenue growth"
          unit="pp"
          min={-20} max={20} step={0.5}
          value={state.revenue_growth_pp_delta}
          onChange={v => setState(s => ({ ...s, revenue_growth_pp_delta: v }))}
        />
        <Slider
          label="COGS growth"
          unit="pp"
          min={-20} max={20} step={0.5}
          value={state.cogs_growth_pp_delta}
          onChange={v => setState(s => ({ ...s, cogs_growth_pp_delta: v }))}
        />
        <Slider
          label="OpEx growth"
          unit="pp"
          min={-20} max={20} step={0.5}
          value={state.opex_growth_pp_delta}
          onChange={v => setState(s => ({ ...s, opex_growth_pp_delta: v }))}
        />
        <Slider
          label="CapEx % of revenue"
          unit="pp"
          min={-10} max={10} step={0.5}
          value={state.capex_pct_pp_delta}
          onChange={v => setState(s => ({ ...s, capex_pct_pp_delta: v }))}
        />
        <Slider
          label="WACC"
          unit="%"
          absolute
          min={3} max={20} step={0.25}
          value={state.wacc_pct}
          onChange={v => setState(s => ({ ...s, wacc_pct: v }))}
        />
        <Slider
          label="Terminal growth"
          unit="%"
          absolute
          min={-2} max={5} step={0.25}
          value={state.terminal_growth_pct}
          onChange={v => setState(s => ({ ...s, terminal_growth_pct: v }))}
        />
      </div>

      <div className="mt-5 pt-4 border-t border-gray-100">
        {error && <p className="text-xs text-rose-600 bg-rose-50 rounded px-3 py-2">{error}</p>}
        {result?.valuation_error && (
          <p className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-2">{result.valuation_error}</p>
        )}
        {result && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Equity Value" value={baselineEquity != null ? fmt(baselineEquity) : '—'} highlight />
            <Metric label="Enterprise Value" value={result.valuation ? fmt(result.valuation.enterprise_value) : '—'} />
            <Metric label={`Terminal Revenue (FY ${result.metrics.year})`} value={result.metrics.revenue != null ? fmt(result.metrics.revenue) : '—'} />
            <Metric label={`Terminal EBITDA (FY ${result.metrics.year})`} value={result.metrics.ebitda != null ? fmt(result.metrics.ebitda) : '—'} />
          </div>
        )}
        {loading && <p className="text-xs text-gray-400 mt-2">Recomputing…</p>}
      </div>
    </div>
  )
}

function Slider({
  label, value, min, max, step, unit, absolute, onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit: 'pp' | '%'
  absolute?: boolean
  onChange: (v: number) => void
}) {
  const display = absolute
    ? `${value.toFixed(2)}${unit === '%' ? '%' : ''}`
    : `${value > 0 ? '+' : ''}${value.toFixed(2)}${unit === 'pp' ? ' pp' : '%'}`
  const tone = absolute
    ? 'text-gray-700'
    : value > 0 ? 'text-emerald-600' : value < 0 ? 'text-rose-600' : 'text-gray-500'
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <label className="text-xs font-medium text-gray-700">{label}</label>
        <span className={`text-xs tabular-nums font-semibold ${tone}`}>{display}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full accent-fuchsia-500"
      />
    </div>
  )
}

function Metric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`rounded-lg p-3 ${highlight ? 'bg-gradient-to-br from-fuchsia-50 to-indigo-50 border border-fuchsia-200' : 'bg-gray-50 border border-gray-200'}`}>
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`text-base font-bold tabular-nums ${highlight ? 'text-indigo-700' : 'text-gray-800'}`}>{value}</div>
    </div>
  )
}
