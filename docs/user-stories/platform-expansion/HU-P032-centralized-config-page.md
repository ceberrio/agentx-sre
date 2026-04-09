# HU-P032 — Centralized Configuration Page

**Module:** Configuration Platform
**Epic:** EPIC-006 — Configuration Platform
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-08

---

## User Story

**As** a platform administrator (superadmin or admin)
**I want** to manage all system configuration from a single centralized UI page, organized by sections, with descriptive labels for each field
**So that** no business configuration value exists as a hardcoded Python variable or `.env` entry, and the platform can be fully reconfigured without redeployment

> **Architectural principle enforced by this HU — "Config-from-DB":**
> After initial bootstrap (DB connection, app environment, Langfuse host), all system behavior is governed by database-stored configuration managed through this page. `.env` contains only infrastructure bootstrap variables. No business logic value may be hardcoded in Python files or `.env` after HU-P032 is implemented.

> **Relationship to existing HUs:**
> - **Supersedes HU-016** (Governance UI HTMX panel) completely. The HTMX `governance.html` template is removed once this HU is implemented.
> - **Expands the scope of HU-012** (Governance Thresholds backend): the `IGovernanceProvider` port now manages ALL business configuration variables, not only the original 5 governance thresholds. See Technical Notes.
> - **Absorbs HU-P029** (LLM Config): The LLM Configuration section of this page replaces HU-P029 as the UI entry point. HU-P029 backend work (table `llm_config`, hot reload mechanism) remains valid as the backend contract for this page's LLM section. @architect should decide whether to keep HU-P029 as a standalone backend HU and treat this HU as the UI layer only, or merge them.

---

## Variable Classification: Bootstrap vs UI-Managed

> This table is the authoritative classification of every variable in `config.py`. It defines what stays in `.env` and what migrates to the database and UI.

| Variable | Category | UI Section | Label (English) | Input Type | Description | Default Value |
|----------|----------|-----------|----------------|------------|-------------|---------------|
| `app_database_url` | **Bootstrap (.env only)** | — | — | — | PostgreSQL connection string. Required to start the app before any DB config can be read. | `postgresql+asyncpg://sre:sre@app-db:5432/sre_agent` |
| `langfuse_host` | **Bootstrap (.env only)** | — | — | — | Langfuse server URL. Required at startup before DB config is loaded. | `http://langfuse-web:3000` |
| `app_env` | **Bootstrap (.env only)** | — | — | — | Runtime environment (`development`, `production`). Determines startup validation behavior. | `development` |
| `api_key` | **Bootstrap (.env only)** | — | — | — | Legacy API key for non-JWT bootstrap access. Retained for backward compatibility during migration. | `sre-demo-key` |
| `mock_services_url` | **Bootstrap (.env only)** | — | — | — | URL of the mock services container. Infrastructure-level, not business config. | `http://mock-services:9000` |
| `llm_provider` | **UI — LLM Configuration** | LLM Configuration | Primary LLM Provider | Dropdown (`gemini`, `openrouter`, `anthropic`, `openai`, `stub`) | The main LLM provider used by the triage agent. Changes apply in < 5 seconds without container restart. | `gemini` |
| `llm_fallback_provider` | **UI — LLM Configuration** | LLM Configuration | Fallback LLM Provider | Dropdown (`gemini`, `openrouter`, `anthropic`, `openai`, `stub`, `none`) | Provider used when the primary provider's circuit breaker opens. Set to `none` to disable fallback. | `openrouter` |
| `llm_circuit_breaker_threshold` | **UI — LLM Configuration** | LLM Configuration | Circuit Breaker — Failure Threshold | Number (min: 1, max: 20) | Number of consecutive LLM failures before the circuit breaker opens and switches to the fallback provider. | `3` |
| `llm_circuit_breaker_cooldown_s` | **UI — LLM Configuration** | LLM Configuration | Circuit Breaker — Cooldown (seconds) | Number (min: 10, max: 600) | Time in seconds the circuit breaker stays open before attempting to use the primary provider again. | `60` |
| `llm_timeout_s` | **UI — LLM Configuration** | LLM Configuration | LLM Request Timeout (seconds) | Number (min: 5, max: 120) | Maximum time to wait for a response from the LLM before considering the request a failure. | `25` |
| `gemini_api_key` | **UI — LLM Configuration** | LLM Configuration | Gemini API Key | Password (masked) | API key for Google Gemini. Required when Primary or Fallback Provider is set to `gemini`. | — |
| `gemini_model` | **UI — LLM Configuration** | LLM Configuration | Gemini Model | Text | Specific Gemini model to use (e.g., `gemini-2.0-flash`). | `gemini-2.0-flash` |
| `openrouter_api_key` | **UI — LLM Configuration** | LLM Configuration | OpenRouter API Key | Password (masked) | API key for OpenRouter. Required when Primary or Fallback Provider is set to `openrouter`. | — |
| `openrouter_model` | **UI — LLM Configuration** | LLM Configuration | OpenRouter Model | Text | Model identifier for OpenRouter (e.g., `google/gemini-2.0-flash-exp:free`). | `google/gemini-2.0-flash-exp:free` |
| `openai_api_key` | **UI — LLM Configuration** | LLM Configuration | OpenAI API Key | Password (masked) | API key for OpenAI. Required when Primary or Fallback Provider is set to `openai`. | — |
| `openai_model` | **UI — LLM Configuration** | LLM Configuration | OpenAI Model | Text | OpenAI model to use (e.g., `gpt-4o-mini`). | `gpt-4o-mini` |
| `anthropic_api_key` | **UI — LLM Configuration** | LLM Configuration | Anthropic API Key | Password (masked) | API key for Anthropic Claude. Required when Primary or Fallback Provider is set to `anthropic`. | — |
| `anthropic_model` | **UI — LLM Configuration** | LLM Configuration | Anthropic Model | Text | Anthropic model identifier (e.g., `claude-3-5-sonnet-latest`). | `claude-3-5-sonnet-latest` |
| `ticket_provider` | **UI — Ticket System** | Ticket System | Active Ticket Provider | Dropdown (`mock`, `gitlab`, `jira`) | The ticket system adapter the agent uses to create and track incident tickets. | `mock` |
| `gitlab_base_url` | **UI — Ticket System** | Ticket System | GitLab Base URL | Text (URL) | Base URL of your GitLab instance (e.g., `https://gitlab.com`). Required when provider is `gitlab`. | — |
| `gitlab_token` | **UI — Ticket System** | Ticket System | GitLab Access Token | Password (masked) | Personal access token or project token for GitLab API. Requires `api` scope. | — |
| `gitlab_project_id` | **UI — Ticket System** | Ticket System | GitLab Project ID | Text | Numeric ID or path of the GitLab project where issues are created. | — |
| `jira_base_url` | **UI — Ticket System** | Ticket System | Jira Base URL | Text (URL) | Base URL of your Jira instance (e.g., `https://your-org.atlassian.net`). Required when provider is `jira`. | — |
| `jira_token` | **UI — Ticket System** | Ticket System | Jira API Token | Password (masked) | Jira API token for authentication. Generate at `id.atlassian.com/manage-profile/security/api-tokens`. | — |
| `jira_project_key` | **UI — Ticket System** | Ticket System | Jira Project Key | Text | The Jira project key where issues are created (e.g., `SRE`). | — |
| `notify_provider` | **UI — Notifications** | Notifications | Active Notification Provider | Dropdown (`mock`, `slack`, `email`, `teams`) | Channel used to notify the technical team when a new incident ticket is created. | `mock` |
| `slack_webhook_url` | **UI — Notifications** | Notifications | Slack Webhook URL | Password (masked) | Incoming webhook URL for Slack notifications. Required when provider is `slack`. | — |
| `smtp_host` | **UI — Notifications** | Notifications | SMTP Server Host | Text | Hostname of the SMTP server for email notifications (e.g., `smtp.gmail.com`). | — |
| `smtp_port` | **UI — Notifications** | Notifications | SMTP Port | Number (min: 1, max: 65535) | Port of the SMTP server. Common values: 587 (TLS), 465 (SSL), 25 (plain). | `587` |
| `smtp_user` | **UI — Notifications** | Notifications | SMTP Username | Text | Username or email address for SMTP authentication. | — |
| `smtp_password` | **UI — Notifications** | Notifications | SMTP Password | Password (masked) | Password for SMTP authentication. | — |
| `context_provider` | **UI — Context / eShop** | Context / eShop | Context Provider | Dropdown (`static`, `faiss`, `github`) | Source used to provide codebase context to the triage LLM. `static` = local files, `faiss` = local FAISS index, `github` = live eShopOnWeb indexing. | `faiss` |
| `eshop_context_dir` | **UI — Context / eShop** | Context / eShop | Local Context Directory | Text (path) | Filesystem path to the directory containing static context files for the `static` provider. Read-only during normal operation. | `/app/eshop-context` |
| `faiss_index_path` | **UI — Context / eShop** | Context / eShop | FAISS Index Path | Text (path) | Filesystem path where the FAISS index is stored and read from. Read-only during normal operation (set at install time). | `/data/faiss/eshop.index` |
| `confidence_escalation_min` | **UI — Governance & Thresholds** | Governance & Thresholds | Minimum Confidence for Auto-Resolution | Number (0.0–1.0, step 0.01) | If the triage confidence score is below this threshold, the incident is flagged for human escalation instead of auto-resolution. | `0.7` |
| `quality_score_min_for_autoticket` | **UI — Governance & Thresholds** | Governance & Thresholds | Minimum Quality Score for Auto-Ticket | Number (0.0–1.0, step 0.01) | Minimum quality score the LLM output must achieve for the system to auto-create a ticket without human review. | `0.6` |
| `severity_autoticket_threshold` | **UI — Governance & Thresholds** | Governance & Thresholds | Severity Threshold for Auto-Ticket | Dropdown (`low`, `medium`, `high`, `critical`) | Incidents at or above this severity level are always auto-ticketed, regardless of quality score. | `high` |
| `kill_switch_enabled` | **UI — Governance & Thresholds** | Governance & Thresholds | Kill Switch — Disable Auto-Ticketing | Toggle | When enabled, the agent stops creating tickets automatically. All incidents require manual review. Use during incidents or maintenance. | `false` |
| `max_rag_docs_to_expose` | **UI — Governance & Thresholds** | Governance & Thresholds | Max RAG Documents Exposed to LLM | Number (min: 1, max: 20) | Maximum number of codebase documents (from FAISS/GitHub index) that the triage LLM receives as context per request. Higher values improve accuracy but increase token cost. | `5` |
| `EVAL_MIN_SCORE` | **UI — Governance & Thresholds** | Governance & Thresholds | Minimum Eval Score (CI Gate) | Number (0.0–1.0, step 0.01) | Minimum average Langfuse eval score required for the CI/CD pipeline eval gate to pass. Below this, the pipeline fails and alerts the team. | `0.7` |
| `langfuse_enabled` | **UI — Observability** | Observability | Enable Langfuse Tracing | Toggle | When enabled, all LLM calls, pipeline stages, and evals are traced in Langfuse. Disable to reduce latency or when Langfuse is unavailable. | `true` |
| `langfuse_public_key` | **UI — Observability** | Observability | Langfuse Public Key | Text | Public key for Langfuse project authentication. Found in the Langfuse project settings. | `pk-lf-demo` |
| `langfuse_secret_key` | **UI — Observability** | Observability | Langfuse Secret Key | Password (masked) | Secret key for Langfuse project authentication. Keep confidential. | `sk-lf-demo` |
| `log_level` | **UI — Observability** | Observability | Log Level | Dropdown (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | Logging verbosity for the SRE agent service. `DEBUG` produces verbose output for troubleshooting; `INFO` is the standard production setting. | `INFO` |
| `GOVERNANCE_CACHE_TTL_S` | **UI — Observability** | Observability | Governance Cache TTL (seconds) | Number (min: 0, max: 300) | How long the governance threshold cache is valid before re-reading from the database. Set to 0 to disable caching (live reads on every request). | `30` |
| `EXPLAINABILITY_PROVIDER` | **UI — Observability** | Observability | Explainability Provider | Dropdown (`langfuse`, `local`, `none`) | Backend used to store and retrieve explainability reports (RAG attribution). `langfuse` = stored in Langfuse traces, `local` = PostgreSQL, `none` = disabled. | `langfuse` |
| `guardrails_llm_judge_enabled` | **UI — Security** | Security | Enable LLM Judge for Guardrails | Toggle | When enabled, a secondary LLM call validates that the triage output does not contain harmful content or prompt injections before returning results to the user. Disabling reduces latency at the cost of safety. | `true` |
| `max_upload_size_mb` | **UI — Security** | Security | Maximum File Upload Size (MB) | Number (min: 1, max: 50) | Maximum size of files that can be attached to an incident report. Larger files are rejected at the API level. | `5` |
| `storage_provider` | **UI — Storage** | Storage | Storage Backend | Dropdown (`memory`, `postgres`) | Database backend for incident and configuration persistence. `memory` is for testing only — all data is lost on restart. `postgres` is required for production use. | `postgres` |

---

## Acceptance Criteria

> ACs are verifiable conditions. Each one must be independently testable.

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Page accessible only to authorized roles | **Given** a user is authenticated, **When** they navigate to `/config`, **Then** only users with role `superadmin` or `admin` see the full page with edit access. Users with role `flow_configurator` see only the "Governance & Thresholds" and "Agents" sections (read-write). All other roles receive HTTP 403. |
| AC-02 | Page organized in labeled sections | **Given** the admin opens `/config`, **When** the page loads, **Then** configuration fields are grouped in the following collapsible sections: LLM Configuration, Ticket System, Notifications, Context / eShop, Governance & Thresholds, Observability, Security, Storage. Each section has a header, a short description, and a collapse/expand toggle. |
| AC-03 | Every field has label and description | **Given** any configuration field is visible on the page, **When** the admin reads the field, **Then** it shows: (a) a descriptive label in English, (b) a 1-2 line description explaining what the field controls and when to change it, (c) the current value, (d) the type-appropriate input control (text, password, number, toggle, dropdown). |
| AC-04 | Password fields are masked by default | **Given** a field contains a credential (API key, token, password), **When** the page renders, **Then** the field shows masked content (`••••••••`). A "Reveal" button (eye icon) temporarily shows the value in plaintext only for `superadmin` and `admin`. |
| AC-05 | LLM Configuration section — provider selector | **Given** the admin selects a Primary or Fallback LLM Provider from the dropdown, **When** they change the selection, **Then** only the credential fields relevant to the selected provider are shown (e.g., selecting `gemini` shows the Gemini API Key and Model fields; selecting `none` for fallback hides all fallback credential fields). |
| AC-06 | LLM Configuration — save applies in < 5 seconds | **Given** the admin changes the LLM provider or circuit breaker parameters and clicks "Save", **When** the `PUT /config/llm` request succeeds, **Then** a success toast appears, and the new configuration is active within 5 seconds without container restart (hot reload per SA-012). |
| AC-07 | Ticket System section — provider selector | **Given** the admin selects a Ticket Provider (Mock, GitLab, Jira), **When** they change the selection, **Then** only the credential and URL fields for the selected provider are shown. Fields for other providers are hidden. |
| AC-08 | Ticket System — test connection button | **Given** the admin has configured the ticket system credentials and clicks "Test Connection", **When** the backend executes a health-check call to the selected ticket system, **Then** the UI shows a success message (green) with the system name, or a descriptive error message (red) explaining why the connection failed. |
| AC-09 | Notifications section — test notification button | **Given** the admin has configured a notification channel and clicks "Send Test Notification", **When** the backend sends a test notification via the configured provider, **Then** the UI shows confirmation of delivery or a descriptive error. |
| AC-10 | Governance & Thresholds — flow_configurator access | **Given** a user with role `flow_configurator` is authenticated, **When** they navigate to `/config`, **Then** they see and can edit only the "Governance & Thresholds" section. All other sections are either hidden or shown as read-only. |
| AC-11 | Kill switch visible and actionable | **Given** an `admin` or `superadmin` is on the Governance & Thresholds section, **When** they view the Kill Switch toggle, **Then** the toggle has a prominent visual indicator (red border when enabled, green when disabled) and a confirmation dialog before activation ("Are you sure you want to disable auto-ticketing?"). |
| AC-12 | All config persisted in database | **Given** the admin saves any configuration value, **When** the save request completes, **Then** the value is stored in the corresponding database table (`llm_config`, `platform_config`, or `governance_thresholds`). After a container restart, the saved value is loaded from the database — not from `.env`. |
| AC-13 | Bootstrap variables NOT shown in UI | **Given** the config page loads, **When** the admin sees the page, **Then** the following variables are NOT present as editable fields: `app_database_url`, `langfuse_host`, `app_env`, `api_key`, `mock_services_url`. These exist only in `.env` and are never exposed or modifiable from the UI. |
| AC-14 | Inline validation before save | **Given** the admin fills in a field with an invalid value (e.g., negative number for a threshold, invalid URL format, empty required field), **When** they attempt to save or blur the field, **Then** an inline validation error appears below the field in red, explaining the constraint. The "Save" button is disabled while validation errors exist. |
| AC-15 | Number fields enforce min/max | **Given** a number field (e.g., Circuit Breaker Failure Threshold), **When** the admin enters a value outside the allowed range (e.g., 0 or 25 for a field with min: 1, max: 20), **Then** the field shows an inline error and the save is blocked. |
| AC-16 | Default values visible | **Given** a field has a default value defined, **When** the current value matches the default, **Then** a "Default" badge or placeholder shows the default value. If the admin clears a field, they can click "Reset to default" to restore the documented default. |
| AC-17 | Audit log entry on save | **Given** an admin saves any configuration change, **When** the save succeeds, **Then** an audit log entry is created with: `user_email`, `timestamp`, `section`, `field_key`, `old_value` (masked if credential), `new_value` (masked if credential). |
| AC-18 | All UI text in English | **Given** any text visible on the configuration page (labels, descriptions, placeholders, validation messages, button text, section headers, toast messages), **When** the page renders or user interactions occur, **Then** all text is displayed in English. No Spanish or other language text appears. No i18n layer is implemented. |
| AC-19 | Page renders within design system | **Given** the Design System from HU-P031 is implemented, **When** the config page renders, **Then** all components (inputs, toggles, dropdowns, buttons, cards, alerts) use the SoftServe Design System tokens (`#454494` primary color, Montserrat/Inter typography, spacing tokens). No hardcoded Tailwind color classes are used outside the Design System. |

---

## Business Rules

> BRs are business constraints or policies that apply to this HU.

| ID | Rule |
|----|------|
| BR-01 | **Config-from-DB principle:** After the initial bootstrap phase (connecting to the database using `app_database_url`, loading `app_env`, connecting to Langfuse using `langfuse_host`), all system behavior is governed by values stored in the database. No business configuration value may remain hardcoded in Python source files or `.env` after HU-P032 is deployed. The bootstrap variables listed in the Variable Classification table are the only values permitted in `.env` post-deployment. |
| BR-02 | **No blank-slate cold start:** If the database has no configuration rows (first install, empty DB), the system must seed all configuration fields with their documented default values during the Alembic migration. The existing seed for `governance_thresholds` must be extended to cover all tables (`llm_config`, `platform_config`). The system must never fail to start due to missing config rows. |
| BR-03 | **Role enforcement — edit permissions:** The full configuration page (all sections) is read-write only for `superadmin` and `admin`. The `flow_configurator` role may read and write only the "Governance & Thresholds" section. All other roles have no access to `/config`. This rule applies at both the API level (enforced by the JWT middleware from HU-P018) and the UI level (enforced by conditional rendering). |
| BR-04 | **Credential masking in audit logs:** API keys, tokens, and passwords must never appear in plaintext in audit log entries. They must be stored as `"[REDACTED]"` in both the old_value and new_value fields of the audit log. The fact that a credential changed must be logged, but not the credential values themselves. |
| BR-05 | **Validation before persistence:** No invalid value may be stored in the database. The backend `PUT` endpoints for each config section must apply the same validation rules as the UI (type, min/max, required fields, format). A `PUT` request with invalid values must return HTTP 422 with a detailed validation error body, never HTTP 200. |
| BR-06 | **HU-016 superseded:** The HTMX `governance.html` template and its associated route are considered deprecated from the moment HU-P032 is deployed. The governance UI from HU-016 must be removed or disabled once HU-P032 passes QA. The backend endpoints of HU-012 (`GET/PUT /governance/thresholds`) are retained and consumed by the new React page. |
| BR-07 | **All UI text in English — no i18n:** Every user-visible string on the configuration page (labels, descriptions, error messages, button text, toast messages, placeholder text) must be written in English. No internationalization layer (i18n, react-i18next, etc.) is implemented. Implementing i18n is out of scope for v1. |
| BR-08 | **LLM stub forbidden in production:** The `llm_provider` and `llm_fallback_provider` dropdowns must not allow selection of `stub` when `app_env=production`. The UI must disable the `stub` option or show a warning, mirroring the validation in `config.py`'s `_reject_stub_in_production`. |

---

## Edge Cases

> Boundary or exceptional scenarios the system must handle.

| Scenario | Expected Behavior |
|----------|-------------------|
| Admin saves a new LLM provider but does not fill in the API key | Inline validation error: "API Key is required for the selected provider." Save is blocked. |
| Admin enables the kill switch, then navigates away and returns | The kill switch toggle shows its current DB state (enabled/red) on re-render. State is not lost on navigation. |
| Admin sets `llm_circuit_breaker_threshold` to 0 | Inline error: "Minimum value is 1." Save is blocked. The system never stores 0 (would mean the circuit breaker triggers immediately on every call). |
| Admin saves LLM config while the primary provider's circuit breaker is currently open | The hot reload applies the new config. The circuit breaker state resets to closed for the newly configured provider. The UI shows a warning: "Circuit breaker was open. It has been reset with the new parameters." |
| `flow_configurator` attempts to POST to `/config/llm` directly (bypassing UI) | The JWT middleware returns HTTP 403. The backend enforces role permissions independently of the UI. |
| Database is unreachable when admin tries to save | The `PUT` endpoint returns HTTP 503. The UI shows: "Configuration could not be saved. Database is unreachable. Try again shortly." |
| Admin changes `storage_provider` from `postgres` to `memory` | A prominent warning dialog appears before save: "Switching to in-memory storage will cause all data loss on restart. This is intended for testing only. Confirm?" Requires explicit confirmation. |
| First install — database has no config rows | Alembic seed migration runs automatically and inserts all default values. The config page renders with all defaults shown. No fields appear blank or errored. |
| Two admins edit the same field simultaneously | Last-write-wins. The save that completes second overwrites the first. An audit log entry exists for both writes. A future version may implement optimistic locking (out of scope for v1). |
| Admin reveals a credential field and screenshots it | The system cannot prevent screenshots. This is documented as an operational risk in the security notes. Masking reduces accidental exposure in casual viewing. |

---

## Design Reference

> Figma screens/mockups or components that apply to this HU.

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| Configuration Page layout | Pending design | Page follows the shell layout from HU-P027: left sidebar + main content area. The main area uses a two-column layout: section nav (sticky) on the left, form content on the right. |
| Collapsible section pattern | HU-P031 `<Card>` component | Each section renders as a Card with an expand/collapse chevron. |
| Password field with reveal | HU-P031 `<Input>` component with `type="password"` + toggle button | |
| Toggle for kill switch and boolean flags | HU-P031 — new `<Toggle>` component to be created in this HU or HU-P031 | |
| Dropdown / Select | HU-P031 `<Select>` component | |
| Toast notifications | HU-P031 `<Alert>` component (or dedicated toast library — @architect approves) | |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-012 | Backend port `IGovernanceProvider` — this HU expands its scope to cover all business config variables (see Technical Notes). Must be complete before implementing Governance & Thresholds section. |
| HU-P017 | JWT auth — must be complete before any `/config/*` endpoint is protected |
| HU-P018 | JWT middleware + `require_role()` — enforces RBAC on all config endpoints |
| HU-P027 | React shell — the config page lives inside the authenticated shell |
| HU-P029 | Backend `llm_config` table + hot reload mechanism — this HU provides the UI layer for the LLM section. HU-P029 backend work is a prerequisite. |
| HU-P031 | Design System — all UI components must use SoftServe tokens |
| HU-016 | Superseded — the HTMX governance UI template is removed once this HU is in production |

---

## Technical Notes

> Observations for the developer. Not implementation — constraints or technical context.

- **Expanded scope of `IGovernanceProvider` (HU-012):** The original `IGovernanceProvider` port managed only the 5 governance threshold fields (`confidence_escalation_min`, `quality_score_min_for_autoticket`, `severity_autoticket_threshold`, `kill_switch_enabled`, `max_rag_docs_to_expose`) plus `EVAL_MIN_SCORE`. With HU-P032, the concept of "governable configuration" expands to all non-bootstrap variables. The @architect should decide whether to extend `IGovernanceProvider` or create additional ports (`ILLMConfigProvider`, `IPlatformConfigProvider`, etc.) — a cleaner separation of concerns is preferred over a monolithic config port.

- **Database tables involved:**
  - `governance_thresholds` — existing table (HU-012). Covers: Governance & Thresholds section.
  - `llm_config` — table from HU-P029. Covers: LLM Configuration section.
  - `platform_config` — existing table from HU-P020/P021/P022/P023. Covers: Ticket System, Notifications, Context/eShop, Security, Storage sections. Observability config can use this table with prefixed keys (e.g., `key='langfuse_enabled'`).

- **API surface:** The configuration page calls existing endpoints where possible:
  - `GET/PUT /governance/thresholds` (HU-012) — Governance section
  - `GET/PUT /config/llm` (HU-P029) — LLM section
  - `GET/PUT /config/ticket-system` (HU-P022) — Ticket section
  - `GET/PUT /config/notifications` (HU-P023) — Notifications section
  - `GET/PUT /config/ecommerce-repo` (HU-P021) — Context/eShop section
  - New: `GET/PUT /config/observability` — Observability section (langfuse keys, log level, cache TTL, explainability provider)
  - New: `GET/PUT /config/security` — Security section (guardrails toggle, max upload size)
  - New: `GET/PUT /config/storage` — Storage section (storage_provider)

- **Cold start seeding:** The Alembic seed migration that inserts defaults for `governance_thresholds` (already exists) must be extended to also seed `llm_config` and all `platform_config` keys used by this page. This prevents a blank config page on first install.

- **The `.env` file after HU-P032:** The `.env` file retains only bootstrap variables: `APP_DATABASE_URL`, `LANGFUSE_HOST`, `APP_ENV`, `SRE_API_KEY` (legacy), `MOCK_SERVICES_URL`, `JWT_SECRET` (for HU-P017), `CONFIG_ENCRYPTION_KEY` (for credential encryption). All other variables in `.env` become ignored once they have a corresponding DB row. The `pydantic-settings` `Settings` class in `config.py` may be simplified post-implementation to remove the migrated fields.

- **Credential encryption:** API keys and tokens stored via this page must be encrypted at rest using AES-256 with the key from `CONFIG_ENCRYPTION_KEY` env var (established in SA-004/HU-P021). The decryption happens transparently in the adapter layer — the credentials are never returned in plaintext via the API.

---

## Pending Questions

> Ambiguities that must be resolved before starting development.

| # | Question | Directed To | Status |
|---|----------|------------|--------|
| 1 | Should `IGovernanceProvider` be extended to cover all config variables, or should separate ports be created (`ILLMConfigProvider`, `IPlatformConfigProvider`)? Clean architecture prefers separation. | @architect | Pending — DEC-A08 |
| 2 | Should the Observability section expose `langfuse_public_key` and `langfuse_secret_key` as editable fields? These are bootstrap-adjacent (Langfuse connection requires the host to be set in `.env` first). If the keys change in the UI but the host is wrong, the connection fails silently. Recommendation: keep only `langfuse_enabled`, `log_level`, `GOVERNANCE_CACHE_TTL_S`, `EXPLAINABILITY_PROVIDER` in the Observability section; move the Langfuse keys to bootstrap (`.env`). | @architect / @client | Pending — DEC-A09 |
| 3 | The `storage_provider` toggle from `postgres` to `memory` would be catastrophic in production. Should this field be hidden entirely in the UI (leaving it as bootstrap-only), or shown with a stern warning? | @architect | Pending — DEC-A10 |

---

## Change History

| Version | Date | Change | Reason |
|---------|------|--------|--------|
| v1 | 2026-04-08 | Initial creation | Requisito D — centralized config UI. Covers all non-bootstrap variables from `config.py`. Supersedes HU-016. Expands scope of HU-012. |
