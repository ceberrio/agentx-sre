/**
 * AuthInitializer — runs on app mount to validate any existing token.
 *
 * Flow:
 * 1. If no token in localStorage → render children immediately (unauthenticated).
 * 2. If token exists → call GET /auth/me to validate and populate the auth store.
 *    - 200: update user in store, then attempt to load kill switch state.
 *    - 401: apiClient interceptor already clears token and redirects to /login.
 *    - Other error: clear token and redirect to /login.
 * 3. Show full-screen Spinner during the check.
 *
 * Also calls GET /api/governance/thresholds to hydrate kill switch.
 * If 404 (not yet implemented), silently ignores.
 *
 * Security: no token values logged or exposed.
 */
import { type ReactNode, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { apiClient } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { useConfigStore } from '../store/configStore'
import { Spinner } from './ui'
import type { GovernanceThresholds, User } from '../api/types'

interface AuthInitializerProps {
  children: ReactNode
}

export function AuthInitializer({ children }: AuthInitializerProps) {
  const token = useAuthStore((s) => s.token)
  const login = useAuthStore((s) => s.login)
  const logout = useAuthStore((s) => s.logout)
  const setKillSwitch = useConfigStore((s) => s.setKillSwitch)
  const navigate = useNavigate()

  // Only block rendering if we have a token that needs verification
  const [checking, setChecking] = useState(token !== null)

  useEffect(() => {
    if (!token) {
      setChecking(false)
      return
    }

    let cancelled = false

    const verify = async () => {
      try {
        const { data: user } = await apiClient.get<User>('/auth/me')
        if (cancelled) return
        // Refresh user data in store (token stays the same)
        login(token, user)

        // Best-effort: load governance thresholds for kill switch
        try {
          const { data: thresholds } =
            await apiClient.get<GovernanceThresholds>('/governance/thresholds')
          if (!cancelled) {
            setKillSwitch(thresholds.kill_switch_enabled)
          }
        } catch {
          // 404 or not implemented — keep kill switch false
        }
      } catch (err: unknown) {
        if (cancelled) return
        // 401 is handled by the apiClient interceptor (clears token + redirects).
        // Any other error: clear session and send to login.
        if (axios.isAxiosError(err) && err.response?.status !== 401) {
          logout()
          navigate('/login', { replace: true })
        }
      } finally {
        if (!cancelled) setChecking(false)
      }
    }

    void verify()

    return () => {
      cancelled = true
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  // Intentionally run only on mount — token is the initial snapshot.

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50">
        <div className="flex flex-col items-center gap-4">
          <Spinner size="lg" label="Verifying session..." />
          <p className="text-sm text-neutral-500 font-montserrat">Verifying session…</p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
