import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { simulationApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Driver {
  id: string
  driver: string
  distribution: string
  mean: number
  std: number
}

const DRIVER_OPTIONS = [
  { value: 'revenue_growth', label: 'Revenue Growth Rate (%)' },
  { value: 'gross_margin', label: 'Gross Margin (%)' },
  { value: 'wacc', label: 'WACC (%)' },
  { value: 'terminal_growth', label: 'Terminal Growth Rate (%)' },
]

interface Props {
  projectId: string
  scenarioId?: string
}

export default function MonteCarloView({ projectId, scenarioId }: Props) {
  const [drivers, setDrivers] = useState<Driver[]>([
    { id: '1', driver: 'revenue_growth', distribution: 'normal', mean: 5, std: 2 },
    { id: '2', driver: 'gross_margin', distribution: 'normal', mean: 40, std: 3 },
  ])
  const [nIterations, setNIterations] = useState(1000)

  const { data: latest, refetch } = useQuery({
    queryKey: ['mc-latest', projectId, scenarioId],
    queryFn: () => simulationApi.getLatest(projectId, scenarioId).then(r => r.data),
  })

  const runMutation = useMutation({
    mutationFn: () => simulationApi.run(projectId, {
      drivers: drivers.map(d => ({
        driver: d.driver,
        distribution: d.distribution,
        mean: d.mean,
        std: d.std,
      })),
      n_iterations: nIterations,
      scenario_id: scenarioId || null,
    }),
    onSuccess: () => {
      toast.success('Simulation complete!')
      refetch()
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Simulation failed'),
  })

  const addDriver = () => setDrivers(prev => [
    ...prev,
    { id: Date.now().toString(), driver: 'revenue_growth', distribution: 'normal', mean: 5, std: 2 }
  ])

  const updateDriver = (id: string, field: keyof Driver, value: any) =>
    setDrivers(prev => prev.map(d => d.id === id ? { ...d, [field]: value } : d))

  const removeDriver = (id: string) => setDrivers(prev => prev.filter(d => d.id !== id))

  const hasResults = latest && latest.n_valid > 0
  const maxBin = hasResults ? Math.max(...(latest.histogram || []).map((b: any) => b.count)) : 1

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Monte Carlo Simulation</h3>
          <p className="text-sm text-gray-500">Randomize key drivers across thousands of runs to get a distribution of equity values.</p>
        </div>
        <button
          onClick={() => runMutation.mutate()}
          disabled={runMutation.isPending}
          className="btn-primary"
          id="mc-run-btn"
        >
          {runMutation.isPending ? '⏳ Running...' : '▶ Run Simulation'}
        </button>
      </div>

      {/* Driver Configuration */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-gray-700">Driver Configuration</h4>
          <button onClick={addDriver} className="text-xs text-primary-600 hover:text-primary-700 font-medium">
            + Add Driver
          </button>
        </div>
        <div className="space-y-2">
          {drivers.map(d => (
            <div key={d.id} className="flex gap-2 items-center">
              <select
                className="flex-1 text-sm border border-gray-300 rounded px-2 py-1.5"
                value={d.driver}
                onChange={e => updateDriver(d.id, 'driver', e.target.value)}
              >
                {DRIVER_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <select
                className="text-sm border border-gray-300 rounded px-2 py-1.5 w-28"
                value={d.distribution}
                onChange={e => updateDriver(d.id, 'distribution', e.target.value)}
              >
                <option value="normal">Normal</option>
                <option value="triangular">Triangular</option>
                <option value="uniform">Uniform</option>
              </select>
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <span>μ</span>
                <input
                  type="number"
                  className="w-16 border border-gray-300 rounded px-2 py-1.5 text-sm"
                  value={d.mean}
                  onChange={e => updateDriver(d.id, 'mean', parseFloat(e.target.value))}
                />
              </div>
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <span>σ</span>
                <input
                  type="number"
                  className="w-16 border border-gray-300 rounded px-2 py-1.5 text-sm"
                  value={d.std}
                  onChange={e => updateDriver(d.id, 'std', parseFloat(e.target.value))}
                />
              </div>
              <button onClick={() => removeDriver(d.id)} className="text-red-400 hover:text-red-600 px-1">×</button>
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-2 text-sm text-gray-600">
          <label>Iterations:</label>
          <input
            type="number"
            min={100} max={5000} step={100}
            value={nIterations}
            onChange={e => setNIterations(parseInt(e.target.value))}
            className="w-24 border border-gray-300 rounded px-2 py-1"
          />
        </div>
      </div>

      {/* Results */}
      {hasResults && (
        <div className="space-y-4">
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: 'P10', value: latest.p10, color: 'text-red-600' },
              { label: 'P25', value: latest.p25, color: 'text-orange-500' },
              { label: 'P50 (Median)', value: latest.p50, color: 'text-blue-600 font-bold' },
              { label: 'P75', value: latest.p75, color: 'text-green-500' },
              { label: 'P90', value: latest.p90, color: 'text-green-700' },
            ].map(stat => (
              <div key={stat.label} className="card text-center py-3">
                <div className="text-xs text-gray-500 mb-1">{stat.label}</div>
                <div className={`text-sm font-mono ${stat.color}`}>
                  {stat.value != null ? stat.value.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '—'}
                </div>
              </div>
            ))}
          </div>

          {/* Histogram */}
          <div className="card">
            <h4 className="text-sm font-medium text-gray-700 mb-3">Equity Value Distribution</h4>
            <div className="flex items-end gap-0.5 h-32">
              {(latest.histogram || []).map((bin: any, i: number) => (
                <div
                  key={i}
                  className="flex-1 bg-primary-400 hover:bg-primary-500 transition-colors rounded-t"
                  style={{ height: `${(bin.count / maxBin) * 100}%` }}
                  title={`${bin.bin_start.toLocaleString()} – ${bin.bin_end.toLocaleString()}: ${bin.count} runs`}
                />
              ))}
            </div>
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>{latest.min?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
              <span>Mean: {latest.mean?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
              <span>{latest.max?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              {latest.n_valid}/{latest.n_iterations} valid iterations · σ = {latest.std?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </p>
          </div>
        </div>
      )}

      {!hasResults && !runMutation.isPending && (
        <div className="card text-center py-10 text-gray-400">
          <p>Configure drivers and click Run to see results.</p>
        </div>
      )}
    </div>
  )
}
