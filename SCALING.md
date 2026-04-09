# SCALING.md — From Hackathon Demo to Production

> The hackathon submission is intentionally a single-host Docker Compose demo with mocked external integrations. This document explains, honestly, what would change to take it to production.

---

## Current state (hackathon)

| Component | What it is now | Why it's fine for the demo |
|---|---|---|
| `sre-agent` | Single FastAPI container | Simplest deployable unit, fastest iteration |
| `sre-web` | React 18 SPA served by Nginx (port 5173) | Full management UI — incidents, config, governance, users |
| `mock-services` | In-process mock of GitLab Issues + webhook + email | Judges can see the full E2E flow without depending on external SaaS keys |
| Storage | PostgreSQL via SQLAlchemy + Alembic (default) | Production-ready schema from day 1 — migrations in `alembic/versions/` |
| Auth | Mock Google OAuth + JWT HS256 + RBAC (5 roles) | Full auth flow without requiring a real Google OAuth app — swap in Authlib for production |
| Resolution trigger | Manual button → `POST /incidents/:id/resolve` | Avoids needing a real ticketing webhook for the demo (see below) |
| Observability | Self-hosted Langfuse | Visual proof of the 6 stages for judges |

---

## Production roadmap

> **v2 (Hexagonal):** every "production swap" below is a **single environment variable change** — never a code change. Adapters already exist in `app/adapters/`. Most have stub `NotImplementedError` bodies that `@developer` fills in to activate.

### 1. Replace `mock-services` with real integrations

| Goal | Action | Code change? |
|---|---|---|
| Switch to GitLab Issues | Set `TICKET_PROVIDER=gitlab` + GitLab env vars | None — `GitLabTicketAdapter` already exists |
| Switch to Jira | Set `TICKET_PROVIDER=jira` + Jira env vars | Fill `JiraTicketAdapter` stub methods |
| Notify via Slack | Set `NOTIFY_PROVIDER=slack` + `SLACK_WEBHOOK_URL` | None — `SlackNotifyAdapter` exists |
| Notify via Email | Set `NOTIFY_PROVIDER=email` + SMTP env vars | Fill `EmailNotifyAdapter` stub |

The graph, the nodes, the API, and the domain are **unchanged** by any of these swaps. That is the entire point of the hexagonal boundary.

### 2. Resolution trigger — from manual button to real webhook (DEC-004)

**Today:** the UI has a "Mark as Resolved" button that calls `POST /tickets/:id/resolve` on `mock-services`, which then triggers the reporter notification.

**Production-ready path:** the system is already designed for a webhook. To activate it:

1. Add a public endpoint `POST /webhooks/ticket-resolved` to `sre-agent` that validates the signature from the real ticketing system (GitLab uses `X-Gitlab-Token`).
2. Configure GitLab/Jira to send a webhook on issue close events.
3. The handler simply enqueues the same `resolve_notify` node currently triggered by the manual button.

The agent pipeline does not change — only the entry point flips from manual to webhook. This is documented as a one-day migration.

### 3. Storage — already production-ready

`PostgresStorageAdapter` is the **default** in v2. The `app-db` container runs on every `docker compose up`. Schema is documented in `ARCHITECTURE.md` §11. Migrations live in `alembic/`.

Remaining production tasks:
- Add Alembic baseline migration
- Add a Redis-backed queue (Arq/Celery) so the agent pipeline runs asynchronously rather than blocking the HTTP request — relevant once concurrent users > ~20.

### 4. Multi-tenancy & auth

- Add OAuth/SSO at the FastAPI layer (Authlib).
- Tag every incident with `tenant_id`. Enforce row-level isolation in the storage layer.
- Per-tenant LLM API keys via a secrets manager (AWS Secrets Manager / HashiCorp Vault).

### 5. Horizontal scaling

| Component | Scaling strategy |
|---|---|
| `sre-agent` API | Stateless → run N replicas behind a load balancer |
| Agent worker pool | Move long-running graph execution to a queue + worker pool |
| Storage | Postgres with read replicas |
| LLM calls | Per-tenant rate limiting + fallback chain (Gemini → OpenRouter → Anthropic) |
| Langfuse | Use Langfuse Cloud, or self-host with the official multi-node Helm chart |

### 6. Observability beyond the demo

- Export Langfuse traces to OpenTelemetry → Grafana Tempo for unified ops dashboards.
- Add Prometheus metrics for: incidents/min, p95 stage latency, guardrail block rate, LLM token spend.
- Alert on: stage failure rate > 1%, p95 triage latency > 30s, guardrail false positive rate.

### 7. AI security hardening

The 5-layer defense is a starting point. For production add:

- LLM-based output validation (judge that the triage summary doesn't contain leaked system prompts or PII)
- Per-user rate limiting on uploads
- Antivirus scan on uploaded log files (ClamAV sidecar)
- Secrets-in-output detection (e.g. detect-secrets) on every LLM response before persisting it
- Audit log of every prompt sent to the LLM, stored immutably for incident response

### 8. Cost controls

- Cache the eShop context retrievals (they're stable across runs) — embed once into a vector store.
- Prefer the cheapest model that meets the quality bar per stage. Triage = Gemini Flash. Guardrails LLM judge = a tiny model (Gemini Flash Lite).
- Set hard daily token budgets per tenant.

---

## What we deliberately skipped (and why)

| Skipped | Why |
|---|---|
| Real Jira/GitLab integration | Required keys + tenant setup; mock proves the same flow |
| Real Slack/Teams webhook | Same reason |
| Persistent DB | Demo runs are minutes long |
| Authentication | Single judge, single demo |
| Vector DB for eShop context | Curated excerpts are enough for a demo; vector store is a 1-day add |
| Multi-region | Out of scope for a 48h hackathon |

The architecture is designed so that **none of the above require rewrites** — only additions at clearly-marked boundaries (`tools/`, `storage/`, `api/`).
