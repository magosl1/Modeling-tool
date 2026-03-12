import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { historicalApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Props { projectId: string; project: any }

export default function UploadHistorical({ projectId, project }: Props) {
  const qc = useQueryClient()
  const [validationErrors, setValidationErrors] = useState<any[]>([])

  const { data: historical } = useQuery({
    queryKey: ['historical', projectId],
    queryFn: () => historicalApi.getData(projectId).then(r => r.data),
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => historicalApi.upload(projectId, file),
    onSuccess: () => {
      setValidationErrors([])
      qc.invalidateQueries({ queryKey: ['historical', projectId] })
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      toast.success('Historical data uploaded and validated!')
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      if (detail?.error?.details) {
        setValidationErrors(detail.error.details)
        toast.error(`Validation failed: ${detail.error.details.length} error(s)`)
      } else {
        toast.error(err.response?.data?.detail || 'Upload failed')
      }
    },
  })

  const onDrop = useCallback((files: File[]) => {
    if (files[0]) uploadMutation.mutate(files[0])
  }, [uploadMutation])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
    maxFiles: 1,
  })

  const downloadTemplate = async () => {
    try {
      const res = await historicalApi.downloadTemplate(projectId)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = 'historical_template.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Failed to download template')
    }
  }

  const hasData = historical && (
    Object.keys(historical.PNL || {}).length > 0 ||
    Object.keys(historical.BS || {}).length > 0
  )

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-1">Historical Data</h2>
        <p className="text-sm text-gray-500">
          Download the template, fill in your historical financials, and upload it back.
        </p>
      </div>

      {/* Step 1: Download Template */}
      <div className="card">
        <h3 className="font-medium text-gray-900 mb-3">Step 1 — Download Template</h3>
        <p className="text-sm text-gray-500 mb-4">
          3-tab Excel file (P&amp;L, Balance Sheet, Cash Flow) pre-configured for{' '}
          <strong>{project.currency} {project.scale}</strong>.
        </p>
        <button onClick={downloadTemplate} className="btn-secondary">
          ⬇ Download Historical Template (.xlsx)
        </button>
      </div>

      {/* Step 2: Upload */}
      <div className="card">
        <h3 className="font-medium text-gray-900 mb-3">Step 2 — Upload Completed File</h3>
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
            isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <input {...getInputProps()} />
          {uploadMutation.isPending ? (
            <p className="text-gray-500">Uploading and validating...</p>
          ) : isDragActive ? (
            <p className="text-primary-600">Drop the file here</p>
          ) : (
            <>
              <p className="text-gray-600 font-medium">Drag &amp; drop your .xlsx file here</p>
              <p className="text-gray-400 text-sm mt-1">or click to browse</p>
            </>
          )}
        </div>
      </div>

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="card border-red-200 bg-red-50">
          <h3 className="font-medium text-red-800 mb-3">
            Validation Errors ({validationErrors.length})
          </h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {validationErrors.map((e, i) => (
              <div key={i} className="text-sm bg-white border border-red-200 rounded-lg p-3">
                <span className="font-medium text-red-700">[{e.tab}] {e.line_item}</span>
                {e.year && <span className="text-red-500 ml-2">Year {e.year}</span>}
                <p className="text-red-600 mt-0.5">{e.message}</p>
              </div>
            ))}
          </div>
          <p className="text-red-600 text-sm mt-3">Fix the errors above and re-upload.</p>
        </div>
      )}

      {/* Success State */}
      {hasData && validationErrors.length === 0 && (
        <div className="card border-green-200 bg-green-50">
          <h3 className="font-medium text-green-800 mb-2">✓ Historical Data Loaded</h3>
          <div className="text-sm text-green-700">
            <p>P&amp;L: {Object.keys(historical.PNL).length} line items</p>
            <p>Balance Sheet: {Object.keys(historical.BS).length} line items</p>
            <p>Cash Flow: {Object.keys(historical.CF).length} line items</p>
          </div>
          <p className="text-green-600 text-sm mt-3">
            Proceed to <strong>Assumptions</strong> to configure your projection model.
          </p>
        </div>
      )}
    </div>
  )
}
