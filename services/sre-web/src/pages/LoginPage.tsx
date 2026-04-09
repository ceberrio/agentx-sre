/**
 * LoginPage — authentication entry point.
 * AC-05: SoftServe logo prominently at top.
 * Mock Google auth: POST /api/auth/mock-google-login with demo email.
 * All text in English (AC-12, BR-06).
 *
 * Security: no credentials hardcoded — email entered by user at runtime.
 */
import { useState, type FormEvent } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { apiClient } from '../api/client'
import type { AuthResponse } from '../api/types'
import { Input, Button, Alert, Spinner } from '../components/ui'
import { useAuthStore } from '../store/authStore'
import axios from 'axios'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const login = useAuthStore((s) => s.login)
  const token = useAuthStore((s) => s.token)
  const navigate = useNavigate()

  // Already authenticated → redirect to dashboard
  if (token) {
    return <Navigate to="/dashboard" replace />
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!email.trim()) {
      setError('Please enter your SoftServe Google email address.')
      return
    }
    setIsLoading(true)
    setError(null)

    try {
      const { data } = await apiClient.post<AuthResponse>('/auth/mock-google-login', {
        email: email.trim(),
      })
      login(data.access_token, data.user)
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail as string | undefined
        setError(detail ?? 'Login failed. Please check your email and try again.')
      } else {
        setError('An unexpected error occurred. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Card */}
        <div className="bg-white rounded-lg shadow-lg px-8 py-10">
          {/* Logo — AC-05 */}
          <div className="flex justify-center mb-6">
            <img
              src="/assets/softserve-logo.svg"
              alt="SoftServe"
              className="h-10 w-auto"
            />
          </div>

          {/* Title */}
          <h1 className="text-2xl font-bold text-neutral-900 font-montserrat text-center mb-1">
            SRE Platform
          </h1>
          <p className="text-sm text-neutral-500 font-montserrat text-center mb-8">
            Sign in with your SoftServe Google account
          </p>

          {/* Error alert */}
          {error && (
            <div className="mb-4">
              <Alert type="error" message={error} onDismiss={() => setError(null)} />
            </div>
          )}

          {/* Login form */}
          <form onSubmit={(e) => void handleSubmit(e)} noValidate className="space-y-4">
            <Input
              label="Google Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your SoftServe Google email"
              autoComplete="email"
              required
            />

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={isLoading}
              className="w-full"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Spinner size="sm" />
                  Signing in…
                </span>
              ) : (
                'Sign in with Google'
              )}
            </Button>
          </form>

          {/* Mock auth notice */}
          <p className="text-center text-xs text-neutral-400 font-montserrat mt-4">
            🔒 Mock authentication — for demo purposes only
          </p>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-neutral-400 font-montserrat mt-6">
          &copy; 2025 SoftServe. All rights reserved.
        </p>
      </div>
    </div>
  )
}
