import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { historicalApi } from '../../services/api'
import toast from 'react-hot-toast'
import type { Project, AIIngestionResponse, HistoricalResponse } from '../../types/api'
import { CheckCircleIcon, ExclamationCircleIcon, DocumentIcon, SparklesIcon, XMarkIcon, TableCellsIcon } from '@heroicons/react/24/outline'

interface Props { projectId: string; project: Project; entityId?: string; onComplete?: () => void }

export default function AIIngestionWizard({ projectId, entityId, onComplete }: Props) {
  const qc = useQueryClient()
  const [ingestData, setIngestData] = useState<AIIngestionResponse | null>(null)

  const { data: historical } = useQuery<HistoricalResponse>({
    queryKey: ['historical', projectId, entityId],
    queryFn: () => entityId 
      ? historicalApi.getEntityHistorical(entityId).then(r => r.data)
      : historicalApi.getData(projectId).then(r => r.data),
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => historicalApi.uploadAI(projectId, file),
    onSuccess: (res) => {
      setIngestData(res.data)
      if (res.data.validation_errors.length > 0) {
        toast.error(`Found ${res.data.validation_errors.length} validation issues.`)
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

  const saveMutation = useMutation({
    mutationFn: () => historicalApi.saveJSON(projectId, { parsed: ingestData!.parsed, years: ingestData!.years, entity_id: entityId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['historical', projectId] })
      if (entityId) qc.invalidateQueries({ queryKey: ['historical', projectId, entityId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      toast.success('Historical data persisted successfully!')
      setIngestData(null)
      if (onComplete) onComplete()
    },
    onError: () => toast.error('Failed to save validated data'),
  })

  const onDrop = useCallback((acceptedFiles: File[], fileRejections: any[]) => {
    if (acceptedFiles[0]) {
      uploadMutation.mutate(acceptedFiles[0])
    } else if (fileRejections.length > 0) {
      toast.error('File type not supported. Please upload a valid Excel, PDF, or CSV file.')
    }
  }, [uploadMutation])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: 1,
  })

  if (ingestData) {
    const { parsed, years, validation_errors, ai_stats } = ingestData
    const hasErrors = validation_errors.length > 0

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <SparklesIcon className="w-6 h-6 text-indigo-500" />
              AI Extraction Review
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Review the extracted financial data before saving to your project.
            </p>
          </div>
          <button 
            onClick={() => setIngestData(null)} 
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
                ? "Document was highly complex. Automatically routed to Smart Model (Phase 2)." 
                : "Document processed quickly using standard extraction."}
            </p>
            {ai_stats.reasons.length > 0 && (
              <ul className="list-disc list-inside text-xs text-indigo-600 mt-2">
                {ai_stats.reasons.map((r, i) => <li key={i}>{r}</li>)}
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
            <div className="space-y-2 max-h-48 overflow-y-auto pr-2">
              {validation_errors.map((e, i) => (
                <div key={i} className="text-sm bg-white border border-red-100 rounded p-2 text-red-700 shadow-sm">
                  <span className="font-semibold">[{e.tab}] {e.line_item}</span> {e.year ? `(Year ${e.year})` : ''}: {e.message}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Data Preview */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {['PNL', 'BS', 'CF'].map(stmt => (
            <div key={stmt} className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
              <div className="bg-gray-50 border-b border-gray-200 px-4 py-3 font-semibold text-gray-800 flex justify-between items-center">
                {stmt}
                <span className="text-xs bg-gray-200 text-gray-600 px-2 py-1 rounded-full">
                  {Object.keys(parsed[stmt as keyof typeof parsed] || {}).length} items
                </span>
              </div>
              <div className="overflow-x-auto flex-1 max-h-[400px]">
                <table className="min-w-full text-sm text-left">
                  <thead className="bg-white sticky top-0 border-b border-gray-100">
                    <tr>
                      <th className="px-4 py-2 font-medium text-gray-500">Line Item</th>
                      {years.map(y => <th key={y} className="px-4 py-2 font-medium text-gray-500 text-right">{y}</th>)}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {Object.entries(parsed[stmt as keyof typeof parsed] || {}).map(([item, vals]) => (
                      <tr key={item} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-2 font-medium text-gray-900 max-w-[200px] truncate" title={item}>{item}</td>
                        {years.map(y => (
                          <td key={y} className="px-4 py-2 text-right text-gray-600 font-mono text-xs">
                            {vals[y] ? vals[y].toLocaleString() : '-'}
                          </td>
                        ))}
                      </tr>
                    ))}
                    {Object.keys(parsed[stmt as keyof typeof parsed] || {}).length === 0 && (
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
          <button onClick={() => setIngestData(null)} className="btn-secondary">Cancel</button>
          <button 
            onClick={() => saveMutation.mutate()} 
            disabled={saveMutation.isPending || hasErrors}
            className={`btn-primary flex items-center gap-2 ${(saveMutation.isPending || hasErrors) ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {saveMutation.isPending ? 'Saving...' : <><CheckCircleIcon className="w-5 h-5"/> Confirm & Save Data</>}
          </button>
        </div>
      </div>
    )
  }

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

      <div 
        {...getRootProps()} 
        className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-300 relative overflow-hidden group
          ${isDragActive ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400 hover:bg-gray-50'}
          ${uploadMutation.isPending ? 'pointer-events-none' : ''}
        `}
      >
        {/* Background decorative blob */}
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
              {isDragActive ? 'Drop your file now!' : 'Drag & drop a file here'}
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

      {/* Educational info or Currently Loaded Data */}
      {historical && (Object.keys(historical.PNL || {}).length > 0 || Object.keys(historical.BS || {}).length > 0) ? (
        <div className="mt-8">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <TableCellsIcon className="w-5 h-5 text-gray-500" />
            Currently Loaded Data
          </h3>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {['PNL', 'BS', 'CF'].map(stmt => {
              const stmtData = historical[stmt as keyof HistoricalResponse] || {}
              const items = Object.keys(stmtData)
              // Extract all unique years from this statement
              const yearsSet = new Set<string>()
              items.forEach(item => Object.keys(stmtData[item]).forEach(y => yearsSet.add(y)))
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
                          {stmtYears.map(y => <th key={y} className="px-4 py-2 font-medium text-gray-500 text-right">{y}</th>)}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {items.map(item => (
                          <tr key={item} className="hover:bg-gray-50 transition-colors">
                            <td className="px-4 py-2 font-medium text-gray-900 max-w-[200px] truncate" title={item}>{item}</td>
                            {stmtYears.map(y => {
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
            <h4 className="font-semibold text-gray-900 text-sm mb-1">Upload Any Format</h4>
            <p className="text-xs text-gray-500 leading-relaxed">Simply upload your company's raw historicals. No pre-formatting needed.</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-4">
            <div className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center font-bold mb-3">2</div>
            <h4 className="font-semibold text-gray-900 text-sm mb-1">AI Mapping</h4>
            <p className="text-xs text-gray-500 leading-relaxed">Our AI intelligently maps your internal line items to standard financial categories.</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-4">
            <div className="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center font-bold mb-3">3</div>
            <h4 className="font-semibold text-gray-900 text-sm mb-1">Human Validation</h4>
            <p className="text-xs text-gray-500 leading-relaxed">Review the extracted data and confirm it passes structural balance checks.</p>
          </div>
        </div>
      )}
    </div>
  )
}
