import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { projectsApi } from '../../services/api'
import toast from 'react-hot-toast'

const CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY', 'INR', 'BRL']
const SCALES = ['units', 'thousands', 'millions', 'billions']

interface FormData {
  name: string
  currency: string
  scale: string
  fiscal_year_end: string
  projection_years: number
}

export default function ProjectSetup() {
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<FormData>({
    defaultValues: { currency: 'USD', scale: 'thousands', projection_years: 5 },
  })
  const navigate = useNavigate()

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
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="card w-full max-w-lg">
        <h1 className="text-xl font-bold mb-6">New Project</h1>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <div>
            <label className="label">Project Name</label>
            <input className="input" {...register('name', { required: 'Name is required' })} placeholder="e.g. Acme Corp Model" />
            {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>}
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
