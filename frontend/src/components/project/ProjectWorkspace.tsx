import { Routes, Route, NavLink, useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { projectsApi, assumptionsApi } from '../../services/api'
import UploadHistorical from '../project/UploadHistorical'
import AssumptionsPanel from '../modules/AssumptionsPanel'
import ProjectionsView from '../projections/ProjectionsView'
import ValuationView from '../valuation/ValuationView'
import LiveProjectionsView from '../projections/LiveProjectionsView'
import clsx from 'clsx'

const STATUS_ICON: Record<string, string> = {
  not_started: '⬜',
  configured: '🟡',
  complete: '🟢',
  error: '🔴',
}

const MODULES = [
  { key: 'revenue', label: 'Revenue' },
  { key: 'cogs', label: 'COGS' },
  { key: 'opex', label: 'OpEx' },
  { key: 'da', label: 'D&A' },
  { key: 'working_capital', label: 'Working Capital' },
  { key: 'capex', label: 'Capex' },
  { key: 'debt', label: 'Debt & Financing' },
  { key: 'tax', label: 'Tax' },
  { key: 'dividends', label: 'Dividends' },
  { key: 'interest_income', label: 'Interest Income' },
  { key: 'non_operating', label: 'Non-Operating' },
]

export default function ProjectWorkspace() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const isAssumptionsRoute = location.pathname.includes('/assumptions')

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => projectsApi.get(id!).then(r => r.data),
  })

  const { data: moduleStatuses = [] } = useQuery({
    queryKey: ['module-status', id],
    queryFn: () => assumptionsApi.getModuleStatus(id!).then(r => r.data),
    refetchInterval: 5000,
  })

  const statusMap = Object.fromEntries(moduleStatuses.map((s: any) => [s.module, s.status]))
  const allComplete = MODULES.every(m => statusMap[m.key] === 'complete')

  if (isLoading) return <div className="p-8 text-gray-500">Loading...</div>
  if (!project) return <div className="p-8 text-red-500">Project not found</div>

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top Bar */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-4">
          <button onClick={() => navigate('/')} className="text-gray-400 hover:text-gray-600 text-sm">
            ← Dashboard
          </button>
          <h1 className="text-lg font-semibold text-gray-900">{project.name}</h1>
          <span className="text-sm text-gray-400">{project.currency} · {project.scale}</span>
        </div>
        {/* Tabs */}
        <div className="max-w-7xl mx-auto px-6 flex gap-1 border-t border-gray-100">
          {[
            { to: '', label: 'Historical Data' },
            { to: 'assumptions', label: 'Assumptions' },
            { to: 'projections', label: 'Projections' },
            { to: 'valuation', label: 'Valuation' },
          ].map(tab => (
            <NavLink
              key={tab.to}
              to={tab.to === '' ? `/projects/${id}` : `/projects/${id}/${tab.to}`}
              end={tab.to === ''}
              className={({ isActive }) => clsx(
                'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors',
                isActive
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              {tab.label}
            </NavLink>
          ))}
        </div>
      </header>

      <div className={clsx(
        'flex flex-1 mx-auto w-full px-6 py-6 gap-6',
        isAssumptionsRoute ? 'max-w-[1600px]' : 'max-w-7xl'
      )}>
        {/* Left sidebar: module status (only on assumptions route) */}
        {isAssumptionsRoute && (
          <aside className="w-48 shrink-0">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Modules</h3>
            <nav className="space-y-1">
              {MODULES.map(m => (
                <NavLink
                  key={m.key}
                  to={`/projects/${id}/assumptions/${m.key}`}
                  className={({ isActive }) => clsx(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                    isActive ? 'bg-primary-50 text-primary-700 font-medium' : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <span>{STATUS_ICON[statusMap[m.key] || 'not_started']}</span>
                  {m.label}
                </NavLink>
              ))}
            </nav>
            {allComplete && (
              <div className="mt-4 p-3 bg-green-50 rounded-lg text-xs text-green-700">
                All modules complete! You can run projections.
              </div>
            )}
          </aside>
        )}

        {/* Main content */}
        <main className="flex-1 min-w-0">
          <Routes>
            <Route index element={<UploadHistorical projectId={id!} project={project} />} />
            <Route path="assumptions" element={<AssumptionsPanel projectId={id!} />} />
            <Route path="assumptions/:module" element={<AssumptionsPanel projectId={id!} />} />
            <Route path="projections" element={<ProjectionsView projectId={id!} allModulesComplete={allComplete} />} />
            <Route path="valuation" element={<ValuationView projectId={id!} />} />
          </Routes>
        </main>

        {/* Right sidebar: Live projections (only on assumptions route) */}
        {isAssumptionsRoute && (
          <div className="w-[450px] shrink-0 xl:w-[550px]">
            <LiveProjectionsView projectId={id!} module="all" />
          </div>
        )}
      </div>
    </div>
  )
}
