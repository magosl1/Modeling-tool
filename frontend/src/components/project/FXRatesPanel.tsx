import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fxApi, projectsApi, projectionsApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Props { projectId: string }

export default function FXRatesPanel({ projectId }: Props) {
  const qc = useQueryClient()
  const [rates, setRates] = useState<Record<number, number>>({})

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId).then(r => r.data),
  })

  // Calculate projection years array
  const projectionYears: number[] = []
  if (project?.fiscal_year_end && project?.projection_years) {
    const lastHistYear = parseInt(project.fiscal_year_end.substring(0, 4))
    for (let i = 1; i <= project.projection_years; i++) {
      projectionYears.push(lastHistYear + i)
    }
  }

  const { isLoading } = useQuery({
    queryKey: ['fx-rates', projectId],
    queryFn: () => fxApi.get(projectId).then(r => r.data),
    meta: {
      onSuccess: (data: any) => {
        if (data && data.rates) {
          setRates(data.rates)
        }
      }
    }
  })

  const runMutation = useMutation({
    mutationFn: () => projectionsApi.run(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projections', projectId] }),
  })

  const saveMutation = useMutation({
    mutationFn: (data: Record<number, number>) => fxApi.save(projectId, { rates: data }),
    onSuccess: () => {
      toast.success('FX Rates saved')
      runMutation.mutate()
    },
    onError: () => toast.error('Failed to save FX rates')
  })

  const updateRate = (year: number, val: string) => {
    setRates(prev => ({ ...prev, [year]: parseFloat(val) || 1.0 }))
  }

  if (isLoading || !project) return <div className="card text-center text-gray-500">Loading FX Rates...</div>

  return (
    <div className="card max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">Exchange Rates</h2>
        <p className="text-sm text-gray-500 mt-1">Configure forecasted exchange rates for international modeling.</p>
        <p className="text-xs text-blue-600 bg-blue-50 p-2 rounded mt-2 border border-blue-100">
          Base Currency: <strong>{project.currency}</strong>
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        {projectionYears.map(y => (
          <div key={y} className="bg-gray-50 p-3 rounded-lg border border-gray-200">
            <label className="text-xs font-semibold text-gray-600 block mb-1">Year {y}</label>
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-sm">1 USD =</span>
              <input
                type="number"
                step="0.01"
                className="input text-sm text-right flex-1"
                value={rates[y] || 1.0}
                onChange={e => updateRate(y, e.target.value)}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end pt-4 border-t border-gray-100">
        <button
          onClick={() => saveMutation.mutate(rates)}
          disabled={saveMutation.isPending}
          className="btn-primary"
        >
          {saveMutation.isPending ? 'Saving...' : 'Save FX Rates'}
        </button>
      </div>
    </div>
  )
}
