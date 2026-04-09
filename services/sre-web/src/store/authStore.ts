/**
 * Auth store — manages JWT and current user session.
 *
 * Security:
 * - Token stored in localStorage (acceptable for hackathon demo; production
 *   should use httpOnly cookies)
 * - Never logs token or sensitive data
 * - Logout clears all auth state and localStorage entry
 */
import { create } from 'zustand'
import type { User } from '../api/types'

const STORAGE_KEY = 'sre_auth_token'

interface AuthState {
  user: User | null
  token: string | null
  login: (token: string, user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  // Hydrate from localStorage on init (BR: token persistence across page refresh)
  user: null,
  token: localStorage.getItem(STORAGE_KEY),

  login: (token, user) => {
    localStorage.setItem(STORAGE_KEY, token)
    set({ token, user })
  },

  logout: () => {
    localStorage.removeItem(STORAGE_KEY)
    set({ token: null, user: null })
  },
}))
