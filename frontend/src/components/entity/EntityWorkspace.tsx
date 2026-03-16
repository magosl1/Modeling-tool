/**
 * EntityWorkspace — Main working area for a single entity.
 * Tabs: Overview | Historical Data | Assumptions | Projections | Valuation
 *
 * For single_entity projects this replaces the old ProjectWorkspace behavior.
 * For multi_entity projects this is shown when an entity is selected in EntityTree.
 */
import React, { useState } from 'react'
import { NavLink, Routes, Route } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import clsx from 'clsx'
import { entitiesApi, assumptionsApi } from '../../services/api'
import type { Entity, ModuleStatus } from '../../types/api'
import UploadHistorical from '../project/UploadHistorical'
import AssumptionsPanel from '../modules/AssumptionsPanel'
import ProjectionsView from '../projections/ProjectionsView'
import ValuationView from '../valuation/ValuationView'
import LiveProjectionsView from '../projections/LiveProjectionsView'

// ── Module status helpers (reused from ProjectWorkspace) ──────────────────────

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

// ── EntityOverview ────────────────────────────────────────────────────────────

function EntityOverview({ entity, onUpdate }: { entity: Entity; onUpdate: () => void }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(entity.name)
  const [description, setDescription] = useState(entity.description ?? '')
  const queryClient = useQueryClient()

  const { mutate, isPending } = useMutation({
    mutationFn: () => entitiesApi.update(entity.id, { name, description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', entity.project_id] })
      toast.success('Saved')
      setEditing(false)
      onUpdate()
    },
    onError: () => toast.error('Save failed'),
  })

  return (
    <div className="card space-y-4">
      <div className="flex items-start justify-between">
        <div>
          {editing ? (
            <input
              className="input text-lg font-semibold w-80"
              value={name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
            />
          ) : (
            <h2 className="text-xl font-semibold text-gray-900">{entity.name}</h2>
          )}
          <p className="text-sm text-gray-500 mt-1">
            {entity.entity_type.replace('_', ' ')} · {entity.currency}
            {entity.country ? ` · ${entity.country}` : ''}
            {entity.sector ? ` · ${entity.sector}` : ''}
          </p>
        </div>
        <div className="flex gap-2">
          {editing ? (
            <>
              <button className="btn btn-secondary btn-sm" onClick={() => setEditing(false)}>Cancel</button>
              <button className="btn btn-primary btn-sm" onClick={() => mutate()} disabled={isPending}>Save</button>
            </>
          ) : (
            <button className="btn btn-secondary btn-sm" onClick={() => setEditing(true)}>Edit</button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500">Ownership</p>
          <p className="text-lg font-semibold text-gray-900">{entity.ownership_pct}%</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500">Consolidation</p>
          <p className="text-sm font-medium text-gray-900 capitalize">{entity.consolidation_method.replace('_', ' ')}</p>
        </div>
        {entity.ticker && (
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500">Ticker</p>
            <p className="text-lg font-semibold text-gray-900">{entity.ticker}</p>
          </div>
        )}
        {entity.start_date && (
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500">Start Date</p>
            <p className="text-sm font-medium text-gray-900">{entity.start_date}</p>
          </div>
        )}
      </div>

      {editing && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea
            className="input w-full h-24 resize-none"
            value={description}
            onChange={e => setDescription(e.target.value)}
          />
        </div>
      )}
      {!editing && entity.description && (
        <p className="text-sm text-gray-600">{entity.description}</p>
      )}
    </div>
  )
}

// ── EntityWorkspace ───────────────────────────────────────────────────────────

interface EntityWorkspaceProps {
  entityId: string
  /** The parent project object (for currency/scale context) */
  project: {
    id: string
    currency: string
    scale: string
    fiscal_year_end: string | null
    projection_years: number
    status: string
  }
}

export default function EntityWorkspace({ entityId, project }: EntityWorkspaceProps) {
  const { data: entity, isLoading, refetch } = useQuery({
    queryKey: ['entity', entityId],
    queryFn: () => entitiesApi.get(entityId).then(r => r.data),
  })

  // Module status — reuse project-level endpoint with project_id (entity shares project)
  const { data: moduleStatuses = [] } = useQuery({
    queryKey: ['module-status', project.id],
    queryFn: () => assumptionsApi.getModuleStatus(project.id).then(r => r.data),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })

  const statusMap = Object.fromEntries(moduleStatuses.map((s: ModuleStatus) => [s.module, s.status]))
  const allComplete = MODULES.every(m => statusMap[m.key] === 'complete')

  if (isLoading) return <div className="p-6 text-gray-400">Loading entity…</div>
  if (!entity) return <div className="p-6 text-red-500">Entity not found</div>

  const basePath = `/projects/${project.id}/entities/${entityId}`

  const tabs = [
    { to: basePath, label: 'Overview', end: true },
    { to: `${basePath}/historical`, label: 'Historical Data' },
    { to: `${basePath}/assumptions`, label: 'Assumptions' },
    { to: `${basePath}/projections`, label: 'Projections' },
    { to: `${basePath}/valuation`, label: 'Valuation' },
  ]

  const isAssumptionsRoute = location.pathname.includes('/assumptions')

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Entity tabs */}
      <div className="border-b border-gray-200 bg-white flex gap-1 px-4">
        {tabs.map(tab => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) => clsx(
              'px-3 py-2 text-sm font-medium border-b-2 transition-colors',
              isActive
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            )}
          >
            {tab.label}
          </NavLink>
        ))}
      </div>

      <div className={clsx(
        'flex flex-1 px-4 py-4 gap-4 min-h-0',
      )}>
        {/* Left sidebar: module nav (assumptions only) */}
        {isAssumptionsRoute && (
          <aside className="w-44 shrink-0">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Modules</h3>
            <nav className="space-y-0.5">
              {MODULES.map(m => (
                <NavLink
                  key={m.key}
                  to={`${basePath}/assumptions/${m.key}`}
                  className={({ isActive }) => clsx(
                    'flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors',
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

        {/* Main content */}
        <main className="flex-1 min-w-0 overflow-auto">
          <Routes>
            <Route
              index
              element={<EntityOverview entity={entity} onUpdate={refetch} />}
            />
            <Route
              path="historical"
              element={
                <UploadHistorical
                  projectId={project.id}
                  project={project as Parameters<typeof UploadHistorical>[0]['project']}
                />
              }
            />
            <Route path="assumptions" element={<AssumptionsPanel projectId={project.id} />} />
            <Route path="assumptions/:module" element={<AssumptionsPanel projectId={project.id} />} />
            <Route
              path="projections"
              element={
                <ProjectionsView
                  projectId={project.id}
                  allModulesComplete={allComplete}
                  project={project as Parameters<typeof ProjectionsView>[0]['project']}
                />
              }
            />
            <Route path="valuation" element={<ValuationView projectId={project.id} />} />
          </Routes>
        </main>

        {/* Right sidebar: live projections (assumptions only) */}
        {isAssumptionsRoute && (
          <div className="w-[420px] shrink-0">
            <LiveProjectionsView projectId={project.id} module="all" />
          </div>
        )}
      </div>
    </div>
  )
}
