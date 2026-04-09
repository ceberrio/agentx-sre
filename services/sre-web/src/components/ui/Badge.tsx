/**
 * Badge — severity and status badges using semantic tokens.
 * AC-07: severity badges (CRITICAL/HIGH/MEDIUM/LOW).
 * AC-09: status badges (open/closed/processing/error + incident statuses).
 * AC-07: RoleBadge with role-specific colors.
 */
import { clsx } from 'clsx'
import type { Severity, BackendSeverity, UserRole } from '../../api/types'
import { SEVERITY_MAP } from '../../api/types'

// --- Severity Badge ---

const severityClasses: Record<Severity, string> = {
  CRITICAL: 'bg-semantic-error-light text-red-800 border border-semantic-error',
  HIGH: 'bg-semantic-warning-light text-amber-800 border border-semantic-warning',
  MEDIUM: 'bg-semantic-info-light text-blue-800 border border-semantic-info',
  LOW: 'bg-semantic-success-light text-green-800 border border-semantic-success',
}

interface SeverityBadgeProps {
  /** Accepts both display labels (CRITICAL/HIGH/MEDIUM/LOW) and backend codes (P1/P2/P3/P4). */
  severity: Severity | BackendSeverity
  className?: string
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  // Normalize backend P1/P2/P3/P4 → display label
  const displaySeverity: Severity =
    severity in SEVERITY_MAP
      ? SEVERITY_MAP[severity as BackendSeverity]
      : (severity as Severity)

  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-semibold font-montserrat uppercase tracking-wide',
        severityClasses[displaySeverity],
        className,
      )}
    >
      {displaySeverity}
    </span>
  )
}

// --- Status Badge (AC-09) ---

type DisplayStatus =
  | 'open'
  | 'closed'
  | 'processing'
  | 'error'
  | 'received'
  | 'triaging'
  | 'ticketed'
  | 'resolved'
  | 'blocked'
  | 'failed'
  | 'dismissed'

const statusClasses: Record<DisplayStatus, string> = {
  open: 'bg-semantic-warning-light text-amber-800',
  closed: 'bg-neutral-100 text-neutral-600',
  processing: 'bg-semantic-info-light text-blue-800',
  error: 'bg-semantic-error-light text-red-800',
  // Current backend IncidentStatus values
  received: 'bg-semantic-info-light text-blue-800',
  triaging: 'bg-semantic-info-light text-blue-800',
  ticketed: 'bg-semantic-success-light text-green-800',
  resolved: 'bg-semantic-success-light text-green-800',
  blocked: 'bg-semantic-warning-light text-amber-800',
  failed: 'bg-semantic-error-light text-red-800',
  dismissed: 'bg-neutral-100 text-neutral-600',
}

const statusLabels: Record<DisplayStatus, string> = {
  open: 'Open',
  closed: 'Closed',
  processing: 'Processing',
  error: 'Error',
  received: 'Received',
  triaging: 'Triaging',
  ticketed: 'Ticketed',
  resolved: 'Resolved',
  blocked: 'Blocked',
  failed: 'Failed',
  dismissed: 'Dismissed',
}

interface StatusBadgeProps {
  status: DisplayStatus
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium font-montserrat',
        statusClasses[status],
        className,
      )}
    >
      {statusLabels[status] ?? status}
    </span>
  )
}

// --- Role Badge (AC-07) ---

const roleClasses: Record<UserRole, string> = {
  // AC-07: superadmin = Victoria purple (#454494)
  superadmin: 'bg-brand-lighter text-brand-primary border border-brand-primary',
  admin: 'bg-orange-100 text-orange-800 border border-orange-300',
  flow_configurator: 'bg-sky-100 text-sky-800 border border-sky-300',
  operator: 'bg-green-100 text-green-800 border border-green-300',
  viewer: 'bg-neutral-100 text-neutral-600 border border-neutral-300',
}

const roleLabels: Record<UserRole, string> = {
  superadmin: 'Super Admin',
  admin: 'Admin',
  flow_configurator: 'Flow Configurator',
  operator: 'Operator',
  viewer: 'Viewer',
}

interface RoleBadgeProps {
  role: UserRole
  className?: string
}

export function RoleBadge({ role, className }: RoleBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold font-montserrat',
        roleClasses[role],
        className,
      )}
    >
      {roleLabels[role]}
    </span>
  )
}
