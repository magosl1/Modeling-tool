import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import ErrorBoundary from './components/common/ErrorBoundary'
import LoginPage from './components/auth/LoginPage'
import RegisterPage from './components/auth/RegisterPage'
import AISettingsPanel from './components/auth/AISettingsPanel'
import ProfilePage from './components/auth/ProfilePage'
import AdminPage from './components/admin/AdminPage'
import Dashboard from './components/dashboard/Dashboard'
import ProjectSetup from './components/project/ProjectSetup'
import ProjectWorkspace from './components/project/ProjectWorkspace'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <Navigate to="/" replace /> : <>{children}</>
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
        <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/profile" element={<PrivateRoute><ProfilePage /></PrivateRoute>} />
        <Route path="/admin" element={<PrivateRoute><AdminPage /></PrivateRoute>} />
        <Route path="/settings/ai" element={<PrivateRoute><AISettingsPanel /></PrivateRoute>} />
        <Route path="/projects/new" element={<PrivateRoute><ProjectSetup /></PrivateRoute>} />
        {/*
          /projects/:id                     → Project workspace (entity tree + single entity view)
          /projects/:id/entities/:entityId  → Entity-specific workspace
          /projects/:id/consolidated        → Consolidated view (multi_entity)
        */}
        <Route path="/projects/:id/*" element={<PrivateRoute><ProjectWorkspace /></PrivateRoute>} />
      </Routes>
    </ErrorBoundary>
  )
}
