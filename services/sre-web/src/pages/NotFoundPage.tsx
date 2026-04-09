/**
 * NotFoundPage — 404 Page Not Found.
 * Rendered by the catch-all route in App.tsx.
 */
import { SearchX } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'

export function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col items-center justify-center text-center px-4">
      <div className="w-16 h-16 rounded-full bg-neutral-100 flex items-center justify-center mb-6">
        <SearchX size={32} className="text-neutral-400" />
      </div>

      <h1 className="text-4xl font-bold text-neutral-900 font-montserrat mb-3">
        Page Not Found
      </h1>

      <p className="text-neutral-500 font-montserrat max-w-sm mb-8">
        The page you&apos;re looking for doesn&apos;t exist.
      </p>

      <Button
        variant="primary"
        onClick={() => navigate('/dashboard', { replace: true })}
      >
        Back to Dashboard
      </Button>
    </div>
  )
}
