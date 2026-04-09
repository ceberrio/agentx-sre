/**
 * API error helpers — centralize Axios error detail extraction.
 * Avoids repeating `err.response?.data?.detail` across all pages.
 */
import axios from 'axios'

export function getApiErrorDetail(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}
