import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import LoginPage from './components/auth/LoginPage'
import RegisterPage from './components/auth/RegisterPage'
import Dashboard from './components/dashboard/Dashboard'
import ProjectSetup from './components/project/ProjectSetup'
import ProjectWorkspace from './components/project/ProjectWorkspace'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/projects/new" element={<PrivateRoute><ProjectSetup /></PrivateRoute>} />
      <Route path="/projects/:id/*" element={<PrivateRoute><ProjectWorkspace /></PrivateRoute>} />
    </Routes>
  )
}
