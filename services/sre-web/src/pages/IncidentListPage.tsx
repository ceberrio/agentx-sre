/**
 * IncidentListPage — list of all incidents with client-side RBAC filtering,
 * severity/status filtering, and pagination.
 *
 * AC-01: List columns — ID, Title, Severity, Status, Reporter, Created.
 * AC-07: Operators see only their own incidents (client-side filter).
 * AC-08: 20-per-page pagination + severity/status filter bar.
 */
import { useState, useMemo } from 'react'
import { AlertTriangle, Plus, ChevronLeft, ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getApiErrorDetail } from '../api/errors'
import { Layout } from '../components/ui/Layout'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Table } from '../components/ui/Table'
import { SeverityBadge, StatusBadge } from '../components/ui/Badge'
import { Alert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { Select } from '../components/ui/Select'
import { useIncidents } from '../api/hooks/useIncidents'
import { useAuthStore } from '../store/authStore'
import type { Incident, BackendSeverity, IncidentStatus } from '../api/types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20

const SEVERITY_FILTER_OPTIONS = [
  { value: 'ALL', label: 'All Severities' },
  { value: 'P1', label: 'P1 — Critical' },
  { value: 'P2', label: 'P2 — High' },
  { value: 'P3', label: 'P3 — Medium' },
  { value: 'P4', label: 'P4 — Low' },
]

const STATUS_FILTER_OPTIONS = [
  { value: 'ALL', label: 'All Statuses' },
  { value: 'received', label: 'Received' },
  { value: 'triaging', label: 'Triaging' },
  { value: 'ticketed', label: 'Ticketed' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'failed', label: 'Failed' },
]

// ---------------------------------------------------------------------------
// Table columns
// ---------------------------------------------------------------------------

function buildColumns(navigate: (path: string) => void) {
  return [
    {
      key: 'id',
      header: 'ID',
      render: (row: Incident) => (
        <span className="font-mono text-xs text-neutral-600">{row.id.slice(0, 8)}&hellip;</span>
      ),
    },
    {
      key: 'title',
      header: 'Title',
      render: (row: Incident) => (
        <span className="text-sm text-neutral-800 font-montserrat">{row.title}</span>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (row: Incident) =>
        row.severity ? (
          <SeverityBadge severity={row.severity} />
        ) : (
          <span className="text-xs text-neutral-400 font-montserrat">—</span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: Incident) => <StatusBadge status={row.status} />,
    },
    {
      key: 'reporter_email',
      header: 'Reporter',
      render: (row: Incident) => (
        <span className="text-sm text-neutral-600 font-montserrat">{row.reporter_email}</span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row: Incident) => (
        <span className="text-xs text-neutral-500 font-montserrat">
          {new Date(row.created_at).toLocaleString('en-US', {
            dateStyle: 'medium',
            timeStyle: 'short',
          })}
        </span>
      ),
    },
    {
      key: 'actions',
      header: '',
      render: (row: Incident) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            navigate('/incidents/' + row.id)
          }}
          className="text-xs text-brand-primary font-montserrat hover:underline"
        >
          View
        </button>
      ),
    },
  ]
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function IncidentListPage() {
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)

  const { data, isLoading, isError, error } = useIncidents()

  const [severityFilter, setSeverityFilter] = useState<string>('ALL')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [currentPage, setCurrentPage] = useState(1)

  // AC-07: Client-side RBAC — operators only see their own incidents.
  const roleFiltered = useMemo<Incident[]>(() => {
    const incidents = data ?? []
    if (user?.role === 'operator') {
      return incidents.filter((inc) => inc.reporter_email === user.email)
    }
    return incidents
  }, [data, user])

  // Apply severity and status filters.
  const filtered = useMemo<Incident[]>(() => {
    return roleFiltered.filter((inc) => {
      const severityMatch =
        severityFilter === 'ALL' || inc.severity === (severityFilter as BackendSeverity)
      const statusMatch =
        statusFilter === 'ALL' || inc.status === (statusFilter as IncidentStatus)
      return severityMatch && statusMatch
    })
  }, [roleFiltered, severityFilter, statusFilter])

  // AC-08: Client-side pagination (20 per page).
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(currentPage, totalPages)
  const pageStart = (safePage - 1) * PAGE_SIZE
  const pageEnd = pageStart + PAGE_SIZE
  const paginated = filtered.slice(pageStart, pageEnd)

  const showingFrom = filtered.length === 0 ? 0 : pageStart + 1
  const showingTo = Math.min(pageEnd, filtered.length)

  function handleFilterChange(setter: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLSelectElement>) => {
      setter(e.target.value)
      setCurrentPage(1) // reset to first page on filter change
    }
  }

  const errorMessage = isError ? getApiErrorDetail(error, 'Failed to load incidents.') : null

  const columns = useMemo(() => buildColumns(navigate), [navigate])

  return (
    <Layout pageTitle="Incidents">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <AlertTriangle size={24} className="text-brand-primary" />
          <div>
            <h1 className="text-2xl font-semibold text-neutral-900 font-montserrat">
              Incidents
            </h1>
            <p className="text-sm text-neutral-500 font-montserrat">
              Track and manage SRE incident reports.
            </p>
          </div>
        </div>
        <Button
          variant="primary"
          onClick={() => navigate('/incidents/new')}
          className="flex items-center gap-2"
        >
          <Plus size={16} />
          New Incident
        </Button>
      </div>

      {/* Error state */}
      {isError && errorMessage && (
        <div className="mb-4">
          <Alert type="error" title="Failed to load incidents" message={errorMessage} />
        </div>
      )}

      {/* Filter bar */}
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[160px] max-w-xs">
            <Select
              label="Severity"
              options={SEVERITY_FILTER_OPTIONS}
              value={severityFilter}
              onChange={handleFilterChange(setSeverityFilter)}
            />
          </div>
          <div className="flex-1 min-w-[160px] max-w-xs">
            <Select
              label="Status"
              options={STATUS_FILTER_OPTIONS}
              value={statusFilter}
              onChange={handleFilterChange(setStatusFilter)}
            />
          </div>
        </div>
      </Card>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Spinner size="lg" label="Loading incidents..." />
        </div>
      )}

      {/* Table */}
      {!isLoading && (
        <div className="mt-4">
          <Card title={`All Incidents${filtered.length > 0 ? ` (${filtered.length})` : ''}`}>
            <Table
              columns={columns}
              data={paginated}
              keyExtractor={(row) => row.id}
              isLoading={false}
              emptyMessage={
                data?.length === 0
                  ? 'No incidents yet. Create your first incident report.'
                  : 'No incidents match the current filters.'
              }
              onRowClick={(row) => navigate('/incidents/' + row.id)}
            />

            {/* Pagination controls (AC-08) */}
            {filtered.length > 0 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-neutral-100">
                <p className="text-xs text-neutral-500 font-montserrat">
                  Showing {showingFrom}–{showingTo} of {filtered.length} incidents
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={safePage === 1}
                    onClick={() => setCurrentPage((p) => p - 1)}
                    className="flex items-center gap-1"
                  >
                    <ChevronLeft size={14} />
                    Previous
                  </Button>
                  <span className="text-xs text-neutral-600 font-montserrat px-2">
                    Page {safePage} of {totalPages}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={safePage === totalPages}
                    onClick={() => setCurrentPage((p) => p + 1)}
                    className="flex items-center gap-1"
                  >
                    Next
                    <ChevronRight size={14} />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
    </Layout>
  )
}
