/**
 * RevenueStreamsSetup — Step 0 before downloading the historical template.
 *
 * Lets the user define one or more named revenue lines (e.g. "Venta Energía",
 * "Venta Fertilizante", "Venta CO2"). The list is saved to the backend so that
 * the template download and the projection engine both know how to structure
 * revenue.
 *
 * Defaults to a single "Revenue" line (legacy / simple mode).
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { revenueStreamsApi } from '../../services/api'

interface StreamRow {
  id: string | null
  stream_name: string
  display_order: number
  projection_method: string
}

interface Props {
  projectId: string
}

export default function RevenueStreamsSetup({ projectId }: Props) {
  const qc = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [rows, setRows] = useState<StreamRow[]>([])

  const { data: savedStreams, isLoading } = useQuery({
    queryKey: ['revenue-streams', projectId],
    queryFn: () => revenueStreamsApi.list(projectId).then(r => r.data),
  })

  const { mutate: save, isPending } = useMutation({
    mutationFn: (streams: StreamRow[]) =>
      revenueStreamsApi.save(
        projectId,
        streams.map((s, i) => ({
          stream_name: s.stream_name.trim(),
          display_order: i,
          projection_method: s.projection_method,
        })),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['revenue-streams', projectId] })
      toast.success('Revenue streams saved')
      setEditing(false)
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Save failed')
    },
  })

  const startEditing = () => {
    setRows(
      savedStreams
        ? savedStreams.map(s => ({ ...s }))
        : [{ id: null, stream_name: 'Revenue', display_order: 0, projection_method: 'growth_flat' }],
    )
    setEditing(true)
  }

  const addRow = () => {
    setRows(prev => [
      ...prev,
      { id: null, stream_name: '', display_order: prev.length, projection_method: 'growth_flat' },
    ])
  }

  const removeRow = (idx: number) => {
    setRows(prev => prev.filter((_, i) => i !== idx))
  }

  const updateName = (idx: number, value: string) => {
    setRows(prev => prev.map((r, i) => (i === idx ? { ...r, stream_name: value } : r)))
  }

  const handleSave = () => {
    const clean = rows.filter(r => r.stream_name.trim())
    if (!clean.length) {
      toast.error('At least one revenue stream is required')
      return
    }
    save(clean)
  }

  if (isLoading) return null

  const isMultiStream =
    savedStreams &&
    (savedStreams.length > 1 || (savedStreams.length === 1 && savedStreams[0].stream_name !== 'Revenue'))

  return (
    <div className="card">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-medium text-gray-900">Step 1 — Define Revenue Lines</h3>
          <p className="text-sm text-gray-500 mt-0.5">
            {isMultiStream
              ? `${savedStreams!.length} custom revenue streams configured.`
              : 'Single revenue line (default). Add multiple streams for disaggregated revenue.'}
          </p>
        </div>
        {!editing && (
          <button className="btn btn-secondary btn-sm" onClick={startEditing}>
            {isMultiStream ? 'Edit Streams' : 'Add Revenue Streams'}
          </button>
        )}
      </div>

      {/* Saved view */}
      {!editing && savedStreams && (
        <div className="flex flex-wrap gap-2">
          {savedStreams.map(s => (
            <span
              key={s.stream_name}
              className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                s.stream_name === 'Revenue'
                  ? 'bg-gray-100 text-gray-600'
                  : 'bg-blue-100 text-blue-700'
              }`}
            >
              {s.stream_name}
            </span>
          ))}
        </div>
      )}

      {/* Edit form */}
      {editing && (
        <div className="space-y-2 mt-2">
          {rows.map((row, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <span className="text-xs text-gray-400 w-5 text-right">{idx + 1}.</span>
              <input
                className="input flex-1 text-sm"
                placeholder="e.g. Venta Energía"
                value={row.stream_name}
                onChange={e => updateName(idx, e.target.value)}
              />
              {rows.length > 1 && (
                <button
                  className="text-gray-400 hover:text-red-500 transition-colors"
                  onClick={() => removeRow(idx)}
                  title="Remove"
                >
                  ✕
                </button>
              )}
            </div>
          ))}

          <div className="flex items-center gap-2 pt-1">
            <button className="btn btn-secondary btn-sm" onClick={addRow}>
              + Add stream
            </button>
            <div className="flex-1" />
            <button className="btn btn-secondary btn-sm" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={isPending}>
              {isPending ? 'Saving…' : 'Save'}
            </button>
          </div>

          <p className="text-xs text-gray-400 mt-1">
            The template will include one row per stream plus an auto-calculated "Total Revenue" row.
          </p>
        </div>
      )}
    </div>
  )
}
