import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { adminApi, authApi, type AdminStats, type AdminUser } from '../../services/api'

function StatCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wide text-gray-500 font-medium">{label}</div>
      <div className="text-3xl font-semibold text-gray-900 mt-1 tabular-nums">{value}</div>
      {hint && <div className="text-xs text-gray-400 mt-1">{hint}</div>}
    </div>
  )
}

function BreakdownCard({ label, items }: { label: string; items: Record<string, number> }) {
  const total = Object.values(items).reduce((a, b) => a + b, 0) || 1
  const entries = Object.entries(items).sort((a, b) => b[1] - a[1])
  return (
    <div className="card">
      <div className="text-sm font-semibold text-gray-700 mb-3">{label}</div>
      {entries.length === 0 ? (
        <div className="text-xs text-gray-400">No data</div>
      ) : (
        <ul className="space-y-2">
          {entries.map(([k, v]) => {
            const pct = (v / total) * 100
            return (
              <li key={k}>
                <div className="flex justify-between text-xs text-gray-600 mb-1">
                  <span className="capitalize">{k.replace(/_/g, ' ')}</span>
                  <span className="tabular-nums font-medium text-gray-900">{v}</span>
                </div>
                <div className="h-1.5 w-full bg-gray-100 rounded">
                  <div
                    className="h-full bg-primary-500 rounded"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function StatsSection({ stats }: { stats: AdminStats }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Active users"
          value={stats.users_active}
          hint={`${stats.users_total} total · +${stats.users_new_30d} last 30d`}
        />
        <StatCard
          label="Projects"
          value={stats.projects_total}
          hint={`+${stats.projects_new_30d} last 30d`}
        />
        <StatCard label="Entities" value={stats.entities_total} />
        <StatCard
          label="Historical rows"
          value={stats.historical_rows.toLocaleString()}
          hint="data points stored"
        />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Uploads — total" value={stats.uploads_total} />
        <StatCard label="Uploads — validated" value={stats.uploads_validated} />
        <StatCard label="Uploads — rejected" value={stats.uploads_rejected} />
        <StatCard label="Uploads — pending" value={stats.uploads_pending} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <BreakdownCard label="Projects by status" items={stats.projects_by_status} />
        <BreakdownCard label="Entities by type" items={stats.entities_by_type} />
        <BreakdownCard
          label="Roles"
          items={{
            user: stats.users_active - stats.users_admins - stats.users_master_admins,
            admin: stats.users_admins,
            master_admin: stats.users_master_admins,
          }}
        />
      </div>
    </div>
  )
}

function UsersSection({ canMutate }: { canMutate: boolean }) {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [role, setRole] = useState<string>('')
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'users', q, role, includeDeleted, page],
    queryFn: () =>
      adminApi
        .listUsers({
          q: q || undefined,
          role: role || undefined,
          include_deleted: includeDeleted,
          page,
          page_size: 25,
        })
        .then((r) => r.data),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { role?: AdminUser['role']; deactivate?: boolean } }) =>
      adminApi.updateUser(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'users'] })
      qc.invalidateQueries({ queryKey: ['admin', 'stats'] })
      toast.success('User updated')
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || 'Failed to update user'),
  })

  return (
    <div className="card">
      <div className="flex flex-col md:flex-row md:items-center gap-3 mb-4">
        <input
          className="input md:w-64"
          placeholder="Search email or name…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setPage(1)
          }}
        />
        <select
          className="input md:w-40"
          value={role}
          onChange={(e) => {
            setRole(e.target.value)
            setPage(1)
          }}
        >
          <option value="">All roles</option>
          <option value="user">user</option>
          <option value="admin">admin</option>
          <option value="master_admin">master_admin</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={includeDeleted}
            onChange={(e) => {
              setIncludeDeleted(e.target.checked)
              setPage(1)
            }}
          />
          Include deactivated
        </label>
        <div className="md:ml-auto text-xs text-gray-500">
          {data ? `${data.total} users` : ''}
        </div>
      </div>

      {isLoading ? (
        <div className="text-sm text-gray-500">Loading…</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-gray-500 border-b border-gray-200">
                <th className="px-3 py-2 font-medium">Email</th>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium text-right">Projects</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2 font-medium">Status</th>
                {canMutate && <th className="px-3 py-2 font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data?.items.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-medium text-gray-900">{u.email}</td>
                  <td className="px-3 py-2 text-gray-700">{u.name}</td>
                  <td className="px-3 py-2">
                    {canMutate ? (
                      <select
                        className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
                        value={u.role}
                        disabled={updateMutation.isPending || u.deleted_at !== null}
                        onChange={(e) =>
                          updateMutation.mutate({
                            id: u.id,
                            data: { role: e.target.value as AdminUser['role'] },
                          })
                        }
                      >
                        <option value="user">user</option>
                        <option value="admin">admin</option>
                        <option value="master_admin">master_admin</option>
                      </select>
                    ) : (
                      <span className="text-gray-700">{u.role}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-gray-700">
                    {u.project_count}
                  </td>
                  <td className="px-3 py-2 text-gray-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-3 py-2">
                    {u.deleted_at ? (
                      <span className="px-2 py-0.5 rounded text-xs bg-red-50 text-red-700 border border-red-100">
                        deactivated
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-xs bg-green-50 text-green-700 border border-green-100">
                        active
                      </span>
                    )}
                  </td>
                  {canMutate && (
                    <td className="px-3 py-2">
                      {u.deleted_at ? (
                        <button
                          className="text-xs text-gray-700 hover:text-gray-900"
                          onClick={() =>
                            updateMutation.mutate({ id: u.id, data: { deactivate: false } })
                          }
                        >
                          Restore
                        </button>
                      ) : (
                        <button
                          className="text-xs text-red-600 hover:text-red-700"
                          onClick={() => {
                            if (confirm(`Deactivate ${u.email}? Their tokens will be revoked.`)) {
                              updateMutation.mutate({ id: u.id, data: { deactivate: true } })
                            }
                          }}
                        >
                          Deactivate
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {data && data.total > data.page_size && (
            <div className="flex items-center justify-between mt-4 text-xs text-gray-500">
              <span>
                Page {data.page} of {Math.ceil(data.total / data.page_size)}
              </span>
              <div className="flex gap-2">
                <button
                  className="btn-secondary text-xs"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  Prev
                </button>
                <button
                  className="btn-secondary text-xs"
                  disabled={page * data.page_size >= data.total}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AdminPage() {
  const navigate = useNavigate()

  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => authApi.me().then((r) => r.data),
  })

  const isAdmin = me?.role === 'admin' || me?.role === 'master_admin'
  const isMaster = me?.role === 'master_admin'

  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: () => adminApi.stats().then((r) => r.data),
    enabled: isAdmin,
  })

  if (meLoading) {
    return (
      <div className="min-h-screen bg-gray-50 grid place-items-center text-sm text-gray-500">
        Loading…
      </div>
    )
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-gray-50 grid place-items-center">
        <div className="card max-w-md text-center">
          <h2 className="text-lg font-semibold text-gray-900">Admin only</h2>
          <p className="text-sm text-gray-500 mt-2">
            You do not have permission to access this area.
          </p>
          <button onClick={() => navigate('/')} className="btn-primary mt-4">
            Back to dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="text-sm text-gray-500 hover:text-gray-900"
          >
            ← Dashboard
          </button>
          <h1 className="text-lg font-semibold text-gray-900">Admin</h1>
          <span className="text-xs text-gray-500 capitalize">
            Signed in as {me?.role.replace('_', ' ')}
          </span>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Usage
          </h2>
          {statsLoading ? (
            <div className="text-sm text-gray-500">Loading stats…</div>
          ) : statsError ? (
            <div className="text-sm text-red-500">Failed to load stats.</div>
          ) : stats ? (
            <StatsSection stats={stats} />
          ) : null}
        </section>

        <section>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Users
          </h2>
          <UsersSection canMutate={isMaster} />
        </section>
      </main>
    </div>
  )
}
