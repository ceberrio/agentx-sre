/**
 * Config API hooks — TanStack Query wrappers for all configuration sections.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'
import type {
  TicketSystemConfig,
  NotificationsConfig,
  EcommerceRepoConfig,
  ObservabilityConfig,
  SecurityConfig,
  LLMConfigResponse,
  LLMConfigUpdateResponse,
  GovernanceThresholds,
} from '../types'

// ---- Query keys ----

export const configKeys = {
  ticket: ['config', 'ticket'] as const,
  notifications: ['config', 'notifications'] as const,
  ecommerce: ['config', 'ecommerce'] as const,
  observability: ['config', 'observability'] as const,
  security: ['config', 'security'] as const,
  llm: ['config', 'llm'] as const,
  governance: ['governance', 'thresholds'] as const,
}

// ---- Ticket System ----

export function useTicketSystemConfig() {
  return useQuery<TicketSystemConfig>({
    queryKey: configKeys.ticket,
    queryFn: async () => {
      const { data } = await apiClient.get<TicketSystemConfig>('/config/ticket-system')
      return data
    },
    staleTime: 30_000,
  })
}

export function useUpdateTicketSystemConfig() {
  const queryClient = useQueryClient()
  return useMutation<{ success: boolean; updated_at: string }, Error, Record<string, unknown>>({
    mutationFn: async (body) => {
      const { data } = await apiClient.put('/config/ticket-system', body)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.ticket })
    },
  })
}

// ---- Notifications ----

export function useNotificationsConfig() {
  return useQuery<NotificationsConfig>({
    queryKey: configKeys.notifications,
    queryFn: async () => {
      const { data } = await apiClient.get<NotificationsConfig>('/config/notifications')
      return data
    },
    staleTime: 30_000,
  })
}

export function useUpdateNotificationsConfig() {
  const queryClient = useQueryClient()
  return useMutation<{ success: boolean; updated_at: string }, Error, Record<string, unknown>>({
    mutationFn: async (body) => {
      const { data } = await apiClient.put('/config/notifications', body)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.notifications })
    },
  })
}

// ---- Ecommerce Repo ----

export function useEcommerceRepoConfig() {
  return useQuery<EcommerceRepoConfig>({
    queryKey: configKeys.ecommerce,
    queryFn: async () => {
      const { data } = await apiClient.get<EcommerceRepoConfig>('/config/ecommerce-repo')
      return data
    },
    staleTime: 30_000,
  })
}

export function useUpdateEcommerceRepoConfig() {
  const queryClient = useQueryClient()
  return useMutation<{ success: boolean; updated_at: string }, Error, Record<string, unknown>>({
    mutationFn: async (body) => {
      const { data } = await apiClient.put('/config/ecommerce-repo', body)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.ecommerce })
    },
  })
}

// ---- Observability ----

export function useObservabilityConfig() {
  return useQuery<ObservabilityConfig>({
    queryKey: configKeys.observability,
    queryFn: async () => {
      const { data } = await apiClient.get<ObservabilityConfig>('/config/observability')
      return data
    },
    staleTime: 30_000,
  })
}

export function useUpdateObservabilityConfig() {
  const queryClient = useQueryClient()
  return useMutation<{ success: boolean; updated_at: string }, Error, Partial<ObservabilityConfig>>({
    mutationFn: async (body) => {
      const { data } = await apiClient.put('/config/observability', body)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.observability })
    },
  })
}

// ---- Security ----

export function useSecurityConfig() {
  return useQuery<SecurityConfig>({
    queryKey: configKeys.security,
    queryFn: async () => {
      const { data } = await apiClient.get<SecurityConfig>('/config/security')
      return data
    },
    staleTime: 30_000,
  })
}

export function useUpdateSecurityConfig() {
  const queryClient = useQueryClient()
  return useMutation<{ success: boolean; updated_at: string }, Error, Partial<SecurityConfig>>({
    mutationFn: async (body) => {
      const { data } = await apiClient.put('/config/security', body)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.security })
    },
  })
}

// ---- LLM Config ----

export function useLLMConfig() {
  return useQuery<LLMConfigResponse>({
    queryKey: configKeys.llm,
    queryFn: async () => {
      const { data } = await apiClient.get<LLMConfigResponse>('/config/llm')
      return data
    },
    staleTime: 30_000,
  })
}

export function useUpdateLLMConfig() {
  const queryClient = useQueryClient()
  return useMutation<LLMConfigUpdateResponse, Error, Record<string, unknown>>({
    mutationFn: async (body) => {
      const { data } = await apiClient.put<LLMConfigUpdateResponse>('/config/llm', body)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.llm })
    },
  })
}

// ---- Governance Thresholds ----

export function useGovernanceThresholds() {
  return useQuery<GovernanceThresholds>({
    queryKey: configKeys.governance,
    queryFn: async () => {
      const { data } = await apiClient.get<GovernanceThresholds>('/governance/thresholds')
      return data
    },
    staleTime: 30_000,
  })
}

export function useUpdateGovernanceThresholds() {
  const queryClient = useQueryClient()
  return useMutation<GovernanceThresholds, Error, GovernanceThresholds>({
    mutationFn: async (body) => {
      const { data } = await apiClient.put<GovernanceThresholds>('/governance/thresholds', body)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: configKeys.governance })
    },
  })
}
