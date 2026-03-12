import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { projectsApi } from '../../services/api'
import { useAuthStore } from '../../store/authStore'
import toast from 'react-hot-toast'

const STATUS_BADGE: Record<string, string> = {
  draft: 'badge-draft',
  configured: 'badge-configured',
  projected: 'badge-projected',
  valued: 'badge-valued',
}

export default function Dashboard() {
  const { logout } = useAuthStore()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list().then(r => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => projectsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project deleted') },
    onError: () => toast.error('Failed to delete project'),
  })

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Delete "${name}"? This cannot be undone.`)) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">Financial Modeler</h1>
          <div className="flex gap-3">
            <button onClick={() => navigate('/projects/new')} className="btn-primary">
              + New Project
            </button>
            <button onClick={logout} className="btn-secondary">Log out</button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Your Projects</h2>

        {isLoading && <p className="text-gray-500">Loading...</p>}

        {!isLoading && projects.length === 0 && (
          <div className="card text-center py-16">
            <p className="text-gray-500 mb-4">No projects yet.</p>
            <button onClick={() => navigate('/projects/new')} className="btn-primary">
              Create your first project
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p: any) => (
            <div key={p.id} className="card hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <Link to={`/projects/${p.id}`} className="text-lg font-semibold text-gray-900 hover:text-primary-600">
                  {p.name}
                </Link>
                <span className={STATUS_BADGE[p.status] || 'badge-draft'}>{p.status}</span>
              </div>
              <div className="text-sm text-gray-500 space-y-1">
                <p>{p.currency} · {p.scale} · {p.projection_years}yr projection</p>
                <p>Updated {new Date(p.updated_at).toLocaleDateString()}</p>
              </div>
              <div className="mt-4 flex gap-2">
                <Link to={`/projects/${p.id}`} className="btn-primary text-sm flex-1 text-center">
                  Open
                </Link>
                <button
                  onClick={() => handleDelete(p.id, p.name)}
                  className="btn-secondary text-sm text-red-600 hover:text-red-700"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
