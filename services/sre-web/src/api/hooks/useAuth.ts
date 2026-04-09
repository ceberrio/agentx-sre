/**
 * Auth API hooks — TanStack Query wrappers for auth endpoints.
 * All mutations use apiClient directly; queries use useQuery.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'
import type { AuthResponse, User, UserWithStatus, UpdateUserRolePayload } from '../types'

// ---- Query keys ----

export const authKeys = {
  me: ['auth', 'me'] as const,
  users: ['auth', 'users'] as const,
}

// ---- Current user ----

export function useCurrentUser() {
  return useQuery<User>({
    queryKey: authKeys.me,
    queryFn: async () => {
      const { data } = await apiClient.get<User>('/auth/me')
      return data
    },
    // Only run if there is a token (checked by the caller)
    enabled: false,
  })
}

// ---- Login mutation ----

interface LoginPayload {
  email: string
}

export function useLogin() {
  return useMutation<AuthResponse, Error, LoginPayload>({
    mutationFn: async (payload: LoginPayload) => {
      const { data } = await apiClient.post<AuthResponse>(
        '/auth/mock-google-login',
        payload,
      )
      return data
    },
  })
}

// ---- Logout (client-side only, store handles token removal) ----

export function useLogout() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.clear()
  }
}

// ---- Users list ----

export function useUsers() {
  return useQuery<UserWithStatus[]>({
    queryKey: authKeys.users,
    queryFn: async () => {
      const { data } = await apiClient.get<UserWithStatus[]>('/auth/users')
      return data
    },
  })
}

// ---- Update user role ----

interface UpdateRoleVariables {
  userId: string
  payload: UpdateUserRolePayload
}

export function useUpdateUserRole() {
  const queryClient = useQueryClient()
  return useMutation<UserWithStatus, Error, UpdateRoleVariables>({
    mutationFn: async ({ userId, payload }) => {
      const { data } = await apiClient.put<UserWithStatus>(
        `/auth/users/${userId}/role`,
        payload,
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: authKeys.users })
    },
  })
}
