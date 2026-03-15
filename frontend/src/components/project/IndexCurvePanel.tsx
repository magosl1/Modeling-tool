import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { curvesApi, projectsApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Props { projectId: string }

export default function IndexCurvePanel({ projectId }: Props) {
  const qc = useQueryClient()
  const [curves, setCurves] = useState<Record<string, { is_percentage: boolean, values: Record<string, number> }>>({})
  const [newCurveName, setNewCurveName] = useState('')

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId).then(r => r.data),
  })

  // Calculate projection years array
  const projectionYears: string[] = []
  if (project?.fiscal_year_end && project?.projection_years) {
    const lastHistYear = parseInt(project.fiscal_year_end.substring(0, 4))
    for (let i = 1; i <= project.projection_years; i++) {
        projectionYears.push(String(lastHistYear + i))
    }
  }

  const { isLoading } = useQuery({
    queryKey: ['curves', projectId],
    queryFn: () => curvesApi.get(projectId).then(r => r.data),
    meta: {
      onSuccess: (data: any) => {
        if (data) setCurves(data)
      }
    }
  })

  const saveMutation = useMutation({
    mutationFn: (data: Record<string, { is_percentage: boolean, values: Record<string, number> }>) => curvesApi.save(projectId, data),
    onSuccess: () => {
      toast.success('Curves saved')
      qc.invalidateQueries({ queryKey: ['curves', projectId] })
    },
    onError: () => toast.error('Failed to save curves')
  })

  const addCurve = () => {
    const name = newCurveName.trim()
    if (!name) return
    if (curves[name]) {
        toast.error('Curve already exists')
        return
    }
    setCurves(prev => ({
        ...prev,
        [name]: {
            is_percentage: false,
            values: projectionYears.reduce((acc, y) => ({ ...acc, [y]: 1.0 }), {})
        }
    }))
    setNewCurveName('')
  }

  const toggleIsPercentage = (curveName: string) => {
    setCurves(prev => ({
        ...prev,
        [curveName]: {
            ...prev[curveName],
            is_percentage: !prev[curveName].is_percentage
        }
    }))
  }

  const updateCurve = (curveName: string, year: string, val: string) => {
    setCurves(prev => ({
        ...prev,
        [curveName]: {
            ...prev[curveName],
            values: {
                ...prev[curveName].values,
                [year]: parseFloat(val) || 0
            }
        }
    }))
  }

  const removeCurve = (curveName: string) => {
    const updated = { ...curves }
    delete updated[curveName]
    setCurves(updated)
  }

  if (isLoading || !project) return <div className="card text-center text-gray-500">Loading Curves...</div>

  return (
    <div className="card max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">External Indices / Curves</h2>
        <p className="text-sm text-gray-500 mt-1">
          Pre-load external forecasts (e.g. Copper prices, Inflation rates, GDP growth) to be referenced in the assumption modules.
        </p>
      </div>

      <div className="flex gap-2 mb-6">
        <input 
            type="text" 
            className="input flex-1" 
            placeholder="e.g. Copper Price (USD/mt)" 
            value={newCurveName}
            onChange={e => setNewCurveName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addCurve()}
        />
        <button onClick={addCurve} className="btn-secondary whitespace-nowrap">+ Add Curve</button>
      </div>

      {Object.keys(curves).length === 0 ? (
        <div className="text-center py-8 text-gray-500 border border-dashed rounded-lg bg-gray-50">
            No curves defined yet. Add one above.
        </div>
      ) : (
        <div className="space-y-6">
            {Object.entries(curves).map(([curveName, curveData]) => (
                <div key={curveName} className="border border-gray-200 rounded-lg p-4 bg-gray-50 relative">
                    <button 
                        onClick={() => removeCurve(curveName)} 
                        className="absolute top-4 right-4 text-gray-400 hover:text-red-500"
                        title="Remove curve"
                    >
                        ✕
                    </button>
                    <div className="flex justify-between items-center pr-8 mb-3">
                        <h3 className="font-semibold text-gray-800">{curveName}</h3>
                        <label className="flex items-center gap-2 text-sm font-medium text-gray-600 cursor-pointer">
                            <input 
                                type="checkbox"
                                className="rounded border-gray-300 text-primary-600 shadow-sm focus:border-primary-300 focus:ring focus:ring-primary-200 focus:ring-opacity-50"
                                checked={curveData.is_percentage}
                                onChange={() => toggleIsPercentage(curveName)}
                            />
                            Is Percentage (%)?
                        </label>
                    </div>
                    <div className="flex gap-3 overflow-x-auto pb-2">
                        {projectionYears.map(y => (
                            <div key={y} className="flex-1 min-w-[120px]">
                                <label className="text-xs font-medium text-gray-600 mb-1 block">Year {y}</label>
                                <div className="relative">
                                  <input
                                      type="number"
                                      step="0.01"
                                      className="input text-sm text-right w-full pr-8"
                                      value={curveData.values[y] || 0}
                                      onChange={e => updateCurve(curveName, y, e.target.value)}
                                  />
                                  {curveData.is_percentage && (
                                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm pointer-events-none">%</span>
                                  )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
      )}

      <div className="flex justify-end pt-4 border-t border-gray-100 mt-6">
        <button
          onClick={() => saveMutation.mutate(curves)}
          disabled={saveMutation.isPending}
          className="btn-primary"
        >
          {saveMutation.isPending ? 'Saving...' : 'Save Curves'}
        </button>
      </div>
    </div>
  )
}
