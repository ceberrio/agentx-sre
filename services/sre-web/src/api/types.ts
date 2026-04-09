/**
 * TypeScript interfaces matching the FastAPI / Pydantic backend models.
 * Source of truth: ARCHITECTURE.md Data Contract + sre-agent domain entities.
 */

export type UserRole =
  | 'superadmin'
  | 'admin'
  | 'flow_configurator'
  | 'operator'
  | 'viewer'

export interface User {
  id: string
  email: string
  role: UserRole
  created_at: string
}

/** Backend P1-P4 severity values returned by the API. */
export type BackendSeverity = 'P1' | 'P2' | 'P3' | 'P4'

/** Display severity labels used in badges and UI. */
export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

/** Mapping from backend severity (P1/P2/P3/P4) to display labels. */
export const SEVERITY_MAP: Record<BackendSeverity, Severity> = {
  P1: 'CRITICAL',
  P2: 'HIGH',
  P3: 'MEDIUM',
  P4: 'LOW',
}

/** Incident status values as returned by the backend API. */
export type IncidentStatus =
  | 'received'
  | 'triaging'
  | 'ticketed'
  | 'resolved'
  | 'blocked'
  | 'failed'

/** Incident entity matching the backend Incident.model_dump() fields. */
export interface Incident {
  id: string
  reporter_email: string
  title: string
  description: string
  status: IncidentStatus
  severity: BackendSeverity | null
  blocked: boolean
  blocked_reason: string | null
  has_image: boolean
  has_log: boolean
  created_at: string
  updated_at: string
}

export interface GovernanceThresholds {
  confidence_escalation_min: number
  quality_score_min_for_autoticket: number
  severity_autoticket_threshold: Severity
  kill_switch_enabled: boolean
  max_rag_docs_to_expose: number
}

export interface RagAttribution {
  doc_id: string
  chunk_preview: string
  relevance_score: number
  contributed_to: string[]
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface ApiError {
  detail: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export type FeedbackRating = 'positive' | 'negative'

export interface FeedbackPayload {
  incident_id: string
  rating: FeedbackRating
  comment?: string
}

// Context (eShop RAG)

export type ContextProviderStatus = 'ready' | 'fallback' | 'building'

export interface ContextStatus {
  status: ContextProviderStatus
  repo_url: string
  indexed_files: number
  total_chunks: number
  last_indexed_at: string | null
}

// User management

export interface UserWithStatus extends User {
  full_name: string | null
  is_active: boolean
  last_login_at: string | null
}

export interface UpdateUserRolePayload {
  role: UserRole
}

// Config section types

export interface TicketSystemConfig {
  ticket_provider: 'mock' | 'gitlab' | 'jira'
  gitlab_url: string
  gitlab_project_id: string
  gitlab_token: null
  jira_url: string
  jira_project_key: string
  jira_api_token: null
}

export interface NotificationsConfig {
  notify_provider: 'mock' | 'slack' | 'email' | 'teams'
  slack_channel: string
  slack_bot_token: null
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_password: null
}

export interface EcommerceRepoConfig {
  context_provider: 'static' | 'faiss' | 'github'
  eshop_context_dir: string
  faiss_index_path: string
}

export interface ObservabilityConfig {
  log_level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
  governance_cache_ttl_s: number
  explainability_provider: 'langfuse' | 'local' | 'none'
  langfuse_enabled: boolean
}

export interface SecurityConfig {
  guardrails_llm_judge_enabled: boolean
  max_upload_size_mb: number
}

export interface LLMConfig {
  provider: string
  fallback_provider: string
  model: string
  fallback_model: string
  api_key: null | string
  fallback_api_key: null | string
  circuit_breaker_threshold: number
  circuit_breaker_cooldown_s: number
  timeout_s: number
  updated_at: string | null
  updated_by: string | null
}

export interface LLMConfigResponse {
  config: LLMConfig
  storage_backend: string
  connection_ok: boolean
}

export interface LLMConfigUpdateResponse {
  config: LLMConfig
  reload_status: 'ok' | 'failed'
  elapsed_ms: number
  message: string
}
