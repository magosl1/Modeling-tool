import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { scenariosApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Scenario {
  id: string
  project_id: string
  name: string
  description?: string
  is_base: boolean
  created_at: string
}

interface Props {
  projectId: string
  activeScenarioId: string | null
  onScenarioChange: (id: string | null) => void
}

export default function ScenarioManager({ projectId, activeScenarioId, onScenarioChange }: Props) {
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [cloneFrom, setCloneFrom] = useState<string | undefined>(undefined)
  const qc = useQueryClient()

  const { data: scenarios = [] } = useQuery<Scenario[]>({
    queryKey: ['scenarios', projectId],
    queryFn: () => scenariosApi.list(projectId).then(r => r.data),
  })

  const createMutation = useMutation({
    mutationFn: () => scenariosApi.create(projectId, {
      name: newName,
      description: newDesc || undefined,
      clone_from_id: cloneFrom,
    }),
    onSuccess: (res) => {
      toast.success(`Scenario "${res.data.name}" created`)
      qc.invalidateQueries({ queryKey: ['scenarios', projectId] })
      setShowCreate(false)
      setNewName('')
      setNewDesc('')
      setCloneFrom(undefined)
    },
    onError: () => toast.error('Failed to create scenario'),
  })

  const deleteMutation = useMutation({
    mutationFn: (scenarioId: string) => scenariosApi.delete(projectId, scenarioId),
    onSuccess: (_, deletedId) => {
      toast.success('Scenario deleted')
      qc.invalidateQueries({ queryKey: ['scenarios', projectId] })
      if (activeScenarioId === deletedId) onScenarioChange(null)
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Cannot delete this scenario'),
  })

  const runMutation = useMutation({
    mutationFn: (scenarioId: string) => scenariosApi.run(projectId, scenarioId),
    onSuccess: (data, scenarioId) => {
      toast.success('Scenario projected!')
      if (data.data.warnings?.length) data.data.warnings.forEach((w: string) => toast(w, { icon: '⚠️' }))
      qc.invalidateQueries({ queryKey: ['scenario-projections', projectId, scenarioId] })
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      if (detail?.error?.details) toast.error(detail.error.details.join('\n').slice(0, 200))
      else toast.error('Projection run failed')
    },
  })

  const baseScenario = scenarios.find(s => s.is_base)
  const otherScenarios = scenarios.filter(s => !s.is_base)

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm mb-6">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-700">🎭 Scenarios</span>
          <span className="text-xs text-gray-400">
            {scenarios.length === 0 ? 'No scenarios yet' : `${scenarios.length} scenario${scenarios.length > 1 ? 's' : ''}`}
          </span>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="text-xs px-3 py-1 bg-primary-50 text-primary-700 rounded hover:bg-primary-100 transition-colors font-medium"
        >
          + New Scenario
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 space-y-2">
          <div className="flex gap-2">
            <input
              className="flex-1 text-sm border border-gray-300 rounded px-2 py-1"
              placeholder="Scenario name (e.g. Upside)"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              id="scenario-name-input"
            />
            <input
              className="flex-1 text-sm border border-gray-300 rounded px-2 py-1"
              placeholder="Description (optional)"
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
              id="scenario-desc-input"
            />
          </div>
          {scenarios.length > 0 && (
            <select
              className="w-full text-sm border border-gray-300 rounded px-2 py-1"
              value={cloneFrom || ''}
              onChange={e => setCloneFrom(e.target.value || undefined)}
              id="scenario-clone-select"
            >
              <option value="">Clone from: Base (default)</option>
              {scenarios.filter(s => !s.is_base).map(s => (
                <option key={s.id} value={s.id}>Clone from: {s.name}</option>
              ))}
            </select>
          )}
          <div className="flex gap-2">
            <button
              disabled={!newName.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
              className="text-xs px-3 py-1 bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
              id="scenario-create-btn"
            >
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="text-xs px-3 py-1 text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Scenario pills */}
      <div className="px-4 py-3 flex flex-wrap gap-2">
        {/* Base pill */}
        {baseScenario ? (
          <ScenarioPill
            scenario={baseScenario}
            isActive={activeScenarioId === baseScenario.id}
            onSelect={() => onScenarioChange(baseScenario.id)}
            onRun={() => runMutation.mutate(baseScenario.id)}
            isRunning={runMutation.isPending && runMutation.variables === baseScenario.id}
          />
        ) : (
          <span className="text-xs text-gray-400 italic">No base scenario — run projections to auto-create</span>
        )}

        {/* Non-base scenarios */}
        {otherScenarios.map(s => (
          <ScenarioPill
            key={s.id}
            scenario={s}
            isActive={activeScenarioId === s.id}
            onSelect={() => onScenarioChange(s.id)}
            onRun={() => runMutation.mutate(s.id)}
            onDelete={() => {
              if (confirm(`Delete scenario "${s.name}"?`)) deleteMutation.mutate(s.id)
            }}
            isRunning={runMutation.isPending && runMutation.variables === s.id}
          />
        ))}
      </div>
    </div>
  )
}

function ScenarioPill({
  scenario, isActive, onSelect, onRun, onDelete, isRunning,
}: {
  scenario: Scenario
  isActive: boolean
  onSelect: () => void
  onRun: () => void
  onDelete?: () => void
  isRunning: boolean
}) {
  return (
    <div
      className={`flex items-center gap-1 rounded-full pl-3 pr-1 py-1 text-xs border transition-all cursor-pointer
        ${isActive
          ? 'bg-primary-600 text-white border-primary-600'
          : 'bg-white text-gray-700 border-gray-300 hover:border-primary-400'
        }`}
      onClick={onSelect}
    >
      {scenario.is_base && <span className="mr-0.5">🏠</span>}
      <span className="font-medium">{scenario.name}</span>
      <button
        onClick={e => { e.stopPropagation(); onRun() }}
        className={`ml-1 p-0.5 rounded-full hover:opacity-70 ${isActive ? 'text-white' : 'text-primary-700'}`}
        title="Run projections for this scenario"
        id={`scenario-run-${scenario.id}`}
      >
        {isRunning ? '⏳' : '▶'}
      </button>
      {onDelete && (
        <button
          onClick={e => { e.stopPropagation(); onDelete() }}
          className={`p-0.5 rounded-full hover:opacity-70 ${isActive ? 'text-white' : 'text-red-500'}`}
          title="Delete scenario"
          id={`scenario-delete-${scenario.id}`}
        >
          ×
        </button>
      )}
    </div>
  )
}
