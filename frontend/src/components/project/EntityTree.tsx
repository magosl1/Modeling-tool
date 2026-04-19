/**
 * EntityTree — Left sidebar showing all entities in a project hierarchy.
 * Supports single_entity (collapses to one item) and multi_entity projects.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import clsx from 'clsx'
import { entitiesApi } from '../../services/api'
import type { Entity, EntityCreate, EntityType } from '../../types/api'

// ── Icons / labels ───────────────────────────────────────────────────────────

const ENTITY_ICON: Record<EntityType, string> = {
  company_listed: '📈',
  company_private: '🏢',
  project: '🏭',
  division: '🗂️',
  asset: '🏗️',
  holdco: '🏦',
}

const ENTITY_LABEL: Record<EntityType, string> = {
  company_listed: 'Listed Co.',
  company_private: 'Private Co.',
  project: 'Project',
  division: 'Division',
  asset: 'Asset',
  holdco: 'HoldCo',
}

// ── Build tree from flat list ─────────────────────────────────────────────────

interface TreeNode {
  entity: Entity
  children: TreeNode[]
}

function buildTree(entities: Entity[]): TreeNode[] {
  const map = new Map<string, TreeNode>()
  entities.forEach(e => map.set(e.id, { entity: e, children: [] }))

  const roots: TreeNode[] = []
  entities.forEach(e => {
    if (e.parent_entity_id && map.has(e.parent_entity_id)) {
      map.get(e.parent_entity_id)!.children.push(map.get(e.id)!)
    } else {
      roots.push(map.get(e.id)!)
    }
  })
  return roots
}

// ── EntityNode ────────────────────────────────────────────────────────────────

function EntityNode({
  node,
  projectId,
  activeEntityId,
  depth = 0,
}: {
  node: TreeNode
  projectId: string
  activeEntityId: string | null
  depth?: number
}) {
  const [expanded, setExpanded] = useState(true)
  const navigate = useNavigate()
  const e = node.entity
  const isActive = e.id === activeEntityId
  const hasChildren = node.children.length > 0

  return (
    <div>
      <button
        onClick={() => navigate(`/projects/${projectId}/entities/${e.id}`)}
        className={clsx(
          'w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm transition-colors text-left',
          isActive
            ? 'bg-primary-50 text-primary-700 font-medium'
            : 'text-gray-600 hover:bg-gray-100',
        )}
        style={{ paddingLeft: `${8 + depth * 16}px` }}
      >
        {hasChildren && (
          <span
            className="text-xs text-gray-400 hover:text-gray-600 mr-0.5"
            onClick={ev => { ev.stopPropagation(); setExpanded(v => !v) }}
          >
            {expanded ? '▾' : '▸'}
          </span>
        )}
        {!hasChildren && <span className="w-3.5" />}
        <span className="shrink-0">{ENTITY_ICON[e.entity_type]}</span>
        <span className="truncate flex-1">{e.name}</span>
        {e.ownership_pct < 100 && (
          <span className="text-xs text-gray-400 shrink-0">{e.ownership_pct}%</span>
        )}
      </button>

      {expanded && hasChildren && (
        <div>
          {node.children.map(child => (
            <EntityNode
              key={child.entity.id}
              node={child}
              projectId={projectId}
              activeEntityId={activeEntityId}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── AddEntityModal ────────────────────────────────────────────────────────────

function AddEntityModal({
  projectId,
  onClose,
}: {
  projectId: string
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<EntityCreate>({
    name: '',
    entity_type: 'company_private',
    currency: 'EUR',
    ownership_pct: 100,
    consolidation_method: 'full',
  })

  const { mutate, isPending } = useMutation({
    mutationFn: (data: EntityCreate) => entitiesApi.create(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entities', projectId] })
      toast.success('Entity created')
      onClose()
    },
    onError: () => toast.error('Failed to create entity'),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">Add Entity</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              className="input w-full"
              placeholder="e.g. Planta Biogás Badajoz"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <select
              className="input w-full"
              value={form.entity_type}
              onChange={e => setForm(f => ({ ...f, entity_type: e.target.value as EntityType }))}
            >
              {(Object.keys(ENTITY_LABEL) as EntityType[]).map(t => (
                <option key={t} value={t}>{ENTITY_ICON[t]} {ENTITY_LABEL[t]}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
              <input
                className="input w-full"
                placeholder="EUR"
                maxLength={10}
                value={form.currency}
                onChange={e => setForm(f => ({ ...f, currency: e.target.value.toUpperCase() }))}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ownership %</label>
              <input
                className="input w-full"
                type="number"
                min={0}
                max={100}
                value={form.ownership_pct}
                onChange={e => setForm(f => ({ ...f, ownership_pct: parseFloat(e.target.value) }))}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Consolidation</label>
            <select
              className="input w-full"
              value={form.consolidation_method}
              onChange={e => setForm(f => ({ ...f, consolidation_method: e.target.value as 'full' | 'proportional' | 'equity_method' | 'none' }))}
            >
              <option value="full">Full (line-by-line)</option>
              <option value="proportional">Proportional (ownership × each line)</option>
              <option value="equity_method">Equity Method (net income × ownership only)</option>
              <option value="none">None (excluded)</option>
            </select>
          </div>

          {form.entity_type === 'company_listed' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ticker</label>
              <input
                className="input w-full"
                placeholder="e.g. ENCE.MC"
                value={form.ticker ?? ''}
                onChange={e => setForm(f => ({ ...f, ticker: e.target.value }))}
              />
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            disabled={isPending || !form.name.trim()}
            onClick={() => mutate(form)}
          >
            {isPending ? 'Creating…' : 'Create Entity'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── EntityTree (main export) ──────────────────────────────────────────────────

interface EntityTreeProps {
  projectId: string
  projectType: string
  activeEntityId: string | null
}

export default function EntityTree({ projectId, projectType, activeEntityId }: EntityTreeProps) {
  const navigate = useNavigate()
  const [showAddModal, setShowAddModal] = useState(false)

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['entities', projectId],
    queryFn: () => entitiesApi.list(projectId).then(r => r.data),
  })

  const tree = buildTree(entities)
  const isMulti = projectType !== 'single_entity'

  if (isLoading) return <div className="p-3 text-sm text-gray-400">Loading…</div>

  return (
    <aside className="w-52 shrink-0 flex flex-col">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          {isMulti ? 'Entities' : 'Entity'}
        </h3>
        {isMulti && (
          <button
            className="text-primary-600 hover:text-primary-800 text-xs font-medium"
            onClick={() => setShowAddModal(true)}
          >
            + Add
          </button>
        )}
      </div>

      <nav className="space-y-0.5">
        {tree.map(node => (
          <EntityNode
            key={node.entity.id}
            node={node}
            projectId={projectId}
            activeEntityId={activeEntityId}
          />
        ))}
      </nav>

      {isMulti && entities.length > 1 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <button
            onClick={() => navigate(`/projects/${projectId}/consolidated`)}
            className={clsx(
              'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors',
              !activeEntityId
                ? 'bg-primary-50 text-primary-700 font-medium'
                : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            <span>📊</span>
            <span>Consolidated View</span>
          </button>
        </div>
      )}

      {showAddModal && (
        <AddEntityModal projectId={projectId} onClose={() => setShowAddModal(false)} />
      )}
    </aside>
  )
}
