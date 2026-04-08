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

1. **The LangGraph state machine in `services/sre-agent/app/agent/graph.py` is the ONLY orchestrator of the pipeline.** Do not add ad-hoc orchestration in `api/` routes — routes should only invoke the graph.
2. **Every stage MUST emit a Langfuse span and a structured log line** with the `incident_id` correlation ID. See `app/observability/tracing.py`.
3. **No LLM call may use raw user input as instructions.** All user input must pass through `app/security/prompt_injection.py` first AND be wrapped in clearly delimited user-content blocks in the prompt template (`app/llm/prompts.py`).
4. **Tool calls (ticket_client, notify_client) must accept only typed Pydantic args.** Never let an LLM produce a free-form URL, command, or shell string that flows into a tool.
5. **The agent must never call out to anything except `mock-services` and the configured LLM provider.** No arbitrary HTTP fetches.
6. **Secrets only via environment variables.** Never commit `.env`. Never hardcode API keys.
7. **`mock-services` is the boundary.** When the time comes to swap in real GitLab/Slack, only `app/agent/tools/*.py` should change. The graph and nodes should not need edits.

---

## Folder map for AI assistants

```
services/sre-agent/app/
├── main.py                  # FastAPI app entrypoint — wires routes + observability
├── api/                     # HTTP layer ONLY. No business logic. Calls into agent/graph.py.
├── agent/
│   ├── graph.py             # LangGraph state machine — the source of truth for the pipeline
│   ├── state.py             # AgentState TypedDict — the contract between nodes
│   ├── nodes/               # One file per stage. Each node reads/writes AgentState.
│   └── tools/               # Typed clients to mock-services. The "outside world" boundary.
├── llm/
│   ├── provider.py          # Multi-provider LLM client (gemini/openrouter/openai/anthropic)
│   └── prompts.py           # Versioned prompt templates. EDIT HERE, not inline in nodes.
├── security/
│   ├── prompt_injection.py  # 5-layer defense (sanitize → heuristic → LLM judge → schema → sandbox)
│   └── input_sanitizer.py
├── observability/
│   ├── tracing.py           # Langfuse + correlation ID propagation
│   └── logging.py           # Structured JSON logging
├── storage/
│   └── memory_store.py      # In-memory incident store (NOT for production)
└── ui/static/               # HTMX templates served by FastAPI
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
3. If you're touching the agent pipeline, read `services/sre-agent/app/agent/graph.py` first to understand state flow.
4. If you're adding a new dependency, **stop and ask** — `@architect` must approve it (rule from `CLAUDE.md`).
5. If you change observability instrumentation, verify all 6 stages still emit spans (the demo video literally shows this).

---

## Common tasks — recipes

### Add a new node to the agent pipeline
1. Create `app/agent/nodes/<stage_name>.py` with a function `def run(state: AgentState) -> AgentState:`
2. Wrap the body in `with langfuse.start_as_current_span("agent.<stage_name>"):`
3. Register the node in `app/agent/graph.py` with `graph.add_node(...)` and wire its edges.
4. Update the UI status template to show the new stage.

### Add a new LLM provider
1. Add a branch in `app/llm/provider.py` `get_client()` factory.
2. Add the provider's env vars to `.env.example`.
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
