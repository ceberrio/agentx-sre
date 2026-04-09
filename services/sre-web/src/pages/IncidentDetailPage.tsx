/**
 * IncidentDetailPage — detailed view of a single incident.
 *
 * AC-02: Shows all incident fields, triage/ticket unavailability notice.
 * AC-03: Resolved section shown only when status === 'resolved'; blocked_reason when blocked.
 * AC-04: Auto-polls GET /incidents/{id} every 30 s via refetchInterval in useIncident.
 * AC-05: Prominent green resolved alert when status === 'resolved'.
 * AC-06: FeedbackWidget — POST /feedback on submit.
 */
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Activity, ArrowLeft, AlertTriangle, Info } from 'lucide-react'
import { getApiErrorDetail } from '../api/errors'
import { Layout } from '../components/ui/Layout'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { Modal } from '../components/ui/Modal'
import { SeverityBadge, StatusBadge } from '../components/ui/Badge'
import { FeedbackWidget } from '../components/ui/FeedbackWidget'
import { useIncident, useResolveIncident, useSubmitFeedback } from '../api/hooks/useIncidents'
import { SEVERITY_MAP } from '../api/types'
import type { FeedbackRating } from '../api/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 py-2 border-b border-neutral-50 last:border-b-0">
      <span className="text-xs font-medium text-neutral-500 font-montserrat uppercase tracking-wide">
        {label}
      </span>
      <div className="text-sm text-neutral-800 font-montserrat">{children}</div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function IncidentDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: incident, isLoading, isError, error } = useIncident(id)
  const resolveIncident = useResolveIncident()
  const submitFeedback = useSubmitFeedback()

  const [confirmResolveOpen, setConfirmResolveOpen] = useState(false)
  const [resolveError, setResolveError] = useState<string | null>(null)
  const [resolveSuccess, setResolveSuccess] = useState(false)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)

  // Error message extraction — never expose raw objects to the UI.
  const errorMessage = isError ? getApiErrorDetail(error, 'Failed to load incident.') : null

  // ---- Handlers ----

  async function handleResolve() {
    setConfirmResolveOpen(false)
    setResolveError(null)
    setResolveSuccess(false)
    try {
      await resolveIncident.mutateAsync(id)
      setResolveSuccess(true)
    } catch (err: unknown) {
      setResolveError(getApiErrorDetail(err, 'Resolution failed. Please try again.'))
    }
  }

  async function handleFeedbackSubmit(rating: FeedbackRating, comment?: string): Promise<void> {
    setFeedbackError(null)
    try {
      await submitFeedback.mutateAsync({
        incident_id: id,
        rating,
        comment: comment ?? '',
      })
    } catch (err: unknown) {
      setFeedbackError(getApiErrorDetail(err, 'Failed to submit feedback.'))
      throw err  // re-throw so FeedbackWidget can also update its internal error state
    }
  }

  // ---- Loading state ----
  if (isLoading) {
    return (
      <Layout pageTitle="Incident Detail">
        <div className="flex items-center justify-center py-24">
          <Spinner size="lg" label="Loading incident..." />
        </div>
      </Layout>
    )
  }

  // ---- Error state ----
  if (isError || !incident) {
    return (
      <Layout pageTitle="Incident Detail">
        <Button
          variant="ghost"
          onClick={() => navigate('/incidents')}
          className="flex items-center gap-2 mb-4"
        >
          <ArrowLeft size={16} />
          Back to Incidents
        </Button>
        <Alert
          type="error"
          title="Unable to load incident"
          message={errorMessage ?? 'Incident not found.'}
        />
      </Layout>
    )
  }

  const isResolved = incident.status === 'resolved'
  const isBlocked = incident.blocked
  const isTicketedOrResolved = incident.status === 'ticketed' || incident.status === 'resolved'

  return (
    <Layout pageTitle="Incident Detail">
      {/* Back button */}
      <Button
        variant="ghost"
        onClick={() => navigate('/incidents')}
        className="flex items-center gap-2 mb-4"
      >
        <ArrowLeft size={16} />
        Back to Incidents
      </Button>

      {/* Page header */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Activity size={24} className="text-brand-primary flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
              Incident #{id.slice(0, 8)}
            </h1>
            {/* AC-05: Prominent status badge */}
            <StatusBadge status={incident.status} className="text-sm px-3 py-1" />
          </div>
          <p className="text-sm text-neutral-500 font-montserrat mt-0.5 truncate">
            {incident.title}
          </p>
        </div>
      </div>

      {/* AC-05: Resolved alert */}
      {isResolved && (
        <div className="mb-4">
          <Alert
            type="success"
            title="Incident Resolved"
            message="This incident has been successfully resolved."
          />
        </div>
      )}

      {/* AC-03: Blocked alert */}
      {isBlocked && (
        <div className="mb-4">
          <Alert
            type="warning"
            title="Intake Blocked"
            message={incident.blocked_reason ?? 'This incident was blocked during intake.'}
          />
        </div>
      )}

      {/* Resolution success feedback */}
      {resolveSuccess && !isResolved && (
        <div className="mb-4">
          <Alert
            type="success"
            message="Resolution triggered successfully. Status will update shortly."
            onDismiss={() => setResolveSuccess(false)}
          />
        </div>
      )}

      {/* Resolution error */}
      {resolveError && (
        <div className="mb-4">
          <Alert
            type="error"
            message={resolveError}
            onDismiss={() => setResolveError(null)}
          />
        </div>
      )}

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Incident Details — AC-02 */}
        <Card title="Incident Details">
          <div className="space-y-0">
            <DetailRow label="Title">{incident.title}</DetailRow>
            <DetailRow label="Description">
              <p className="whitespace-pre-wrap leading-relaxed">{incident.description}</p>
            </DetailRow>
            <DetailRow label="Reporter Email">{incident.reporter_email}</DetailRow>
            <DetailRow label="Severity">
              {incident.severity ? (
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={incident.severity} />
                  <span className="text-xs text-neutral-400 font-montserrat">
                    ({SEVERITY_MAP[incident.severity]})
                  </span>
                </div>
              ) : (
                <span className="text-neutral-400">Not assigned</span>
              )}
            </DetailRow>
            <DetailRow label="Status">
              <StatusBadge status={incident.status} />
            </DetailRow>
            <DetailRow label="Has Log File">
              {incident.has_log ? (
                <span className="text-semantic-success font-medium">Yes</span>
              ) : (
                <span className="text-neutral-400">No</span>
              )}
            </DetailRow>
            <DetailRow label="Created At">{formatDate(incident.created_at)}</DetailRow>
            <DetailRow label="Updated At">{formatDate(incident.updated_at)}</DetailRow>
          </div>
        </Card>

        {/* Triage & Ticket — AC-02 */}
        <Card title="Triage &amp; Ticket">
          <div className="space-y-4">
            <div className="flex gap-3 p-3 bg-neutral-50 rounded-md">
              <Info size={16} className="text-neutral-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-neutral-600 font-montserrat leading-relaxed">
                Triage analysis details and ticket information are generated during pipeline
                processing and are not stored in this API version. Check the terminal logs
                or Langfuse for full trace details.
              </p>
            </div>

            {isTicketedOrResolved && (
              <div className="flex items-center gap-2 p-3 bg-semantic-success-light rounded-md border border-semantic-success">
                <span className="text-sm font-medium text-green-800 font-montserrat">
                  Ticket created successfully
                </span>
              </div>
            )}

            {/* AC-03: Resolved section */}
            {isResolved && (
              <div className="flex items-center gap-2 p-3 bg-semantic-success-light rounded-md border border-semantic-success">
                <span className="text-sm font-medium text-green-800 font-montserrat">
                  Resolution recorded — incident closed.
                </span>
              </div>
            )}

            {/* AC-03: Blocked reason */}
            {isBlocked && incident.blocked_reason && (
              <div className="p-3 bg-semantic-warning-light rounded-md border border-semantic-warning">
                <p className="text-xs font-medium text-amber-800 font-montserrat uppercase tracking-wide mb-1">
                  Blocked Reason
                </p>
                <p className="text-sm text-amber-800 font-montserrat">
                  {incident.blocked_reason}
                </p>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Actions */}
      {!isResolved && (
        <div className="mb-4">
          <Card title="Actions">
            <div className="flex items-center gap-4">
              <Button
                variant="danger"
                onClick={() => setConfirmResolveOpen(true)}
                loading={resolveIncident.isPending}
                disabled={resolveIncident.isPending}
              >
                <AlertTriangle size={16} className="mr-2" />
                Trigger Resolution
              </Button>
              <p className="text-xs text-neutral-500 font-montserrat">
                Manually mark this incident as resolved and notify stakeholders.
              </p>
            </div>
          </Card>
        </div>
      )}

      {/* AC-06: Feedback widget */}
      {feedbackError && (
        <div className="mb-4">
          <Alert
            type="error"
            message={feedbackError}
            onDismiss={() => setFeedbackError(null)}
          />
        </div>
      )}
      <Card title="Feedback">
        <FeedbackWidget
          incidentId={id}
          onSubmit={handleFeedbackSubmit}
        />
      </Card>

      {/* Resolve confirmation modal */}
      <Modal
        isOpen={confirmResolveOpen}
        onClose={() => setConfirmResolveOpen(false)}
        title="Confirm Resolution"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmResolveOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => void handleResolve()}
              loading={resolveIncident.isPending}
            >
              Resolve Incident
            </Button>
          </>
        }
      >
        <p className="text-sm text-neutral-700 font-montserrat">
          This will trigger resolution for incident{' '}
          <span className="font-mono font-semibold">#{id.slice(0, 8)}</span>.
        </p>
        <p className="text-sm text-neutral-500 font-montserrat mt-3">
          Are you sure you want to proceed? This action cannot be undone.
        </p>
      </Modal>
    </Layout>
  )
}
