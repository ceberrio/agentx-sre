# SRE Incident Triage Agent — AgentX Hackathon 2026

> **An end-to-end agentic AI system that turns a 30-second incident report into a triaged ticket, a notified team, and a closed-loop reporter notification — all observable, all guarded.**
>
> Built for the SoftServe **AgentX Hackathon 2026** in 48 hours.
> Tag: `#AgentXHackathon`

---

## What it does

A reporter (anyone — dev, ops, customer support) drops an incident report with text **plus an image, log file, or screenshot** into a minimal web UI. The agent then runs a 6-stage pipeline:

| # | Stage | What happens |
|---|---|---|
| 1 | **Ingest** | Multimodal report received (text + file). Correlation ID assigned. |
| 2 | **Guardrails** | 5-layer prompt-injection defense. Blocks malicious inputs before any LLM call uses them as instructions. |
| 3 | **Triage** | Multimodal LLM (Gemini 2.0 Flash) reads the report **and curated eShop codebase context** to produce a structured technical summary (severity, suspected component, hypotheses). |
| 4 | **Ticket** | Creates a ticket in a GitLab-Issues-compatible mock API. |
| 5 | **Notify Team** | Posts to mock team webhook + mock email service. |
| 6 | **Resolve Notify** | When ticket is resolved (manual button → `POST /tickets/:id/resolve`), reporter is notified automatically. |

Every stage is **traced in Langfuse** with a single correlation ID — judges literally see the 6 stages light up live during the demo.

---

## Architecture at a glance

```
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Browser UI  │───▶│  sre-agent   │───▶│  mock-services   │
│  (HTMX form) │    │  (FastAPI    │    │  (FastAPI mock   │
│              │    │   + Lang-    │    │   GitLab API +   │
│              │    │   Graph)     │    │   webhook +      │
│              │    │              │    │   email)         │
└──────────────┘    └──────┬───────┘    └──────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Langfuse    │
                    │  (traces +   │
                    │   metrics)   │
                    └──────────────┘
```

**Stack**

| Layer | Tech |
|---|---|
| Backend | Python 3.11 + FastAPI |
| Agent framework | LangGraph (explicit DAG of 5 stages) |
| LLM (multimodal) | Google Gemini 2.0 Flash (primary) / OpenRouter (fallback) |
| Observability | Langfuse (self-hosted in Docker) |
| Frontend | HTML + HTMX + Tailwind CDN (zero-build) |
| Mocks | FastAPI service `mock-services` |
| Container | Docker Compose |

Full details: [`ARCHITECTURE.md`](ARCHITECTURE.md). Diagrams: [`docs/diagrams/`](docs/diagrams/README.md).

---

## Run it (2 commands)

```bash
cp .env.example .env        # then add your GEMINI_API_KEY (free tier works)
docker compose up --build
```

Then open:

| URL | What |
|---|---|
| http://localhost:8000 | The agent UI (submit incidents) |
| http://localhost:3000 | Langfuse — see all 6 stages traced |
| http://localhost:9000/docs | Mock services — ticketing & notifications |

Detailed walkthrough: [`QUICKGUIDE.md`](QUICKGUIDE.md).

---

## Hackathon evaluation pillars

| Pillar | Where to look |
|---|---|
| **Context engineering** | `services/sre-agent/app/agent/nodes/triage.py` + `eshop-context/` (curated source-code excerpts injected into the triage prompt) |
| **Observability** | `services/sre-agent/app/observability/` — structured JSON logs, correlation IDs, Langfuse spans for every stage |
| **AI security** | `services/sre-agent/app/security/prompt_injection.py` — 5-layer defense documented in `ARCHITECTURE.md` |
| **Smart orchestration** | `services/sre-agent/app/agent/graph.py` — LangGraph state machine with conditional edges, retry on tool failure |

---

## Repository layout

```
.
├── docker-compose.yml
├── .env.example
├── README.md            ← you are here
├── AGENTS_USE.md        ← Anthropic-format guide for AI assistants working in this repo
├── ARCHITECTURE.md      ← system design, layers, rules
├── CONTRIBUTING.md      ← how to contribute, commit, review
├── QUICKGUIDE.md        ← fastest path to a running demo
├── SCALING.md           ← from hackathon mock to production
├── LICENSE              ← MIT
├── services/
│   ├── sre-agent/       ← Python agent (FastAPI + LangGraph)
│   └── mock-services/   ← Mock GitLab API + notify webhook
├── eshop-context/       ← Curated eShop excerpts used as triage context
└── docs/
    ├── diagrams/        ← C4 + sequence diagrams
    └── user-stories/    ← Refined HUs (HU-001..HU-011)
```

---

## License

MIT — see [`LICENSE`](LICENSE).
