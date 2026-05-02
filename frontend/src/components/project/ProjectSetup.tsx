import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { projectsApi, sectorsApi } from '../../services/api'
import type { SectorOption } from '../../services/api'
import toast from 'react-hot-toast'

const CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR', 'BRL']
const SCALES = ['units', 'thousands', 'millions', 'billions']

interface FormData {
  name: string
  currency: string
  scale: string
  fiscal_year_end: string
  projection_years: number
  sector: string
}

export default function ProjectSetup() {
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<FormData>({
    defaultValues: { currency: 'USD', scale: 'thousands', projection_years: 5, sector: 'generic' },
  })
  const navigate = useNavigate()

  // Sector catalog drives the picker + the sector-aware first-pass model the
  // backend seeds once historicals are uploaded. Cached aggressively because
  // it's effectively static config.
  const { data: sectorGroups = [] } = useQuery({
    queryKey: ['sectors'],
    queryFn: () => sectorsApi.list().then(r => r.data),
    staleTime: Infinity,
  })

  const selectedSectorId = watch('sector')
  const selectedSector: SectorOption | undefined = sectorGroups
    .flatMap(g => g.sectors)
    .find(s => s.id === selectedSectorId)

  const onSubmit = async (data: FormData) => {
    try {
      const res = await projectsApi.create(data)
      toast.success('Project created!')
      navigate(`/projects/${res.data.id}`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create project')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-8">
      <div className="card w-full max-w-lg">
        <h1 className="text-xl font-bold mb-6">New Project</h1>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <div>
            <label className="label">Project Name</label>
            <input className="input" {...register('name', { required: 'Name is required' })} placeholder="e.g. Acme Corp Model" />
            {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>}
          </div>

          {/* Sector picker — drives the auto-seeded first-pass model so the
              user gets sensible defaults (growth, margin, capex %) instead of
              flat zeros. Optgroups keep the long list scannable. */}
          <div>
            <label className="label">Sector</label>
            <select className="input" {...register('sector')}>
              {sectorGroups.map(g => (
                <optgroup key={g.group} label={g.group}>
                  {g.sectors.map(s => (
                    <option key={s.id} value={s.id}>{s.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
            {selectedSector && (
              <div className="mt-2 text-xs text-gray-500 bg-gray-50 rounded px-3 py-2 space-y-1">
                <p>{selectedSector.description}</p>
                {selectedSector.key_kpis?.length > 0 && (
                  <p>
                    <span className="text-gray-400">Key KPIs: </span>
                    {selectedSector.key_kpis.join(' · ')}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Currency</label>
              <select className="input" {...register('currency')}>
                {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Scale</label>
              <select className="input" {...register('scale')}>
                {SCALES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="label">Fiscal Year End</label>
            <input type="date" className="input" {...register('fiscal_year_end')} />
          </div>

          <div>
            <label className="label">Projection Years: <span className="text-primary-600">{watch('projection_years')}</span></label>
            <input
              type="range" min={1} max={20} step={1}
              className="w-full"
              defaultValue={5}
              {...register('projection_years', { valueAsNumber: true })}
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>1</span><span>10</span><span>20</span>
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={() => navigate('/')} className="btn-secondary flex-1">
              Cancel
            </button>
            <button type="submit" disabled={isSubmitting} className="btn-primary flex-1">
              {isSubmitting ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
