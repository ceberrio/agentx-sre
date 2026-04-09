/**
 * KillSwitchBanner — full-width sticky banner shown when kill switch is active.
 * Uses semantic.error background. Sticky at top, z-index above everything.
 */
import { AlertTriangle } from 'lucide-react'
import { useConfigStore } from '../../store/configStore'

export function KillSwitchBanner() {
  const killSwitchEnabled = useConfigStore((s) => s.killSwitchEnabled)

  if (!killSwitchEnabled) return null

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="sticky top-0 z-50 w-full bg-semantic-error text-white px-4 py-2.5 flex items-center justify-center gap-2"
    >
      <AlertTriangle size={18} className="flex-shrink-0" aria-hidden="true" />
      <p className="text-sm font-semibold font-montserrat text-center">
        KILL SWITCH ACTIVE &mdash; Automated incident processing is paused. All
        incidents require manual review.
      </p>
    </div>
  )
}
