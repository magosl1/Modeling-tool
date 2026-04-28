import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { authApi } from '../../services/api'
import { useAuthStore } from '../../store/authStore'

function passwordIssues(pw: string): string[] {
  const issues: string[] = []
  if (pw.length < 8) issues.push('At least 8 characters')
  if (!/[A-Z]/.test(pw)) issues.push('One uppercase letter')
  if (!/\d/.test(pw)) issues.push('One digit')
  return issues
}

export default function ProfilePage() {
  const navigate = useNavigate()
  const { setTokens, logout } = useAuthStore()

  const { data: me, isLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => authApi.me().then((r) => r.data),
  })

  // Change password state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const changePwMutation = useMutation({
    mutationFn: () =>
      authApi.changePassword({ current_password: currentPassword, new_password: newPassword }),
    onSuccess: (res) => {
      setTokens(res.data.access_token, res.data.refresh_token)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      toast.success('Password updated. Other devices have been signed out.')
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to change password')
    },
  })

  const handleChangePassword = (e: React.FormEvent) => {
    e.preventDefault()
    const issues = passwordIssues(newPassword)
    if (issues.length > 0) {
      toast.error('New password is too weak: ' + issues.join(', '))
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error('New password and confirmation do not match')
      return
    }
    if (newPassword === currentPassword) {
      toast.error('New password must differ from the current one')
      return
    }
    changePwMutation.mutate()
  }

  // Delete account state
  const [showDelete, setShowDelete] = useState(false)
  const [deleteEmail, setDeleteEmail] = useState('')
  const [deletePassword, setDeletePassword] = useState('')

  const deleteMutation = useMutation({
    mutationFn: () =>
      authApi.deleteAccount({ email_confirmation: deleteEmail, password: deletePassword }),
    onSuccess: () => {
      toast.success('Account deleted')
      logout()
      navigate('/login', { replace: true })
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to delete account')
    },
  })

  const handleDelete = (e: React.FormEvent) => {
    e.preventDefault()
    if (!me) return
    if (deleteEmail.trim().toLowerCase() !== me.email.toLowerCase()) {
      toast.error('Email confirmation does not match your account email')
      return
    }
    if (!confirm('This will deactivate your account and sign you out. Continue?')) return
    deleteMutation.mutate()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="text-sm text-gray-500 hover:text-gray-900"
          >
            ← Dashboard
          </button>
          <h1 className="text-lg font-semibold text-gray-900">Profile</h1>
          <div className="w-20" />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <section className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Account</h2>
          {isLoading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : me ? (
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-y-3 text-sm">
              <dt className="text-gray-500">Name</dt>
              <dd className="text-gray-900 font-medium">{me.name}</dd>
              <dt className="text-gray-500">Email</dt>
              <dd className="text-gray-900 font-medium">{me.email}</dd>
              <dt className="text-gray-500">Auth provider</dt>
              <dd className="text-gray-900 font-medium capitalize">{me.auth_provider}</dd>
              {me.created_at && (
                <>
                  <dt className="text-gray-500">Member since</dt>
                  <dd className="text-gray-900 font-medium">
                    {new Date(me.created_at).toLocaleDateString()}
                  </dd>
                </>
              )}
            </dl>
          ) : (
            <p className="text-sm text-red-500">Could not load account.</p>
          )}
        </section>

        <section className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Change password</h2>
          <p className="text-sm text-gray-500 mb-4">
            Changing your password will sign out all other sessions on every device.
          </p>
          <form onSubmit={handleChangePassword} className="space-y-4 max-w-md">
            <div>
              <label className="label" htmlFor="current_password">Current password</label>
              <input
                id="current_password"
                type="password"
                autoComplete="current-password"
                className="input"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="new_password">New password</label>
              <input
                id="new_password"
                type="password"
                autoComplete="new-password"
                className="input"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
              {newPassword.length > 0 && passwordIssues(newPassword).length > 0 && (
                <ul className="mt-2 text-xs text-amber-600 list-disc list-inside">
                  {passwordIssues(newPassword).map((i) => (
                    <li key={i}>Missing: {i}</li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <label className="label" htmlFor="confirm_password">Confirm new password</label>
              <input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                className="input"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
              {confirmPassword.length > 0 && confirmPassword !== newPassword && (
                <p className="mt-2 text-xs text-red-500">Passwords do not match</p>
              )}
            </div>
            <button
              type="submit"
              disabled={changePwMutation.isPending}
              className="btn-primary"
            >
              {changePwMutation.isPending ? 'Updating…' : 'Update password'}
            </button>
          </form>
        </section>

        <section className="card border-red-200">
          <h2 className="text-lg font-semibold text-red-700 mb-1">Danger zone</h2>
          <p className="text-sm text-gray-600 mb-4">
            Deleting your account deactivates access immediately. Your data is retained for audit
            purposes for a limited window before permanent removal.
          </p>
          {!showDelete ? (
            <button
              onClick={() => setShowDelete(true)}
              className="btn-secondary border-red-300 text-red-700 hover:bg-red-50"
            >
              Delete my account
            </button>
          ) : (
            <form onSubmit={handleDelete} className="space-y-4 max-w-md">
              <p className="text-sm text-gray-700">
                Type your email <span className="font-mono">{me?.email}</span> and your password to
                confirm.
              </p>
              <div>
                <label className="label" htmlFor="delete_email">Email confirmation</label>
                <input
                  id="delete_email"
                  type="email"
                  className="input"
                  value={deleteEmail}
                  onChange={(e) => setDeleteEmail(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="label" htmlFor="delete_password">Password</label>
                <input
                  id="delete_password"
                  type="password"
                  autoComplete="current-password"
                  className="input"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  required
                />
              </div>
              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={deleteMutation.isPending}
                  className="btn-primary bg-red-600 hover:bg-red-700"
                >
                  {deleteMutation.isPending ? 'Deleting…' : 'Permanently delete account'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowDelete(false)
                    setDeleteEmail('')
                    setDeletePassword('')
                  }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </section>
      </main>
    </div>
  )
}
