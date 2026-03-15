import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sharingApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Props {
  projectId: string
}

export default function SharePanel({ projectId }: Props) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'viewer' | 'editor'>('viewer')
  const qc = useQueryClient()

  const { data: shares = [] } = useQuery({
    queryKey: ['shares', projectId],
    queryFn: () => sharingApi.list(projectId).then(r => r.data),
  })

  const shareMutation = useMutation({
    mutationFn: () => sharingApi.share(projectId, { email, role }),
    onSuccess: () => {
      toast.success(`Invited ${email} as ${role}`)
      qc.invalidateQueries({ queryKey: ['shares', projectId] })
      setEmail('')
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Could not share project'),
  })

  const revokeMutation = useMutation({
    mutationFn: (userId: string) => sharingApi.revoke(projectId, userId),
    onSuccess: () => {
      toast.success('Access revoked')
      qc.invalidateQueries({ queryKey: ['shares', projectId] })
    },
    onError: () => toast.error('Could not revoke access'),
  })

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-gray-900">Share Project</h3>
        <p className="text-sm text-gray-500">Invite teammates to view or edit this project.</p>
      </div>

      {/* Invite form */}
      <div className="flex gap-2 items-center">
        <input
          type="email"
          placeholder="colleague@company.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="flex-1 border border-gray-300 rounded px-3 py-1.5 text-sm"
          id="share-email-input"
        />
        <select
          value={role}
          onChange={e => setRole(e.target.value as 'viewer' | 'editor')}
          className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          id="share-role-select"
        >
          <option value="viewer">Viewer</option>
          <option value="editor">Editor</option>
        </select>
        <button
          disabled={!email || shareMutation.isPending}
          onClick={() => shareMutation.mutate()}
          className="btn-primary text-sm"
          id="share-invite-btn"
        >
          {shareMutation.isPending ? 'Inviting...' : 'Invite'}
        </button>
      </div>

      {/* Role explanation */}
      <div className="text-xs text-gray-500 bg-gray-50 rounded p-3 space-y-1">
        <p><strong>Viewer</strong> — can see all projections and valuation, cannot modify assumptions</p>
        <p><strong>Editor</strong> — can configure assumptions and run projections, cannot delete the project</p>
      </div>

      {/* Current shares */}
      {shares.length > 0 ? (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-700">Current Collaborators</h4>
          {shares.map((s: any) => (
            <div key={s.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
              <div>
                <p className="text-sm font-medium text-gray-800">{s.shared_with_email}</p>
                <p className="text-xs text-gray-400 capitalize">{s.role}</p>
              </div>
              <button
                onClick={() => {
                  if (confirm(`Revoke access for ${s.shared_with_email}?`))
                    revokeMutation.mutate(s.shared_with_user_id)
                }}
                className="text-xs text-red-500 hover:text-red-700"
              >
                Revoke
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-400">No collaborators yet. Invite someone above.</p>
      )}
    </div>
  )
}
