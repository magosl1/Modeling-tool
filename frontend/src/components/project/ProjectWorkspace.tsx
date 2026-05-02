/**
 * ProjectWorkspace — Top-level project container.
 *
 * Single-entity projects: shows legacy single-entity UI (backward compatible).
 * Multi-entity projects: shows EntityTree sidebar + EntityWorkspace per entity.
 *
 * Routing:
 *   /projects/:id                       → project root (defaults to first entity)
 *   /projects/:id/entities/:entityId/*  → entity workspace
 *   /projects/:id/consolidated          → consolidated view (Phase 3)
 *   /projects/:id/assumptions/*         → legacy single-entity assumptions
 *   etc. (all legacy routes preserved)
 */
import { useEffect, useState } from 'react'
import { Routes, Route, NavLink, useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { projectsApi, assumptionsApi, entitiesApi } from '../../services/api'
import type { ModuleStatus } from '../../types/api'
import UploadHistorical from './UploadHistorical'
import UploadHistoricalAI from './UploadHistoricalAI'
import ProjectDashboard from './ProjectDashboard'
import AssumptionsPanel from '../modules/AssumptionsPanel'
import ProjectionsView from '../projections/ProjectionsView'
import ValuationView from '../valuation/ValuationView'
import LiveProjectionsView from '../projections/LiveProjectionsView'
import DebtSchedulePanel from './DebtSchedulePanel'
import FXRatesPanel from './FXRatesPanel'
import IndexCurvePanel from './IndexCurvePanel'
import SharePanel from './SharePanel'
import EntityTree from './EntityTree'
import EntityWorkspace from '../entity/EntityWorkspace'
import ConsolidatedView from '../consolidation/ConsolidatedView'
import AuditTimeline from './AuditTimeline'

// ── Module status helpers ─────────────────────────────────────────────────────

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

// ── ProjectWorkspace ──────────────────────────────────────────────────────────

export default function ProjectWorkspace() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const [uploadMode, setUploadMode] = useState<'ai' | 'manual'>('ai')

  const isAssumptionsRoute = location.pathname.includes('/assumptions')

  // Detect active entity from URL: /projects/:id/entities/:entityId
  const entityMatch = location.pathname.match(/\/entities\/([^/]+)/)
  const activeEntityId = entityMatch ? entityMatch[1] : null

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => projectsApi.get(id!).then(r => r.data),
  })

  const { data: entities = [] } = useQuery({
    queryKey: ['entities', id],
    queryFn: () => entitiesApi.list(id!).then(r => r.data),
    enabled: !!id,
  })

  const { data: moduleStatuses = [] } = useQuery({
    queryKey: ['module-status', id],
    queryFn: () => assumptionsApi.getModuleStatus(id!).then(r => r.data),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })

  const statusMap = Object.fromEntries(moduleStatuses.map((s: ModuleStatus) => [s.module, s.status]))
  const allComplete = MODULES.every(m => statusMap[m.key] === 'complete')

  // For single_entity projects: auto-navigate to the first entity workspace when at root
  useEffect(() => {
    if (!project || !entities.length) return
    const isProjectRoot = location.pathname === `/projects/${id}` || location.pathname === `/projects/${id}/`
    if (project.project_type === 'single_entity' && isProjectRoot && entities.length > 0) {
      navigate(`/projects/${id}/entities/${entities[0].id}`, { replace: true })
    }
  }, [project, entities, location.pathname, id, navigate])

  if (isLoading) return <div className="p-8 text-gray-500">Loading…</div>
  if (!project) return <div className="p-8 text-red-500">Project not found</div>

  const isMultiEntity = project.project_type !== 'single_entity'

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top Bar */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-[1800px] mx-auto px-6 py-3 flex items-center gap-4">
          <button onClick={() => navigate('/')} className="text-gray-400 hover:text-gray-600 text-sm">
            ← Dashboard
          </button>
          <h1 className="text-lg font-semibold text-gray-900">{project.name}</h1>
          <span className="text-sm text-gray-400">{project.currency} · {project.scale}</span>
          {isMultiEntity && (
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
              {project.project_type === 'project_finance' ? 'Project Finance' : 'Multi-Entity'}
            </span>
          )}
        </div>

        {/* Top-level tabs (for legacy single-entity or multi-entity project level) */}
        {!isMultiEntity && (
          <div className="max-w-[1800px] mx-auto px-6 flex gap-1 border-t border-gray-100">
            {[
              { to: '', label: '🚀 Dashboard' },
              { to: 'historical', label: 'Historical Data' },
              { to: 'assumptions', label: 'Assumptions' },
              { to: 'projections', label: 'Projections' },
              { to: 'valuation', label: 'Valuation' },
              { to: 'activity', label: '🕐 Activity' },
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
        )}

        {/* Multi-entity project-level tabs */}
        {isMultiEntity && (
          <div className="max-w-[1800px] mx-auto px-6 flex gap-1 border-t border-gray-100">
            {[
              { to: `/projects/${id}`, label: 'Entities', end: true },
              { to: `/projects/${id}/consolidated`, label: '📊 Consolidated', end: false },
              { to: `/projects/${id}/share`, label: '👥 Share', end: false },
            ].map(tab => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.end}
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
        )}
      </header>

      {/* Main content area */}
      <div className="flex flex-1 max-w-[1800px] mx-auto w-full px-6 py-6 gap-6 overflow-hidden">

        {/* Entity tree sidebar (always shown) */}
        <EntityTree
          projectId={id!}
          projectType={project.project_type}
          activeEntityId={activeEntityId}
        />

        {/* Right side: entity workspace or legacy single-entity content */}
        <div className="flex-1 flex flex-col min-w-0">

          <Routes>
            {/* Entity-level workspace */}
            <Route
              path="entities/:entityId/*"
              element={
                <EntityWorkspaceRoute project={project} />
              }
            />

            {/* Consolidated view (Phase 3) */}
            <Route
              path="consolidated"
              element={<ConsolidatedView projectId={id!} entities={entities} />}
            />

            {/* Share panel */}
            <Route
              path="share"
              element={<div className="card"><SharePanel projectId={id!} /></div>}
            />

            <Route
              index
              element={
                isMultiEntity ? (
                  <div className="card p-8 text-center text-gray-500">
                    <p className="text-2xl mb-2">🏗️</p>
                    <p className="font-medium">Select an entity from the sidebar</p>
                    <p className="text-sm mt-1">or click the Consolidated View to see group financials</p>
                  </div>
                ) : (
                  <ProjectDashboard projectId={id!} project={project} />
                )
              }
            />
            <Route
              path="historical"
              element={
                <div className="flex flex-col gap-6">
                  <div className="flex bg-gray-100 p-1 rounded-lg w-fit">
                    <button
                      onClick={() => setUploadMode('ai')}
                      className={clsx(
                        "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                        uploadMode === 'ai' ? "bg-white text-indigo-600 shadow-sm" : "text-gray-500 hover:text-gray-700"
                      )}
                    >
                      ✨ AI Ingestion
                    </button>
                    <button
                      onClick={() => setUploadMode('manual')}
                      className={clsx(
                        "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                        uploadMode === 'manual' ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                      )}
                    >
                      Template (Manual)
                    </button>
                  </div>
                  {uploadMode === 'ai' ? (
                    <UploadHistoricalAI projectId={id!} project={project} />
                  ) : (
                    <UploadHistorical projectId={id!} project={project} />
                  )}
                </div>
              }
            />

            {/* Legacy assumption routes (single_entity) */}
            <Route
              path="assumptions"
              element={
                <div className={clsx(isAssumptionsRoute && 'flex gap-6')}>
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
                    </aside>
                  )}
                  <AssumptionsPanel projectId={id!} />
                </div>
              }
            />
            <Route path="assumptions/structural_debt" element={<DebtSchedulePanel projectId={id!} />} />
            <Route path="assumptions/fx" element={<FXRatesPanel projectId={id!} />} />
            <Route path="assumptions/curves" element={<IndexCurvePanel projectId={id!} />} />
            <Route path="assumptions/:module" element={
              <div className="flex gap-6">
                <aside className="w-48 shrink-0 pb-8">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Core Modules</h3>
                  <nav className="space-y-1 mb-6">
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
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Advanced Setup</h3>
                  <nav className="space-y-1 bg-white rounded-lg border border-gray-200 p-2 shadow-sm">
                    <NavLink to={`/projects/${id}/assumptions/structural_debt`} className={({ isActive }) => clsx('flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors', isActive ? 'bg-primary-50 text-primary-700 font-medium' : 'text-gray-600 hover:bg-gray-100')}>
                      <span>🏦</span> Debt Schedule
                    </NavLink>
                    <NavLink to={`/projects/${id}/assumptions/fx`} className={({ isActive }) => clsx('flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors', isActive ? 'bg-primary-50 text-primary-700 font-medium' : 'text-gray-600 hover:bg-gray-100')}>
                      <span>💱</span> FX Rates
                    </NavLink>
                    <NavLink to={`/projects/${id}/assumptions/curves`} className={({ isActive }) => clsx('flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors', isActive ? 'bg-primary-50 text-primary-700 font-medium' : 'text-gray-600 hover:bg-gray-100')}>
                      <span>📈</span> External Curves
                    </NavLink>
                  </nav>
                  {allComplete && (
                    <div className="mt-4 p-3 bg-green-50 rounded-lg text-xs text-green-700">
                      All modules complete! You can run projections.
                    </div>
                  )}
                </aside>
                <div className="flex-1 min-w-0">
                  <AssumptionsPanel projectId={id!} />
                </div>
                <div className="w-[450px] shrink-0 xl:w-[550px]">
                  <LiveProjectionsView projectId={id!} module="all" />
                </div>
              </div>
            } />
            <Route path="projections" element={<ProjectionsView projectId={id!} allModulesComplete={allComplete} project={project} />} />
            <Route path="valuation" element={<ValuationView projectId={id!} />} />
            <Route
              path="activity"
              element={
                <div className="card flex flex-col min-h-[600px] overflow-hidden">
                  <div className="px-4 pt-4 pb-2 border-b border-gray-100">
                    <h2 className="text-sm font-semibold text-gray-800">Activity Log</h2>
                    <p className="text-xs text-gray-500 mt-0.5">Audit trail — who changed what and when</p>
                  </div>
                  <AuditTimeline projectId={id!} />
                </div>
              }
            />
          </Routes>
        </div>
      </div>
    </div>
  )
}

// ── EntityWorkspaceRoute — helper that picks entityId from URL ────────────────

function EntityWorkspaceRoute({ project }: { project: any }) {
  const { entityId } = useParams<{ entityId: string }>()
  if (!entityId || !project) return null
  return <EntityWorkspace entityId={entityId} project={project} />
}
