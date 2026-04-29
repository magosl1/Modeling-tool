import { useCallback, useMemo, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  DocumentIcon,
  SparklesIcon,
  XMarkIcon,
  TableCellsIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'

import { entitiesApi, historicalApi } from '../../services/api'
import { ALL_CANONICAL, statementOf, type CanonicalStatement } from '../../lib/canonicalItems'
import type { Project, AIIngestionResponse, HistoricalResponse } from '../../types/api'

interface Props {
  projectId: string
  project: Project
  entityId?: string
  onComplete?: () => void
}

type Mapping = AIIngestionResponse['mappings'][number]

/** Dropdown choices: every canonical line + the IGNORE sentinel. */
const TARGET_OPTIONS: Array<{ value: string; label: string; group: string }> = [
  { value: 'IGNORE', label: 'IGNORE — drop this row', group: 'Ignore' },
  ...ALL_CANONICAL.map((c) => ({
    value: c.name,
    label: c.name,
    group: c.stmt,
  })),
]

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  let cls = 'bg-green-50 text-green-700 border-green-200'
  if (pct < 70) cls = 'bg-red-50 text-red-700 border-red-200'
  else if (pct < 85) cls = 'bg-amber-50 text-amber-700 border-amber-200'
  return (
    <span className={`inline-flex text-[10px] font-medium px-1.5 py-0.5 rounded border ${cls} tabular-nums`}>
      {pct}%
    </span>
  )
}

function applyOverrides(
  base: AIIngestionResponse['parsed'],
  baseMappings: Mapping[],
  overrides: Record<number, string>,
): AIIngestionResponse['parsed'] {
  // Build a fresh parsed structure where mapping decisions reflect the
  // current user-edited overrides. Only line items that the AI already
  // produced numeric values for can be moved (we don't re-run extraction
  // client-side — values come from `base`).
  const result: AIIngestionResponse['parsed'] = { PNL: {}, BS: {}, CF: {} }

  const valuesByOriginal: Record<string, Record<string, number>> = {}
  for (const stmtKey of ['PNL', 'BS', 'CF'] as CanonicalStatement[]) {
    for (const [item, years] of Object.entries(base[stmtKey] || {})) {
      valuesByOriginal[item] = years
    }
  }

  baseMappings.forEach((m, idx) => {
    const target = overrides[idx] ?? m.mapped_to
    if (!target || target === 'IGNORE') return
    const stmt = statementOf(target)
    if (!stmt) return
    // Find the values this row contributed to in the original parsed output.
    // The applier keys parsed by the *original* canonical name, so for moved
    // rows we have to look up by the original mapped_to (if it exists).
    const sourceKey = m.mapped_to !== 'IGNORE' && valuesByOriginal[m.mapped_to]
      ? m.mapped_to
      : null
    if (!sourceKey) return
    const years = valuesByOriginal[sourceKey]
    if (!years) return
    const target_ = result[stmt][target] || {}
    for (const [y, v] of Object.entries(years)) {
      target_[y] = (target_[y] || 0) + (v as number)
    }
    result[stmt][target] = target_
  })

  return result
}

function ReviewMappingsTable({
  mappings,
  overrides,
  setOverrides,
}: {
  mappings: Mapping[]
  overrides: Record<number, string>
  setOverrides: (next: Record<number, string>) => void
}) {
  const lowConfidence = mappings.filter(
    (m, i) => (overrides[i] ?? m.mapped_to) !== 'IGNORE' && m.confidence < 0.7,
  ).length

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-gray-900">
          Mappings ({mappings.length})
        </h4>
        {lowConfidence > 0 && (
          <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
            {lowConfidence} low-confidence — review before saving
          </span>
        )}
      </div>
      <div className="overflow-x-auto max-h-[400px]">
        <table className="min-w-full text-sm">
          <thead className="bg-white sticky top-0 border-b border-gray-100">
            <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="px-3 py-2 font-medium">Original label</th>
              <th className="px-3 py-2 font-medium">Mapped to</th>
              <th className="px-3 py-2 font-medium text-right">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {mappings.map((m, idx) => {
              const current = overrides[idx] ?? m.mapped_to
              const isOverridden = overrides[idx] !== undefined && overrides[idx] !== m.mapped_to
              return (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-3 py-2 max-w-[260px]">
                    <div className="font-medium text-gray-900 truncate" title={m.original_name}>
                      {m.original_name || <span className="italic text-gray-400">(empty)</span>}
                    </div>
                    <div className="text-[11px] text-gray-400">
                      {m.sheet_name} · row {m.row_index + 1}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <select
                      value={current}
                      onChange={(e) => setOverrides({ ...overrides, [idx]: e.target.value })}
                      className={`w-full text-xs border rounded px-2 py-1 bg-white ${
                        isOverridden
                          ? 'border-indigo-400 ring-1 ring-indigo-200'
                          : 'border-gray-200'
                      }`}
                    >
                      <option value="IGNORE">IGNORE — drop this row</option>
                      <optgroup label="P&L">
                        {TARGET_OPTIONS.filter((o) => o.group === 'PNL').map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </optgroup>
                      <optgroup label="Balance Sheet">
                        {TARGET_OPTIONS.filter((o) => o.group === 'BS').map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </optgroup>
                      <optgroup label="Cash Flow">
                        {TARGET_OPTIONS.filter((o) => o.group === 'CF').map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </optgroup>
                    </select>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <ConfidenceBadge value={m.confidence} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function AIIngestionWizard({ projectId, entityId: presetEntityId, onComplete }: Props) {
  const qc = useQueryClient()
  const [ingestData, setIngestData] = useState<AIIngestionResponse | null>(null)

  // When the wizard is opened from project-wide context (no presetEntityId),
  // the user picks the destination entity here. If a preset entity is passed
  // (entity workspace), we honour it but still show it for clarity.
  const [selectedEntityId, setSelectedEntityId] = useState<string>(presetEntityId || '')
  const [overrides, setOverrides] = useState<Record<number, string>>({})
  const [showIgnored, setShowIgnored] = useState(false)

  const { data: entities = [] } = useQuery({
    queryKey: ['entities', projectId],
    queryFn: () => entitiesApi.list(projectId).then((r) => r.data),
  })

  // Auto-select the first entity if none is preselected and entities loaded.
  if (!selectedEntityId && entities.length > 0 && !presetEntityId) {
    // setState during render is tolerated by React because we guard on the
    // condition. The next render will see the new value and avoid the loop.
    setSelectedEntityId(entities[0].id)
  }

  const { data: historical } = useQuery<HistoricalResponse>({
    queryKey: ['historical', projectId, selectedEntityId],
    queryFn: () =>
      selectedEntityId
        ? historicalApi.getEntityHistorical(selectedEntityId).then((r) => r.data)
        : historicalApi.getData(projectId).then((r) => r.data),
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => historicalApi.uploadAI(projectId, file, selectedEntityId || undefined),
    onSuccess: (res) => {
      setIngestData(res.data)
      setOverrides({})
      if (res.data.validation_errors.length > 0) {
        toast.error(`Found ${res.data.validation_errors.length} validation issues — review and edit before saving.`)
      } else {
        toast.success('AI Analysis complete!')
      }
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      const customError = err.response?.data?.error?.message
      const msg = customError || detail || 'AI Upload failed'
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    },
  })

  const editedParsed = useMemo(() => {
    if (!ingestData) return null
    if (Object.keys(overrides).length === 0) return ingestData.parsed
    return applyOverrides(ingestData.parsed, ingestData.mappings, overrides)
  }, [ingestData, overrides])

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!ingestData || !editedParsed) throw new Error('no data')
      return historicalApi.saveJSON(projectId, {
        parsed: editedParsed,
        years: ingestData.years,
        entity_id: selectedEntityId || undefined,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['historical', projectId] })
      if (selectedEntityId) qc.invalidateQueries({ queryKey: ['historical', projectId, selectedEntityId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      toast.success('Historical data persisted successfully!')
      setIngestData(null)
      setOverrides({})
      if (onComplete) onComplete()
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Failed to save validated data')
    },
  })

  const onDrop = useCallback(
    (acceptedFiles: File[], fileRejections: any[]) => {
      if (!selectedEntityId) {
        toast.error('Pick a target entity first.')
        return
      }
      if (acceptedFiles[0]) {
        uploadMutation.mutate(acceptedFiles[0])
      } else if (fileRejections.length > 0) {
        toast.error('File type not supported. Please upload a valid Excel, PDF, or CSV file.')
      }
    },
    [uploadMutation, selectedEntityId],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: 1,
  })

  // ---------------------------------------------------------------------
  // REVIEW SCREEN
  // ---------------------------------------------------------------------
  if (ingestData && editedParsed) {
    const { years, validation_errors, ai_stats, mappings } = ingestData
    const hasErrors = validation_errors.length > 0
    const ignoredMappings = mappings.filter(
      (m, i) => (overrides[i] ?? m.mapped_to) === 'IGNORE',
    )
    const targetEntityName =
      entities.find((e) => e.id === selectedEntityId)?.name || '(default entity)'

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <SparklesIcon className="w-6 h-6 text-indigo-500" />
              AI Extraction Review
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Saving to entity: <span className="font-semibold">{targetEntityName}</span> ·
              {' '}edit mappings below before persisting.
            </p>
          </div>
          <button
            onClick={() => { setIngestData(null); setOverrides({}) }}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        {/* AI Stats Banner */}
        <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 flex gap-4">
          <SparklesIcon className="w-8 h-8 text-indigo-500 shrink-0" />
          <div>
            <h4 className="text-sm font-semibold text-indigo-900">AI Analysis Summary</h4>
            <p className="text-sm text-indigo-700 mt-1">
              {ai_stats.phase2_used
                ? 'Document was highly complex. Automatically routed to Smart Model (Phase 2).'
                : 'Document processed quickly using standard extraction.'}
            </p>
            {ai_stats.reasons.length > 0 && (
              <ul className="list-disc list-inside text-xs text-indigo-600 mt-2">
                {ai_stats.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Validation Errors */}
        {hasErrors && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4">
            <h4 className="text-sm font-semibold text-red-800 flex items-center gap-2 mb-2">
              <ExclamationCircleIcon className="w-5 h-5" />
              Validation Issues ({validation_errors.length})
            </h4>
            <p className="text-xs text-red-700 mb-2">
              You can fix these by re-mapping rows below, or save anyway and edit the project later.
            </p>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-2">
              {validation_errors.map((e, i) => (
                <div key={i} className="text-sm bg-white border border-red-100 rounded p-2 text-red-700 shadow-sm">
                  <span className="font-semibold">[{e.tab}] {e.line_item}</span>{' '}
                  {e.year ? `(Year ${e.year})` : ''}: {e.message}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Mappings table with manual override */}
        <ReviewMappingsTable
          mappings={mappings.filter((m, i) => (overrides[i] ?? m.mapped_to) !== 'IGNORE')}
          overrides={overrides}
          setOverrides={setOverrides}
        />

        {/* IGNORED rows — collapsible */}
        <div className="card">
          <button
            type="button"
            onClick={() => setShowIgnored(!showIgnored)}
            className="flex items-center gap-2 text-sm font-semibold text-gray-700"
          >
            {showIgnored ? <ChevronDownIcon className="w-4 h-4" /> : <ChevronRightIcon className="w-4 h-4" />}
            Ignored rows ({ignoredMappings.length}) — click to expand and promote any back
          </button>
          {showIgnored && ignoredMappings.length > 0 && (
            <div className="mt-3 overflow-x-auto max-h-[300px]">
              <ReviewMappingsTable
                mappings={ignoredMappings}
                overrides={overrides}
                setOverrides={setOverrides}
              />
            </div>
          )}
        </div>

        {/* Data Preview */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {(['PNL', 'BS', 'CF'] as const).map((stmt) => (
            <div key={stmt} className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
              <div className="bg-gray-50 border-b border-gray-200 px-4 py-3 font-semibold text-gray-800 flex justify-between items-center">
                {stmt}
                <span className="text-xs bg-gray-200 text-gray-600 px-2 py-1 rounded-full">
                  {Object.keys(editedParsed[stmt] || {}).length} items
                </span>
              </div>
              <div className="overflow-x-auto flex-1 max-h-[400px]">
                <table className="min-w-full text-sm text-left">
                  <thead className="bg-white sticky top-0 border-b border-gray-100">
                    <tr>
                      <th className="px-4 py-2 font-medium text-gray-500">Line Item</th>
                      {years.map((y) => (
                        <th key={y} className="px-4 py-2 font-medium text-gray-500 text-right">{y}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {Object.entries(editedParsed[stmt] || {}).map(([item, vals]) => (
                      <tr key={item} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-2 font-medium text-gray-900 max-w-[200px] truncate" title={item}>{item}</td>
                        {years.map((y) => (
                          <td key={y} className="px-4 py-2 text-right text-gray-600 font-mono text-xs">
                            {vals[y] ? vals[y].toLocaleString() : '-'}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {Object.keys(editedParsed[stmt] || {}).length === 0 && (
                      <tr>
                        <td colSpan={years.length + 1} className="px-4 py-8 text-center text-gray-400 italic">
                          No items mapped
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
          <button onClick={() => { setIngestData(null); setOverrides({}) }} className="btn-secondary">
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className={`btn-primary flex items-center gap-2 ${
              saveMutation.isPending ? 'opacity-50 cursor-not-allowed' : ''
            }`}
            title={hasErrors ? 'Saving despite validation issues — fix later in the project view' : ''}
          >
            {saveMutation.isPending ? (
              'Saving...'
            ) : (
              <>
                <CheckCircleIcon className="w-5 h-5" />
                {hasErrors ? 'Save anyway' : 'Confirm & Save Data'}
              </>
            )}
          </button>
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------
  // UPLOAD SCREEN
  // ---------------------------------------------------------------------
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <SparklesIcon className="w-6 h-6 text-indigo-500" />
            AI Document Ingestion
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Upload your raw financial statements (PDF, Excel, CSV) and our AI will automatically map them.
          </p>
        </div>
      </div>

      {/* Entity selector */}
      <div className="card">
        <label className="label" htmlFor="entity-select">Target entity</label>
        <select
          id="entity-select"
          className="input max-w-md"
          value={selectedEntityId}
          onChange={(e) => setSelectedEntityId(e.target.value)}
          disabled={uploadMutation.isPending || !!presetEntityId}
        >
          <option value="">— select an entity —</option>
          {entities.map((ent) => (
            <option key={ent.id} value={ent.id}>
              {ent.name} {ent.entity_type ? `· ${ent.entity_type}` : ''}
            </option>
          ))}
        </select>
        <p className="text-xs text-gray-500 mt-2">
          {presetEntityId
            ? 'Uploading inside this entity workspace; the destination is fixed.'
            : 'Historical data will be saved under this entity. You can upload separately for each subsidiary.'}
        </p>
      </div>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-300 relative overflow-hidden group
          ${isDragActive ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400 hover:bg-gray-50'}
          ${uploadMutation.isPending || !selectedEntityId ? 'pointer-events-none opacity-60' : ''}
        `}
      >
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-all"></div>
        <input {...getInputProps()} />

        {uploadMutation.isPending ? (
          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
              <SparklesIcon className="w-6 h-6 text-indigo-600 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 animate-pulse" />
            </div>
            <div>
              <p className="text-lg font-semibold text-indigo-900">Processing Document</p>
              <p className="text-sm text-indigo-600 mt-1 animate-pulse">Extracting tables, mapping items, validating balances...</p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center relative z-10">
            <div className="w-16 h-16 bg-white shadow-sm border border-gray-100 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
              <DocumentIcon className="w-8 h-8 text-indigo-500" />
            </div>
            <p className="text-gray-900 font-semibold text-lg">
              {!selectedEntityId
                ? 'Select an entity above first'
                : isDragActive
                ? 'Drop your file now!'
                : 'Drag & drop a file here'}
            </p>
            <p className="text-gray-500 text-sm mt-2 mb-6">
              Supports .pdf, .xlsx, .xls, and .csv
            </p>
            <button className="bg-white border border-gray-200 text-gray-700 font-medium py-2 px-6 rounded-lg shadow-sm hover:border-gray-300 transition-colors">
              Browse Files
            </button>
          </div>
        )}
      </div>

      {/* Currently Loaded Data preview */}
      {historical && (Object.keys(historical.PNL || {}).length > 0 || Object.keys(historical.BS || {}).length > 0) ? (
        <div className="mt-8">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <TableCellsIcon className="w-5 h-5 text-gray-500" />
            Currently Loaded Data
          </h3>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {(['PNL', 'BS', 'CF'] as const).map((stmt) => {
              const stmtData = historical[stmt as keyof HistoricalResponse] || {}
              const items = Object.keys(stmtData)
              const yearsSet = new Set<string>()
              items.forEach((item) => Object.keys(stmtData[item]).forEach((y) => yearsSet.add(y)))
              const stmtYears = Array.from(yearsSet).sort()

              if (items.length === 0) return null

              return (
                <div key={stmt} className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
                  <div className="bg-gray-50 border-b border-gray-200 px-4 py-3 font-semibold text-gray-800 flex justify-between items-center">
                    {stmt}
                    <span className="text-xs bg-green-100 text-green-700 font-medium px-2 py-1 rounded-full border border-green-200">
                      {items.length} items loaded
                    </span>
                  </div>
                  <div className="overflow-x-auto flex-1 max-h-[300px]">
                    <table className="min-w-full text-sm text-left">
                      <thead className="bg-white sticky top-0 border-b border-gray-100">
                        <tr>
                          <th className="px-4 py-2 font-medium text-gray-500">Line Item</th>
                          {stmtYears.map((y) => (
                            <th key={y} className="px-4 py-2 font-medium text-gray-500 text-right">{y}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {items.map((item) => (
                          <tr key={item} className="hover:bg-gray-50 transition-colors">
                            <td className="px-4 py-2 font-medium text-gray-900 max-w-[200px] truncate" title={item}>{item}</td>
                            {stmtYears.map((y) => {
                              const raw = stmtData[item]?.[Number(y)]
                              return (
                                <td key={y} className="px-4 py-2 text-right text-gray-600 font-mono text-xs">
                                  {raw ? Number(raw).toLocaleString() : '-'}
                                </td>
                              )
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
          <div className="bg-gray-50 rounded-xl p-4">
            <div className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center font-bold mb-3">1</div>
            <h4 className="font-semibold text-gray-900 text-sm mb-1">Pick the entity</h4>
            <p className="text-xs text-gray-500 leading-relaxed">Each subsidiary keeps its own historical series.</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-4">
            <div className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center font-bold mb-3">2</div>
            <h4 className="font-semibold text-gray-900 text-sm mb-1">Drop the file</h4>
            <p className="text-xs text-gray-500 leading-relaxed">PDF, Excel, or CSV — the AI extracts and maps lines for you.</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-4">
            <div className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center font-bold mb-3">3</div>
            <h4 className="font-semibold text-gray-900 text-sm mb-1">Review & save</h4>
            <p className="text-xs text-gray-500 leading-relaxed">Override any wrong mapping inline, then save.</p>
          </div>
        </div>
      )}
    </div>
  )
}
