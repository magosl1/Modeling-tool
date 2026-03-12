import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../../services/api'
import { useAuthStore } from '../../store/authStore'
import toast from 'react-hot-toast'

interface FormData { email: string; password: string; name: string }

export default function RegisterPage() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>()
  const { setTokens } = useAuthStore()
  const navigate = useNavigate()

  const onSubmit = async (data: FormData) => {
    try {
      const res = await authApi.register(data)
      setTokens(res.data.access_token, res.data.refresh_token)
      navigate('/')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Registration failed')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Financial Modeler</h1>
        <h2 className="text-lg font-semibold mb-4">Create Account</h2>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label">Name</label>
            <input className="input" {...register('name', { required: true })} />
          </div>
          <div>
            <label className="label">Email</label>
            <input type="email" className="input" {...register('email', { required: true })} />
          </div>
          <div>
            <label className="label">Password</label>
            <input type="password" className="input" {...register('password', { required: true, minLength: 8 })} />
            {errors.password && <p className="text-red-500 text-xs mt-1">Minimum 8 characters</p>}
          </div>
          <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
            {isSubmitting ? 'Creating account...' : 'Create Account'}
          </button>
        </form>
        <p className="mt-4 text-sm text-gray-600">
          Already have an account? <Link to="/login" className="text-primary-600 hover:underline">Sign In</Link>
        </p>
      </div>
    </div>
  )
}
