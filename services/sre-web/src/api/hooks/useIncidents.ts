/**
 * Incident API hooks — TanStack Query wrappers for the incidents resource.
 * AC-04: useIncident polls every 30 s via refetchInterval.
 * AC-06: useSubmitFeedback wraps POST /incidents/{id}/feedback.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'
import type { Incident, FeedbackPayload } from '../types'

const INCIDENTS_STALE_TIME_MS = 15_000
const INCIDENT_DETAIL_STALE_TIME_MS = 10_000
const INCIDENT_POLL_INTERVAL_MS = 30_000

// ---- Query keys ----

export const incidentKeys = {
  all: ['incidents'] as const,
  detail: (id: string) => ['incidents', id] as const,
}

// ---- Hooks ----

/** Fetch all incidents. Role-based filtering is applied client-side in the page. */
export function useIncidents() {
  return useQuery<Incident[]>({
    queryKey: incidentKeys.all,
    queryFn: async () => {
      const { data } = await apiClient.get<Incident[]>('/incidents')
      return data
    },
    staleTime: INCIDENTS_STALE_TIME_MS,
  })
}

/** Fetch a single incident. Polls every 30 seconds (AC-04). */
export function useIncident(id: string) {
  return useQuery<Incident>({
    queryKey: incidentKeys.detail(id),
    queryFn: async () => {
      const { data } = await apiClient.get<Incident>(`/incidents/${id}`)
      return data
    },
    staleTime: INCIDENT_DETAIL_STALE_TIME_MS,
    refetchInterval: INCIDENT_POLL_INTERVAL_MS,
    enabled: Boolean(id),
  })
}

/** Trigger resolution of an incident via POST /incidents/{id}/resolve. */
export function useResolveIncident() {
  const queryClient = useQueryClient()
  return useMutation<{ incident_id: string; status: string }, Error, string>({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<{ incident_id: string; status: string }>(
        `/incidents/${id}/resolve`,
      )
      return data
    },
    onSuccess: (_, id) => {
      void queryClient.invalidateQueries({ queryKey: incidentKeys.detail(id) })
      void queryClient.invalidateQueries({ queryKey: incidentKeys.all })
    },
  })
}

/** Submit triage feedback via POST /incidents/{incident_id}/feedback. */
export function useSubmitFeedback() {
  return useMutation<void, Error, FeedbackPayload>({
    mutationFn: async (payload: FeedbackPayload) => {
      await apiClient.post(`/incidents/${payload.incident_id}/feedback`, {
        rating: payload.rating,
        comment: payload.comment ?? null,
      })
    },
  })
}
