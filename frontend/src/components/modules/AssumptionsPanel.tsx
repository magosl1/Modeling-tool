import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { assumptionsApi, projectionsApi, projectsApi, historicalApi, scenariosApi } from '../../services/api'
import type { AssumptionItem } from '../../types/api'
import toast from 'react-hot-toast'
import ModuleConfigurator from './ModuleConfigurator'
import { useActiveScenarioId } from '../../store/scenarioStore'

interface Props { projectId: string }

const MODULES = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'cogs', label: 'COGS / Gross Margin' },
  { key: 'opex', label: 'Operating Expenses' },
  { key: 'da', label: 'Depreciation & Amortization' },
  { key: 'working_capital', label: 'Working Capital' },
  { key: 'capex', label: 'Capital Expenditures' },
  { key: 'debt', label: 'Debt & Financing' },
  { key: 'tax', label: 'Tax' },
  { key: 'dividends', label: 'Dividends' },
  { key: 'interest_income', label: 'Interest Income' },
  { key: 'non_operating', label: 'Non-Operating & Other Items' },
]

export default function AssumptionsPanel({ projectId }: Props) {
  const { module: activeModule } = useParams<{ module?: string }>()
  const qc = useQueryClient()
  const activeScenarioId = useActiveScenarioId(projectId)

  const currentModule = activeModule || MODULES[0].key
  const currentModuleMeta = MODULES.find(m => m.key === currentModule)

  // Resolve the active scenario name for the header banner. Reading from the
  // scenarios list (already cached by ScenarioManager) keeps this cheap.
  const { data: scenarios = [] } = useQuery<{ id: string; name: string; is_base: boolean }[]>({
    queryKey: ['scenarios', projectId],
    queryFn: () => scenariosApi.list(projectId).then(r => r.data),
    staleTime: 30_000,
  })
  const activeScenarioName = activeScenarioId
    ? scenarios.find(s => s.id === activeScenarioId)?.name ?? 'Scenario'
    : 'Base'

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

  const { data: moduleData, isLoading } = useQuery({
    queryKey: ['assumptions', projectId, currentModule, activeScenarioId],
    queryFn: () => assumptionsApi.getModule(projectId, currentModule, activeScenarioId).then(r => r.data),
    enabled: !!currentModule,
  })

  // Fetch historical data to show inline context in the configurator
  const { data: historicalData } = useQuery({
    queryKey: ['historical', projectId],
    queryFn: () => historicalApi.getData(projectId).then(r => r.data),
    staleTime: 60000,
  })

  // When editing an override scenario, route the live recompute to that
  // scenario's runner so the user sees their override take effect (otherwise
  // we'd silently re-project the base case and the badge would lie).
  const runMutation = useMutation({
    mutationFn: () =>
      activeScenarioId
        ? scenariosApi.run(projectId, activeScenarioId)
        : projectionsApi.run(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projections', projectId] }),
    onError: () => toast.error('Live projection update failed'),
  })

  const saveMutation = useMutation({
    mutationFn: (data: AssumptionItem[]) =>
      assumptionsApi.saveModule(projectId, currentModule, data, activeScenarioId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assumptions', projectId] })
      qc.invalidateQueries({ queryKey: ['module-status', projectId] })
      toast.success(`${currentModuleMeta?.label} saved to ${activeScenarioName}`)
      runMutation.mutate()
    },
    onError: () => toast.error('Failed to save assumptions'),
  })

  const isPending = saveMutation.isPending || runMutation.isPending

  if (!activeModule) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500">Select a module from the sidebar to configure assumptions.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">{currentModuleMeta?.label}</h2>
          <p className="text-sm text-gray-500 mt-1">Configure how this line item will be projected.</p>
        </div>
        <span
          className={`text-xs px-2 py-1 rounded-full font-medium border ${
            activeScenarioId
              ? 'bg-amber-50 text-amber-700 border-amber-200'
              : 'bg-gray-50 text-gray-600 border-gray-200'
          }`}
          title={activeScenarioId ? 'Editing override scenario' : 'Editing base scenario'}
        >
          {activeScenarioId ? '🎭 ' : '🏠 '}
          {activeScenarioName}
        </span>
      </div>

      {isLoading ? (
        <div className="card"><p className="text-gray-500">Loading...</p></div>
      ) : (
        <ModuleConfigurator
          key={currentModule}
          module={currentModule}
          initialData={moduleData || []}
          projectionYears={projectionYears}
          historicalData={historicalData}
          onSave={(data) => saveMutation.mutate(data)}
          isSaving={isPending}
        />
      )}
    </div>
  )
}
