import { useEffect, useMemo, useState } from 'react'
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
  ArrowUpTrayIcon,
} from '@heroicons/react/24/outline'

import { entitiesApi, historicalApi } from '../../services/api'
import { ALL_CANONICAL, statementOf, type CanonicalStatement } from '../../lib/canonicalItems'
import type { Project, AIIngestionResponse } from '../../types/api'

interface Props {
  projectId: string
  project: Project
  entityId?: string
  onComplete?: () => void
}

type Mapping = AIIngestionResponse['mappings'][number]

const UNIT_OPTIONS = [
  { value: 1, label: 'Units' },
  { value: 1000, label: 'Thousands (k)' },
  { value: 1000000, label: 'Millions (M)' },
]

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
  const result: AIIngestionResponse['parsed'] = { PNL: {}, BS: {}, CF: {} }

  const valuesByOriginal: Record<string, Record<string, number>> = {}
  for (const stmtKey of ['PNL', 'BS', 'CF'] as CanonicalStatement[]) {
    for (const [item, years] of Object.entries(base[stmtKey] || {})) {
      valuesByOriginal[item] = years as Record<string, number>
    }
  }

  baseMappings.forEach((m, idx) => {
    const target = overrides[idx] ?? m.mapped_to
    if (!target || target === 'IGNORE') return
    const stmt = statementOf(target)
    if (!stmt) return
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

export default function DocumentManager({ projectId, entityId: presetEntityId, onComplete }: Props) {
  const qc = useQueryClient()
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [selectedEntityId, setSelectedEntityId] = useState<string>(presetEntityId || '')
  
  // Mapping overrides keyed by docId -> rowIndex -> override
  const [overrides, setOverrides] = useState<Record<string, Record<number, string>>>({})
  
  const [unitMultiplier, setUnitMultiplier] = useState<number>(1)
  const [excludedYears, setExcludedYears] = useState<Set<string>>(new Set())

  const { data: entities = [] } = useQuery({
    queryKey: ['entities', projectId],
    queryFn: () => entitiesApi.list(projectId).then(r => r.data),
  })

  const { data: documents = [], isLoading: loadingDocs } = useQuery({
    queryKey: ['documents', projectId],
    queryFn: () => historicalApi.getDocuments(projectId).then(r => r.data),
  })

  const uploadBatch = useMutation({
    mutationFn: (files: File[]) => historicalApi.batchUpload(projectId, files, selectedEntityId || undefined),
    onSuccess: () => {
      toast.success('Documents uploaded')
      qc.invalidateQueries({ queryKey: ['documents', projectId] })
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to upload documents')
    }
  })

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => uploadBatch.mutate(files)
  })

  const toggleDoc = useMutation({
    mutationFn: ({ id, is_ignored }: { id: string, is_ignored: boolean }) => historicalApi.toggleDocument(projectId, id, is_ignored),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents', projectId] })
  })

  const analyzeDoc = useMutation({
    mutationFn: (id: string) => historicalApi.analyzeDocument(projectId, id),
    onSuccess: () => {
      toast.success('Analysis complete')
      qc.invalidateQueries({ queryKey: ['documents', projectId] })
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Analysis failed')
    }
  })

  const saveMutation = useMutation({
    mutationFn: (data: { parsed: any; years: number[]; entity_id?: string }) => historicalApi.saveJSON(projectId, data),
    onSuccess: () => {
      toast.success('Consolidated data saved successfully')
      onComplete?.()
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to save data')
    }
  })

  const selectedDoc = documents.find(d => d.id === selectedDocId)

  const handleConsolidate = () => {
    // Merge all active documents
    const activeDocs = documents.filter(d => !d.is_ignored && d.has_analysis && d.ai_analysis)
    if (!activeDocs.length) {
      toast.error('No analyzed documents selected for consolidation')
      return
    }

    const mergedParsed: any = { PNL: {}, BS: {}, CF: {} }
    const mergedYears = new Set<number>()

    activeDocs.forEach(doc => {
      const docOverrides = overrides[doc.id] || {}
      const finalParsed = applyOverrides(doc.ai_analysis!.parsed, doc.ai_analysis!.mappings, docOverrides)
      
      // Merge
      for (const stmt of ['PNL', 'BS', 'CF'] as const) {
        for (const [item, yearsDict] of Object.entries(finalParsed[stmt] || {})) {
          if (!mergedParsed[stmt][item]) mergedParsed[stmt][item] = {}
          for (const [yearStr, val] of Object.entries(yearsDict)) {
            if (excludedYears.has(yearStr)) continue
            mergedYears.add(Number(yearStr))
            const rawVal = val as number
            // apply multiplier
            const finalVal = rawVal * unitMultiplier
            mergedParsed[stmt][item][yearStr] = finalVal // overwrite if duplicate
          }
        }
      }
    })

    saveMutation.mutate({
      parsed: mergedParsed,
      years: Array.from(mergedYears).sort((a, b) => a - b),
      entity_id: selectedEntityId || undefined
    })
  }

  // Calculate globally missing items
  const globalMissing = useMemo(() => {
    const activeDocs = documents.filter(d => !d.is_ignored && d.has_analysis)
    const allFound = new Set<string>()
    activeDocs.forEach(d => {
      if (d.ai_analysis?.parsed.PNL && Object.keys(d.ai_analysis.parsed.PNL).length) allFound.add('PNL (Income Statement)')
      if (d.ai_analysis?.parsed.BS && Object.keys(d.ai_analysis.parsed.BS).length) allFound.add('Balance Sheet')
      if (d.ai_analysis?.parsed.CF && Object.keys(d.ai_analysis.parsed.CF).length) allFound.add('Cash Flow')
    })
    const needed = ['PNL (Income Statement)', 'Balance Sheet', 'Cash Flow']
    return needed.filter(n => !allFound.has(n))
  }, [documents])

  // Years detected by the LLM across all active, analyzed documents.
  // Backend stores them as strings (e.g. "2024", "2025e", "FY 2026") so we
  // keep them as strings and let the user untick projection / forecast
  // columns that should not enter the historical series.
  const detectedYears = useMemo<string[]>(() => {
    const set = new Set<string>()
    documents.forEach(d => {
      if (d.is_ignored || !d.has_analysis || !d.ai_analysis) return
      // doc.ai_analysis.years was typed number[] historically but the new
      // ingestion service returns the LLM's raw period labels; tolerate both.
      const yrs: any[] = d.ai_analysis.years || []
      yrs.forEach(y => set.add(String(y)))
    })
    return Array.from(set).sort()
  }, [documents])

  // Heuristic: any label that contains letters is almost certainly a
  // projection / forecast column (2025e, FY26, Plan, Forecast, P25, …).
  const looksLikeProjection = (year: string): boolean => /[a-zA-Z]/.test(year)

  // Auto-exclude obvious projection columns the first time we see them
  // so the user doesn't accidentally import "2025e" as actuals. Re-runs
  // when a newly-analysed doc surfaces years we hadn't seen before.
  const autoExcludedRef = useMemo(() => new Set<string>(), [])
  useEffect(() => {
    const fresh = detectedYears.filter(
      y => looksLikeProjection(y) && !autoExcludedRef.has(y),
    )
    if (fresh.length === 0) return
    fresh.forEach(y => autoExcludedRef.add(y))
    setExcludedYears(prev => {
      const next = new Set(prev)
      fresh.forEach(y => next.add(y))
      return next
    })
  }, [detectedYears, autoExcludedRef])

  return (
    <div className="flex flex-col h-[80vh] border rounded-lg bg-white overflow-hidden shadow-sm">
      {/* Header toolbar */}
      <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between shrink-0">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Document Manager</h2>
          <p className="text-sm text-gray-500">Upload, analyze, and consolidate financial statements.</p>
        </div>
        <div className="flex items-center gap-4">
          {!presetEntityId && entities.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Target Entity:</span>
              <select
                value={selectedEntityId}
                onChange={(e) => setSelectedEntityId(e.target.value)}
                className="input text-sm py-1 max-w-[200px]"
              >
                <option value="">(Project Level)</option>
                {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
              </select>
            </div>
          )}
          <select
            value={unitMultiplier}
            onChange={(e) => setUnitMultiplier(Number(e.target.value))}
            className="input text-sm py-1"
          >
            {UNIT_OPTIONS.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
          </select>
          <button
            onClick={handleConsolidate}
            disabled={saveMutation.isPending || !documents.some(d => !d.is_ignored && d.has_analysis)}
            className="btn btn-primary shadow-sm shadow-indigo-200"
          >
            {saveMutation.isPending ? 'Saving...' : 'Consolidate & Save'}
          </button>
        </div>
      </div>

      {/* Year filter — appears once at least one doc is analyzed. Lets the
          user untick projection columns (2025e, FY26, Plan, …) so they do
          not contaminate the historical series. */}
      {detectedYears.length > 0 && (
        <div className="px-4 py-2 border-b bg-white shrink-0 flex items-center gap-3 flex-wrap">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Years to import
          </span>
          {detectedYears.map(y => {
            const included = !excludedYears.has(y)
            const looksProj = looksLikeProjection(y)
            return (
              <label
                key={y}
                className={`text-xs px-2 py-0.5 rounded border cursor-pointer select-none transition-colors ${
                  included
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-800 hover:bg-indigo-100'
                    : 'border-gray-200 bg-gray-50 text-gray-400 line-through hover:bg-gray-100'
                }`}
                title={looksProj ? 'Looks like a projection / forecast column — usually excluded' : ''}
              >
                <input
                  type="checkbox"
                  className="mr-1.5 align-middle"
                  checked={included}
                  onChange={(e) => {
                    setExcludedYears(prev => {
                      const next = new Set(prev)
                      if (e.target.checked) next.delete(y)
                      else next.add(y)
                      return next
                    })
                  }}
                />
                {y}
                {looksProj && <span className="ml-1 text-[9px] uppercase opacity-60">proj</span>}
              </label>
            )
          })}
          {excludedYears.size > 0 && (
            <button
              type="button"
              onClick={() => setExcludedYears(new Set())}
              className="ml-auto text-xs text-gray-500 hover:text-gray-900 underline underline-offset-2"
            >
              Include all
            </button>
          )}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel: Document List */}
        <div className="w-1/3 border-r bg-gray-50/50 flex flex-col shrink-0">
          <div className="p-4 border-b">
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                isDragActive ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400 bg-white'
              }`}
            >
              <input {...getInputProps()} />
              <ArrowUpTrayIcon className="w-6 h-6 mx-auto text-indigo-500 mb-2" />
              <p className="text-sm font-medium text-gray-700">Drop files or click to upload</p>
              <p className="text-xs text-gray-500 mt-1">Excel, CSV, PDF (Max 50MB total)</p>
            </div>
          </div>

          <div className="p-3 border-b bg-amber-50">
            <h4 className="text-xs font-semibold text-amber-800 flex items-center gap-1 uppercase tracking-wide">
              <ExclamationCircleIcon className="w-4 h-4" /> Global Model Status
            </h4>
            {globalMissing.length === 0 ? (
              <p className="text-xs text-amber-700 mt-1">All core statements present across active documents.</p>
            ) : (
              <p className="text-xs text-amber-700 mt-1">Missing: <span className="font-medium">{globalMissing.join(', ')}</span></p>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {loadingDocs ? (
              <div className="p-4 text-center text-sm text-gray-500 animate-pulse">Loading documents...</div>
            ) : documents.length === 0 ? (
              <div className="p-4 text-center text-sm text-gray-500 italic">No documents uploaded yet.</div>
            ) : (
              documents.map(doc => (
                <div
                  key={doc.id}
                  onClick={() => setSelectedDocId(doc.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedDocId === doc.id
                      ? 'border-indigo-500 bg-indigo-50/50 ring-1 ring-indigo-500 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-indigo-300'
                  } ${doc.is_ignored ? 'opacity-60 grayscale' : ''}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <DocumentIcon className={`w-5 h-5 shrink-0 ${doc.is_ignored ? 'text-gray-400' : 'text-indigo-500'}`} />
                      <span className="text-sm font-medium text-gray-900 truncate" title={doc.filename}>{doc.filename}</span>
                    </div>
                    <label className="flex items-center gap-1 shrink-0 cursor-pointer" onClick={e => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={!doc.is_ignored}
                        onChange={(e) => toggleDoc.mutate({ id: doc.id, is_ignored: !e.target.checked })}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                      />
                      <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wide">Use</span>
                    </label>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-gray-500">{(doc.size / 1024 / 1024).toFixed(1)} MB</span>
                    {doc.has_analysis ? (
                      <span className="flex items-center gap-1 text-green-600 font-medium bg-green-50 px-1.5 py-0.5 rounded border border-green-100">
                        <CheckCircleIcon className="w-3 h-3" /> Analyzed
                      </span>
                    ) : (
                      <span className="text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">Pending</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Panel: Document Details & Analysis */}
        <div className="flex-1 overflow-y-auto bg-white flex flex-col">
          {selectedDoc ? (
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-xl font-medium text-gray-900">{selectedDoc.filename}</h3>
                  <p className="text-sm text-gray-500 mt-1">{(selectedDoc.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
                {!selectedDoc.has_analysis && (
                  <button
                    onClick={() => analyzeDoc.mutate(selectedDoc.id)}
                    disabled={analyzeDoc.isPending || selectedDoc.is_ignored}
                    className="btn btn-secondary flex items-center gap-2"
                  >
                    <SparklesIcon className="w-4 h-4 text-indigo-500" />
                    {analyzeDoc.isPending ? 'Analyzing...' : 'Run AI Analysis'}
                  </button>
                )}
              </div>

              {selectedDoc.is_ignored && (
                <div className="mb-6 p-4 rounded-lg bg-gray-50 border border-gray-200 flex items-start gap-3">
                  <XMarkIcon className="w-5 h-5 text-gray-400" />
                  <div>
                    <h4 className="text-sm font-medium text-gray-800">Document is ignored</h4>
                    <p className="text-sm text-gray-500 mt-1">Check "Use" in the left panel to include it in the consolidated project model.</p>
                  </div>
                </div>
              )}

              {selectedDoc.has_analysis && selectedDoc.ai_analysis && (
                <div className="space-y-6">
                  {/* Analysis Summary */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="card">
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                        <TableCellsIcon className="w-4 h-4" /> Detected
                      </h4>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {['PNL', 'BS', 'CF'].map(stmt => {
                          const hasData = Object.keys(selectedDoc.ai_analysis!.parsed[stmt as 'PNL'] || {}).length > 0
                          return hasData ? (
                            <span key={stmt} className="inline-flex items-center gap-1 text-xs font-medium bg-green-50 text-green-700 border border-green-200 px-2 py-1 rounded">
                              <CheckCircleIcon className="w-3 h-3" /> {stmt}
                            </span>
                          ) : null
                        })}
                        {selectedDoc.missing_inputs?.map(m => (
                          <span key={m} className="inline-flex items-center gap-1 text-xs font-medium bg-red-50 text-red-700 border border-red-200 px-2 py-1 rounded">
                            <XMarkIcon className="w-3 h-3" /> {m} missing
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="card">
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Years Covered</h4>
                      <p className="text-sm font-medium text-gray-900 mt-2">
                        {selectedDoc.ai_analysis.years.length > 0 
                          ? selectedDoc.ai_analysis.years.join(', ')
                          : 'No years detected'}
                      </p>
                    </div>
                  </div>

                  <ReviewMappingsTable 
                    mappings={selectedDoc.ai_analysis.mappings}
                    overrides={overrides[selectedDoc.id] || {}}
                    setOverrides={(next) => setOverrides({ ...overrides, [selectedDoc.id]: next })}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400 p-8">
              <DocumentIcon className="w-16 h-16 mb-4 text-gray-200" />
              <p className="text-lg font-medium text-gray-900">No document selected</p>
              <p className="text-sm mt-2 max-w-md text-center">Select a document from the left panel to view details, run AI analysis, and review mappings.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
