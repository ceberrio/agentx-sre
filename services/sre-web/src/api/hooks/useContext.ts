/**
 * Context (eShop RAG) API hooks — TanStack Query wrappers.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'
import type { ContextStatus } from '../types'

// ---- Query keys ----

export const contextKeys = {
  status: ['context', 'status'] as const,
}

// ---- Context status ----

export function useContextStatus() {
  return useQuery<ContextStatus>({
    queryKey: contextKeys.status,
    queryFn: async () => {
      const { data } = await apiClient.get<ContextStatus>('/context/status')
      return data
    },
    staleTime: 60_000, // 1 minute — status does not change frequently
  })
}

// ---- Reindex mutation ----

export function useReindex() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, void>({
    mutationFn: async () => {
      await apiClient.post('/context/reindex')
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: contextKeys.status })
    },
  })
}
