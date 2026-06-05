import { Navigate } from 'react-router-dom'
import { ReactNode } from 'react'
import { useAuth } from '../hooks/useAuth'

interface AuthGuardProps {
  children: ReactNode
  allowedRoles?: string[]
}

export function AuthGuard({ children, allowedRoles }: AuthGuardProps) {
  const { user, loading } = useAuth()

  if (loading) return <div data-testid="auth-loading">載入中…</div>
  if (!user) return <Navigate to="/login" replace />
  if (user.role === 'pending') return <Navigate to="/pending" replace />
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}
