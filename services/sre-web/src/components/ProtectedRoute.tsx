/**
 * ProtectedRoute — role-based route guard.
 *
 * Rules:
 * - Not authenticated → redirect to /login.
 * - Authenticated but role not in allowedRoles → render 403 inline (ARC-022).
 * - Authenticated and authorized (or no role restriction) → render children.
 *
 * ARC-022: Role checks happen ONLY here, never inside page components.
 */
import { type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import type { UserRole } from '../api/types'
import { UnauthorizedPage } from '../pages/UnauthorizedPage'

interface ProtectedRouteProps {
  children: ReactNode
  allowedRoles?: UserRole[]
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const token = useAuthStore((s) => s.token)
  const user = useAuthStore((s) => s.user)

  // Not authenticated
  if (!token) {
    return <Navigate to="/login" replace />
  }

  // Role check — if allowedRoles is defined, user must have one of them
  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <UnauthorizedPage />
  }

  return <>{children}</>
}
