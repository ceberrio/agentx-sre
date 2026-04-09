/**
 * UnauthorizedPage — 403 Access Denied.
 * Rendered inline by ProtectedRoute when the user's role is not allowed.
 * Shows current role so the user understands why access was denied.
 */
import { Lock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Layout } from '../components/ui/Layout'
import { Button } from '../components/ui/Button'
import { RoleBadge } from '../components/ui/Badge'
import { useAuthStore } from '../store/authStore'

export function UnauthorizedPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)

  return (
    <Layout pageTitle="Access Denied">
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="w-16 h-16 rounded-full bg-semantic-error-light flex items-center justify-center mb-6">
          <Lock size={32} className="text-semantic-error" />
        </div>

        <h1 className="text-3xl font-bold text-neutral-900 font-montserrat mb-3">
          Access Denied
        </h1>

        <p className="text-neutral-600 font-montserrat max-w-md mb-6">
          You don&apos;t have permission to access this page. Contact your administrator
          to request access.
        </p>

        {user && (
          <div className="flex items-center gap-2 mb-8">
            <span className="text-sm text-neutral-500 font-montserrat">
              Your current role:
            </span>
            <RoleBadge role={user.role} />
          </div>
        )}

        <Button
          variant="primary"
          onClick={() => navigate('/dashboard', { replace: true })}
        >
          Go to Dashboard
        </Button>
      </div>
    </Layout>
  )
}
