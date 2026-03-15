import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { assumptionsApi, projectionsApi, projectsApi, historicalApi } from '../../services/api'
import type { AssumptionItem } from '../../types/api'
import toast from 'react-hot-toast'
import ModuleConfigurator from './ModuleConfigurator'

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

  const currentModule = activeModule || MODULES[0].key
  const currentModuleMeta = MODULES.find(m => m.key === currentModule)

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
    queryKey: ['assumptions', projectId, currentModule],
    queryFn: () => assumptionsApi.getModule(projectId, currentModule).then(r => r.data),
    enabled: !!currentModule,
  })

  // Fetch historical data to show inline context in the configurator
  const { data: historicalData } = useQuery({
    queryKey: ['historical', projectId],
    queryFn: () => historicalApi.getData(projectId).then(r => r.data),
    staleTime: 60000,
  })

  const runMutation = useMutation({
    mutationFn: () => projectionsApi.run(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projections', projectId] }),
    onError: () => toast.error('Live projection update failed'),
  })

  const saveMutation = useMutation({
    mutationFn: (data: AssumptionItem[]) => assumptionsApi.saveModule(projectId, currentModule, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assumptions', projectId] })
      qc.invalidateQueries({ queryKey: ['module-status', projectId] })
      toast.success(`${currentModuleMeta?.label} assumptions saved`)
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
      <div>
        <h2 className="text-xl font-semibold text-gray-900">{currentModuleMeta?.label}</h2>
        <p className="text-sm text-gray-500 mt-1">Configure how this line item will be projected.</p>
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
