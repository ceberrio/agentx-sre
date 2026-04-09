# SRE Incident Triage Agent

![Python](https://img.shields.io/badge/python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-orange)
![Langfuse](https://img.shields.io/badge/Langfuse-self--hosted-blueviolet)
![Gemini](https://img.shields.io/badge/LLM-Gemini%202.0%20Flash-4285F4?logo=google&logoColor=white)
![Docker](https://img.shields.io/badge/docker--compose-one--command-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-237%2B%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

> Built for the SoftServe **AgentX Hackathon 2026** — 48-hour sprint.  
> Tag: `#AgentXHackathon`

An end-to-end agentic AI system that turns a 30-second incident report into a **triaged ticket, a notified team, and a closed-loop reporter notification** — all observable, all guarded.

---

## What it does

A reporter drops an incident (text + optional image/log) into a minimal web UI.
The system runs a 6-stage autonomous pipeline:

| Stage | Name | What happens |
|-------|------|-------------|
| 1 | **Ingest** | Multimodal report received. Correlation ID assigned. |
| 2 | **Guardrails** | 5-layer prompt-injection defense. Malicious inputs blocked before any LLM call. |
| 3 | **Triage** | Gemini 2.0 Flash reads the report **and curated eShop codebase context (RAG)** — outputs severity, component, hypotheses, recommended actions. |
| 4 | **Ticket** | Creates a GitLab-compatible issue via the integration agent. |
| 5 | **Notify Team** | Posts to mock Slack webhook + mock SMTP email. |
| 6 | **Resolution** | When the ticket is closed, the reporter is notified automatically. |

Every stage emits a **named Langfuse span** under a single correlation ID — judges see all 6 stages light up in the dashboard in real time.

---

## Quick Start

**Requirements:** Docker + Docker Compose, a free [Google AI Studio](https://aistudio.google.com/) API key.

```bash
# 1. Clone and configure
git clone <repo-url>
cp .env.example .env
# No edits needed — .env.example has working demo values
# After startup: configure your LLM API key from the UI → LLM Config

# 2. Start everything
docker compose up --build

# 3. Open the UI
open http://localhost:5173        # React UI — login and submit an incident

# 4. Watch it run in Langfuse
open http://localhost:3000        # All 6 stages traced live

# 5. Inspect mock ticket + notifications
open http://localhost:9000/docs   # Mock GitLab API + webhook + email
```

That is the entire setup. No database migrations needed (Alembic runs automatically on startup). No external services — everything runs inside the compose stack.

See [`QUICKGUIDE.md`](QUICKGUIDE.md) for a step-by-step walkthrough.

---

## How it works

### Architecture

```
┌─────────────┐    HTTP    ┌─────────────────────────────────────────────────┐
│  React SPA  │──────────▶│                 sre-agent                       │
│  (sre-web)  │           │  FastAPI + LangGraph state machine              │
└─────────────┘           │                                                  │
                          │  ┌──────────┐  ┌────────┐  ┌─────────────────┐ │
                          │  │ Intake   │  │ Triage │  │   Integration   │ │
                          │  │ Guard    │─▶│ Agent  │─▶│   Agent         │ │
                          │  │ (5-layer)│  │(RAG+LLM│  │(ticket + notify)│ │
                          │  └──────────┘  └────────┘  └────────┬────────┘ │
                          │                                       │          │
                          │                              ┌────────▼────────┐ │
                          │                              │ Resolution Agent│ │
                          │                              │(async webhook)  │ │
                          │                              └─────────────────┘ │
                          └──────────────────┬──────────────────────────────┘
                                             │
                          ┌──────────────────▼──────────────────┐
                          │           Langfuse (self-hosted)     │
                          │   Traces · LLM cost · Quality scores │
                          └──────────────────────────────────────┘
```

### Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| Agent framework | LangGraph — explicit DAG, conditional edges |
| LLM (multimodal) | Google Gemini 2.0 Flash (primary) |
| LLM fallback | OpenRouter (circuit-breaker pattern) |
| Observability | Langfuse — self-hosted in Docker |
| Metrics | Prometheus + `/metrics` endpoint |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + Zustand + TanStack Query |
| Auth | Mock Google OAuth + JWT HS256 + RBAC (5 roles) |
| Storage | PostgreSQL via SQLAlchemy + Alembic |
| RAG | FAISS in-process (curated eShop context) |
| Mocks | FastAPI `mock-services` (GitLab API + Slack + email) |
| Container | Docker Compose (single command) |
| Architecture | Hexagonal (Ports & Adapters) |

Full technical details: [`ARCHITECTURE.md`](ARCHITECTURE.md).  
All diagrams: [`docs/diagrams/`](docs/diagrams/README.md).

### Multi-Agent Topology

The system uses **four specialized LangGraph subgraphs** coordinated by a root orchestrator:

- **Intake Guard** — prompt-injection defense (5 layers, no LLM for static patterns)
- **Triage** — RAG retrieval + structured LLM analysis + summary
- **Integration** — idempotent ticket creation + team notification
- **Resolution** — async reporter notification (fired by webhook, never by the sync pipeline)

Each subgraph returns a single typed `AgentEvent`. The orchestrator folds events into an immutable `CaseState` — no subgraph ever mutates state directly.

---

## Evaluation Pillars

This section maps the hackathon judging criteria to concrete files.

### Context Engineering

The triage agent injects curated eShop source-code excerpts into every LLM call:

| What | Where |
|------|-------|
| Curated context chunks | `eshop-context/curated/` (markdown excerpts from checkout, payment, order services) |
| FAISS index builder | `services/sre-agent/app/adapters/context/faiss_adapter.py` |
| RAG retrieval tool | `services/sre-agent/app/orchestration/agents/triage/tools.py` |
| Prompt template (versioned) | `services/sre-agent/app/llm/prompts/triage.yaml` |
| Langfuse span attribute | `agent.rag_queries` + `agent.rag_hits` (visible in dashboard) |

Every LLM call uses a **versioned prompt from the registry** (`llm.prompt_version` in every Langfuse span) — no inline prompt strings anywhere in the codebase.

### Observability

Three-layer observability contract (defined in `ARCHITECTURE.md §4`):

| Layer | What is tracked | Where |
|-------|----------------|-------|
| Infra spans | One span per pipeline stage (ingest, guardrails, triage, ticket, notify, resolve) | `app/observability/tracing.py` |
| LLM attrs | `llm.cost_usd`, `llm.tokens_in/out`, `llm.provider_used`, `llm.fallback_used` | Same spans, Layer 2 attrs |
| Agent attrs | `agent.iterations`, `agent.rag_queries`, `agent.rag_hits`, `agent.escalated` | Triage span, Layer 3 attrs |
| Prometheus | `sre_incidents_total`, `sre_llm_cost_usd_total`, latency histograms at `/metrics` | `app/observability/metrics.py` |
| Structured logs | JSON, correlation ID on every log line, no PII | `app/observability/logging.py` |

### AI Security

5-layer prompt-injection defense (all layers documented in `ARCHITECTURE.md §6`):

| Layer | Mechanism | Cost |
|-------|-----------|------|
| 1 | MIME allow-list (image/png, image/jpeg, text/plain only) | Zero |
| 2 | File size cap (5 MB hard limit) | Zero |
| 3 | Static regex against 20+ known injection patterns | Zero |
| 4 | LLM judge (`intake_guard` prompt v1) for ambiguous inputs | ~0.5K tokens |
| 5 | Policy check — final allow/block with structured reason | Zero |

The injection demo in [`docs/DEMO-SCRIPT.md`](docs/DEMO-SCRIPT.md) shows a live block with zero LLM cost (Layer 3 catches it).

Implementation: `services/sre-agent/app/security/prompt_injection.py`

### Smart Orchestration

| Feature | Implementation |
|---------|---------------|
| Multi-agent DAG | `app/orchestration/orchestrator/graph.py` — LangGraph state machine |
| Conditional routing | `app/orchestration/orchestrator/router.py` — pure routing functions |
| Circuit breaker | `app/adapters/llm/circuit_breaker.py` — auto-failover Gemini → OpenRouter |
| Async resolution path | Separate `build_resolution_graph()` — never blocks the sync pipeline |
| Idempotency | Integration agent: one ticket per `case_id`, checked before creation |
| Immutable state | `CaseState` — only the orchestrator's `_run_*` functions mutate it |

### LLM-as-Judge Eval Pipeline

The CI gate (`ARC-016`) blocks merges when quality drops:

| Metric | Threshold |
|--------|-----------|
| Average triage quality score (golden dataset) | ≥ 0.70 |
| Prompt-injection recall (adversarial dataset) | = 1.00 (zero misses tolerated) |

Files: `evals/runner.py`, `evals/judge.py`, `evals/datasets/`, `.github/workflows/ci.yml`.

---

## Repository Layout

```
.
├── .github/
│   └── workflows/
│       └── ci.yml              <- CI pipeline with LLM-as-judge eval gate
├── docker-compose.yml          <- Single-command environment
├── .env.example                <- All config documented, copy to .env
├── README.md                   <- This file
├── ARCHITECTURE.md             <- System design, layers, all rules
├── QUICKGUIDE.md               <- Fastest path to a running demo
├── SCALING.md                  <- From hackathon mock to production
├── CONTRIBUTING.md             <- Commit conventions, review process
├── AGENTS_USE.md               <- Guide for AI assistants in this repo
├── LICENSE                     <- MIT
├── services/
│   ├── sre-agent/              <- Python agent (FastAPI + LangGraph)
│   │   ├── app/
│   │   │   ├── api/            <- FastAPI route handlers
│   │   │   ├── domain/         <- Entities + port interfaces (pure Python)
│   │   │   ├── adapters/       <- Concrete implementations (LLM, ticket, notify, storage, context)
│   │   │   ├── orchestration/  <- LangGraph graphs + agents
│   │   │   ├── observability/  <- Metrics, tracing, logging
│   │   │   ├── security/       <- Prompt injection defense
│   │   │   ├── llm/            <- Prompt registry + YAML templates
│   │   │   └── infrastructure/ <- Config, container wiring, DB
│   │   └── tests/              <- 237+ unit + contract tests
│   ├── sre-web/                <- React 18 + TypeScript + Vite SPA (Nginx, port 5173)
│   └── mock-services/          <- FastAPI mock: GitLab Issues API + Slack webhook + SMTP
├── eshop-context/
│   └── curated/                <- Chunked eShop source excerpts for RAG
├── evals/
│   ├── datasets/               <- golden.jsonl + adversarial.jsonl
│   ├── runner.py               <- pytest-asyncio eval runner
│   └── judge.py                <- LLM-as-judge scorer
└── docs/
    ├── DEMO-SCRIPT.md          <- 6-stage demo with curl commands
    ├── diagrams/               <- C4, sequence, state diagrams
    └── user-stories/           <- Refined HUs (HU-001..HU-011)
```

---

## Test Suite

```bash
cd services/sre-agent
python -m pytest -q      # 237+ tests, ~2 s
```

Tests are organized by Acceptance Criterion and Business Rule — each `describe` block maps to a specific AC or BR from the user stories.

---

## Configuration Reference

All configuration is in `.env.example` with working demo defaults.
Copy to `.env` — no edits required for a local demo:

```bash
cp .env.example .env
```

LLM provider, model, and API keys are configured from the UI after startup:
**http://localhost:5173 → Sidebar → LLM Config → enter your API key → Save & Reload**

The key is stored encrypted in the database. Hot-reload takes < 5 seconds. No container restart needed.

---

## Live Ports

| URL | Service |
|-----|---------|
| `http://localhost:5173` | **React UI — main platform (login here)** |
| `http://localhost:8000` | FastAPI REST API + Swagger (`/docs`) |
| `http://localhost:8000/metrics` | Prometheus metrics |
| `http://localhost:8000/health` | Health check (JSON) |
| `http://localhost:3000` | Langfuse dashboard |
| `http://localhost:9000/docs` | Mock services (GitLab + notifications) |

---

## Demo

Full 6-stage demo script with curl commands and a live prompt-injection example:
[`docs/DEMO-SCRIPT.md`](docs/DEMO-SCRIPT.md)

---

## License

MIT — see [`LICENSE`](LICENSE).
