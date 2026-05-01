import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import toast from 'react-hot-toast'

import { projectionsApi, projectsApi, scenariosApi } from '../../../services/api'
import type { ProjectionsResponse } from '../../../types/api'
import ScenarioCompare from '../../scenarios/ScenarioCompare'
import ScenarioManager from '../../scenarios/ScenarioManager'
import RatiosView from '../RatiosView'
import AssumptionsSummary from './AssumptionsSummary'
import FinancialTable from './FinancialTable'
import KeyMetricsStrip from './KeyMetricsStrip'
import { BS_ITEMS, CF_ITEMS, PNL_ITEMS } from './constants'

interface Props {
  projectId: string
  allModulesComplete: boolean
  project?: any
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

  const [isPolling, setIsPolling] = useState(false)
  
  const pollStatus = async (taskId: string) => {
    try {
      const res = await projectionsApi.checkStatus(projectId, taskId)
      if (res.data.status === 'completed') {
        setIsPolling(false)
        toast.success('Projections complete!')
        refetch()
        qc.invalidateQueries({ queryKey: ['project', projectId] })
        qc.invalidateQueries({ queryKey: ['scenarios', projectId] })
      } else {
        setTimeout(() => pollStatus(taskId), 2000)
      }
    } catch (err: any) {
      setIsPolling(false)
      const details = err.response?.data?.detail?.error?.details
      if (details) {
        toast.error(details.join('\n').slice(0, 200))
      } else {
        toast.error('Projection engine failed during async execution')
      }
    }
  }

  const runMutation = useMutation({
    mutationFn: () => projectionsApi.run(projectId),
    onSuccess: data => {
      if (data.status === 202 && 'task_id' in data.data) {
        setIsPolling(true)
        toast('Running projections in background...', { icon: '⏳' })
        pollStatus(data.data.task_id)
      } else {
        toast.success('Projections complete!')
        if ('warnings' in data.data && (data.data as any).warnings?.length) {
          (data.data as any).warnings.forEach((w: string) => toast(w, { icon: '⚠️' }))
        }
        refetch()
        qc.invalidateQueries({ queryKey: ['project', projectId] })
        qc.invalidateQueries({ queryKey: ['scenarios', projectId] })
      }
    },
    onError: (err: unknown) => {
      const axiosErr = err as {
        response?: { data?: { detail?: { error?: { details?: string[] } } } }
      }
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
      a.href = url
      a.download = 'projections.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Export failed')
    }
  }

  const hasProjections =
    projections &&
    (projections.projected_years?.length > 0 || Object.keys(projections.PNL || {}).length > 0)
  const projectedYearsSet = new Set<number>((projections?.projected_years || []).map(Number))
  const years = hasProjections
    ? [
        ...new Set([
          ...(projections.historical_years || []).map(Number),
          ...(projections.projected_years || []).map(Number),
          ...Object.values(projections.PNL || {})
            .flatMap(v => Object.keys(v))
            .map(Number),
        ]),
      ].sort()
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
          <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
            <span className="text-xs text-gray-500 whitespace-nowrap">Projection years:</span>
            <input
              type="range"
              min={1}
              max={15}
              step={1}
              value={projYears}
              onChange={e => handleYearsChange(Number(e.target.value))}
              className="w-24 accent-blue-600"
            />
            <span className="text-sm font-semibold text-gray-700 w-4 text-center">{projYears}</span>
            <button
              onClick={applyYears}
              disabled={
                updateYearsMutation.isPending || projYears === (project?.projection_years ?? 5)
              }
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
            disabled={runMutation.isPending || isPolling}
            className="btn-primary"
            id="run-projections-btn"
          >
            {runMutation.isPending || isPolling ? 'Running...' : '▶ Run Projections'}
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
          <p className="text-gray-500 mb-4">
            No data yet. Upload historical data and configure all modules, then run the engine.
          </p>
        </div>
      )}
    </div>
  )
}
