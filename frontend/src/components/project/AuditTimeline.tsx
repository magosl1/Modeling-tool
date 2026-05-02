import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { projectsApi } from '../../services/api'
import {
  ClockIcon,
  PlusCircleIcon,
  PencilSquareIcon,
  TrashIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline'

interface ChangeLogEntry {
  id: string
  user_email: string | null
  entity: string
  entity_id: string
  action: 'create' | 'update' | 'delete'
  summary: string | null
  before_json: Record<string, unknown> | null
  after_json: Record<string, unknown> | null
  created_at: string
}

interface Props {
  projectId: string
}

const ENTITY_FILTERS = [
  { label: 'All', value: '' },
  { label: 'Assumptions', value: 'assumption' },
  { label: 'Historical', value: 'historical' },
  { label: 'Scenarios', value: 'scenario' },
  { label: 'Valuation', value: 'valuation' },
]

const ACTION_CONFIG = {
  create: { icon: PlusCircleIcon, color: 'text-emerald-500', bg: 'bg-emerald-50', label: 'Created' },
  update: { icon: PencilSquareIcon, color: 'text-amber-500', bg: 'bg-amber-50', label: 'Updated' },
  delete: { icon: TrashIcon, color: 'text-red-500', bg: 'bg-red-50', label: 'Deleted' },
}

const ENTITY_BADGE: Record<string, string> = {
  assumption: 'bg-indigo-100 text-indigo-700',
  historical: 'bg-blue-100 text-blue-700',
  scenario: 'bg-purple-100 text-purple-700',
  valuation: 'bg-teal-100 text-teal-700',
}

function formatRelative(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `${diffD}d ago`
  return new Date(iso).toLocaleDateString()
}

function groupByDate(entries: ChangeLogEntry[]): [string, ChangeLogEntry[]][] {
  const groups: Record<string, ChangeLogEntry[]> = {}
  for (const e of entries) {
    const d = new Date(e.created_at)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    let label: string
    if (d.toDateString() === today.toDateString()) label = 'Today'
    else if (d.toDateString() === yesterday.toDateString()) label = 'Yesterday'
    else label = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

    if (!groups[label]) groups[label] = []
    groups[label].push(e)
  }
  return Object.entries(groups)
}

function DiffView({ before, after }: { before: Record<string, unknown> | null; after: Record<string, unknown> | null }) {
  const allKeys = new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])
  const changedKeys = [...allKeys].filter(k => {
    const bv = JSON.stringify((before ?? {})[k])
    const av = JSON.stringify((after ?? {})[k])
    return bv !== av && !['id', 'created_at'].includes(k)
  })
  if (!changedKeys.length) return <p className="text-xs text-gray-400 italic">No scalar changes recorded.</p>
  return (
    <div className="space-y-1">
      {changedKeys.map(k => (
        <div key={k} className="grid grid-cols-3 gap-1 text-xs">
          <span className="font-medium text-gray-600 truncate">{k}</span>
          <span className="text-red-500 bg-red-50 rounded px-1 truncate line-through">
            {String((before ?? {})[k] ?? '—')}
          </span>
          <span className="text-emerald-600 bg-emerald-50 rounded px-1 truncate">
            {String((after ?? {})[k] ?? '—')}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function AuditTimeline({ projectId }: Props) {
  const [activeFilter, setActiveFilter] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['changelog', projectId, activeFilter],
    queryFn: () =>
      projectsApi.getChangelog(projectId, { entity: activeFilter || undefined, limit: 100 })
        .then(r => r.data as ChangeLogEntry[]),
    refetchInterval: 30_000, // poll every 30s for multi-user freshness
  })

  const groups = groupByDate(entries)

  return (
    <div className="flex flex-col h-full">
      {/* Filter pills */}
      <div className="flex items-center gap-1 px-4 pt-4 pb-2 flex-wrap">
        <FunnelIcon className="w-3.5 h-3.5 text-gray-400 mr-1 shrink-0" />
        {ENTITY_FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setActiveFilter(f.value)}
            className={`px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors ${
              activeFilter === f.value
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Timeline */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
            <ClockIcon className="w-4 h-4 mr-2 animate-spin" />
            Loading activity…
          </div>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-gray-400 gap-2">
            <ClockIcon className="w-8 h-8 opacity-40" />
            <p className="text-sm">No activity recorded yet.</p>
            <p className="text-xs">Changes to assumptions, scenarios, and valuations will appear here.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {groups.map(([date, dayEntries]) => (
              <div key={date}>
                <div className="sticky top-0 bg-white/90 backdrop-blur-sm py-1 z-10">
                  <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">{date}</span>
                </div>
                <div className="relative ml-3 mt-2 space-y-3">
                  {/* Vertical line */}
                  <div className="absolute left-2.5 top-0 bottom-0 w-px bg-gray-100" />
                  {dayEntries.map(entry => {
                    const cfg = ACTION_CONFIG[entry.action] ?? ACTION_CONFIG.update
                    const Icon = cfg.icon
                    const isExpanded = expandedId === entry.id
                    const hasDiff = entry.before_json || entry.after_json

                    return (
                      <div key={entry.id} className="relative pl-8">
                        {/* Icon bubble */}
                        <div className={`absolute left-0 w-5 h-5 rounded-full ${cfg.bg} flex items-center justify-center ring-2 ring-white`}>
                          <Icon className={`w-3 h-3 ${cfg.color}`} />
                        </div>

                        <div className="bg-gray-50 hover:bg-gray-100 rounded-lg p-2.5 transition-colors">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${ENTITY_BADGE[entry.entity] ?? 'bg-gray-100 text-gray-600'}`}>
                                  {entry.entity}
                                </span>
                                <span className={`text-[10px] font-medium ${cfg.color}`}>{cfg.label}</span>
                              </div>
                              <p className="text-xs text-gray-700 mt-0.5 leading-snug">
                                {entry.summary ?? `${entry.entity} ${entry.action}d`}
                              </p>
                              {entry.user_email && (
                                <p className="text-[10px] text-gray-400 mt-0.5">{entry.user_email}</p>
                              )}
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-[10px] text-gray-400 whitespace-nowrap">{formatRelative(entry.created_at)}</span>
                              {hasDiff && (
                                <button
                                  onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                                  className="text-[10px] text-indigo-500 hover:text-indigo-700 underline"
                                >
                                  {isExpanded ? 'Hide' : 'Diff'}
                                </button>
                              )}
                            </div>
                          </div>

                          {isExpanded && hasDiff && (
                            <div className="mt-2 pt-2 border-t border-gray-200">
                              <DiffView before={entry.before_json} after={entry.after_json} />
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
