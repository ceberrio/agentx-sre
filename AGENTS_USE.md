# AGENTS_USE.md

> Guidance for AI coding assistants (Claude, Cursor, Copilot, Aider, etc.) working in this repository.
> Format follows the Anthropic AGENTS.md convention: https://docs.anthropic.com/en/docs/agents-use-md

---

## Project summary

This is the **AgentX Hackathon 2026 — SRE Incident Triage Agent**. It is a Python (FastAPI + LangGraph) application that takes a multimodal incident report, runs it through a 6-stage agent pipeline, and creates a ticket + notifications via mock services. Everything runs in Docker Compose.

The 6 stages are: **Ingest → Guardrails → Triage → Ticket → Notify Team → Resolve Notify**.

---

## Build, run, and test

```bash
# Run the full stack
docker compose up --build

# Run the agent service in isolation (for fast iteration)
cd services/sre-agent
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Run tests
cd services/sre-agent
pytest
```

---

## Architecture rules — DO NOT BREAK

These rules are enforced by `@architect`. Violating them will fail review.

1. **The LangGraph state machine in `services/sre-agent/app/orchestration/orchestrator/graph.py` is the ONLY orchestrator of the pipeline.** Do not add ad-hoc orchestration in `api/` routes — routes should only invoke the graph.
2. **Every stage MUST emit a Langfuse span and a structured log line** with the `incident_id` correlation ID. See `app/observability/tracing.py`.
3. **No LLM call may use raw user input as instructions.** All user input must pass through `app/security/prompt_injection.py` first AND be wrapped in clearly delimited user-content blocks in the prompt template (`app/llm/prompts.py`).
4. **Tool calls (ticket_client, notify_client) must accept only typed Pydantic args.** Never let an LLM produce a free-form URL, command, or shell string that flows into a tool.
5. **The agent must never call out to anything except `mock-services` and the configured LLM provider.** No arbitrary HTTP fetches.
6. **Secrets only via environment variables.** Never commit `.env`. Never hardcode API keys.
7. **`mock-services` is the boundary.** When the time comes to swap in real GitLab/Slack, only the adapter implementations under `app/adapters/` should change. The orchestration graph and agents should not need edits.

---

## Folder map for AI assistants

```
services/sre-agent/app/
├── main.py                      # FastAPI entrypoint — lifespan, routers, CORS
├── api/                         # HTTP layer. Routes only — no business logic.
│   ├── routes_incidents.py      # POST /incidents, GET /incidents/:id
│   ├── routes_auth.py           # POST /auth/mock-google-login, GET /auth/me
│   ├── routes_llm_config.py     # GET/PUT /config/llm (hot-reload)
│   ├── routes_platform_config.py # Config sections (governance, security, etc.)
│   ├── routes_feedback.py       # POST /incidents/:id/feedback
│   └── routes_webhooks.py       # POST /webhooks/resolve
├── domain/
│   ├── entities/                # Pure domain: Incident, TriageResult, LLMConfig, User…
│   └── ports/                   # Port interfaces: ILLMProvider, IStorageProvider…
├── adapters/                    # Concrete implementations of ports
│   ├── llm/                     # gemini, openrouter, anthropic, stub, circuit_breaker
│   ├── storage/                 # postgres_adapter, memory_adapter
│   ├── llm_config/              # postgres_adapter (Fernet-encrypted), memory_adapter
│   ├── platform_config/         # postgres_adapter, memory_adapter
│   ├── auth/                    # jwt_adapter, auth_service
│   └── context/                 # faiss_adapter, github_adapter, static_adapter
├── orchestration/               # LangGraph multi-agent pipeline
│   ├── orchestrator/            # Root graph + router
│   └── agents/                  # intake_guard, triage, integration, resolution
├── observability/               # tracing.py, logging.py, metrics.py
├── security/                    # prompt_injection.py, input_sanitizer.py
├── llm/                         # prompt_registry.py + YAML prompt templates
└── infrastructure/              # config.py (Settings), container.py (DI), database.py

services/sre-web/                # React 18 + TypeScript + Vite SPA
├── src/
│   ├── api/                     # Axios client, types, hooks (useIncidents, useConfig…)
│   ├── pages/                   # LoginPage, DashboardPage, IncidentListPage…
│   ├── components/              # UI components (Button, Badge, FeedbackWidget…)
│   └── store/                   # Zustand stores (authStore, configStore)
└── Dockerfile                   # Multi-stage Node→Nginx build
```

---

## Code style

- Python 3.11+, type hints required on all public functions.
- Pydantic v2 for all DTOs and tool args.
- Async-first (FastAPI + httpx). Avoid blocking calls in request handlers.
- One stage = one file under `agent/nodes/`. If a stage exceeds 150 lines, split helpers into a sibling module — don't bloat the node.
- Logs are JSON, never `print()`.

---

## When you (the AI assistant) make changes

Before suggesting or applying any change:

1. Read the relevant **HU** in `docs/user-stories/` first — it contains acceptance criteria.
2. Read `ARCHITECTURE.md` section **"Architecture Rules — DO NOT BREAK"**.
3. If you're touching the agent pipeline, read `services/sre-agent/app/orchestration/orchestrator/graph.py` first to understand state flow.
4. If you're adding a new dependency, **stop and ask** — `@architect` must approve it (rule from `CLAUDE.md`).
5. If you change observability instrumentation, verify all 6 stages still emit spans (the demo video literally shows this).

---

## Common tasks — recipes

### Add a new node to the agent pipeline
1. Create `app/orchestration/agents/<stage_name>/node.py` with a function `def run(state: CaseState) -> CaseState:`
2. Wrap the body in `with langfuse.start_as_current_span("agent.<stage_name>"):`
3. Register the node in `app/orchestration/orchestrator/graph.py` with `graph.add_node(...)` and wire its edges.
4. Update the React UI to display the new stage status if needed.

### Add a new LLM provider
1. Add a branch in `app/adapters/llm/` — create a new adapter file implementing the `ILLMProvider` port.
2. The provider selection and API key are configured from the UI (ARC-023) — no `.env` changes needed. Add the new provider name to the `Literal` type in `LLMProviderName` and handle it in `container.py` `_build_single_llm_from_key()`.
3. Document it in `QUICKGUIDE.md`.

### Add a new guardrail pattern
1. Add the regex/heuristic to `app/security/prompt_injection.py`.
2. Add a unit test in `tests/test_guardrails.py` proving it blocks the attack and doesn't false-positive on a legitimate report.

---

## What to NEVER do

- Never bypass the guardrails node, even "just for testing".
- Never write to disk outside `/tmp` inside the container.
- Never `pip install` a new package without updating `requirements.txt` AND getting `@architect` approval.
- Never expose new ports in `docker-compose.yml` without `@architect` approval — only necessary ports are exposed by design.
- Never store API keys, even in tests. Use fixtures with fake keys.
