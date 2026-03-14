import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../../services/api'
import { useAuthStore } from '../../store/authStore'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<{ email: string; password: string }>()
  const { setTokens } = useAuthStore()
  const navigate = useNavigate()

  const onSubmit = async (data: { email: string; password: string }) => {
    try {
      const res = await authApi.login(data)
      setTokens(res.data.access_token, res.data.refresh_token)
      navigate('/')
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      toast.error(axiosErr.response?.data?.detail || 'Login failed')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Financial Modeler</h1>
        <h2 className="text-lg font-semibold mb-4">Sign In</h2>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label">Email</label>
            <input
              type="email"
              className="input"
              {...register('email', { required: 'Email is required' })}
            />
            {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>}
          </div>
          <div>
            <label className="label">Password</label>
            <input
              type="password"
              className="input"
              {...register('password', { required: 'Password is required' })}
            />
          </div>
          <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
            {isSubmitting ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        <p className="mt-4 text-sm text-gray-600">
          No account? <Link to="/register" className="text-primary-600 hover:underline">Register</Link>
        </p>
      </div>
    </div>
  )
}
