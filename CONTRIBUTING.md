# CONTRIBUTING.md

> How to contribute to the SRE Incident Triage Agent during the AgentX Hackathon 2026.

---

## Prerequisites

1. **Read [`ARCHITECTURE.md`](ARCHITECTURE.md) before writing any code.** Especially section 5 ("Architecture Rules — DO NOT BREAK").
2. Read the user story you're implementing in [`docs/user-stories/`](docs/user-stories/README.md).
3. Have Docker running.
4. Have a Gemini or OpenRouter API key in your local `.env`.

---

## Development workflow

```
1. Pick an HU from docs/user-stories/README.md
2. Read its acceptance criteria
3. Create a branch:  feat/HU-XXX-short-description
4. Implement (follow the layer rules in ARCHITECTURE.md §6)
5. Add/update tests in services/sre-agent/tests/
6. Run:   docker compose up --build   and verify the stage shows in Langfuse
7. Open a PR using the checklist below
8. Wait for code review (@tech-lead-code-quality) and architecture review (@architect)
```

---

## Commit conventions (Conventional Commits)

```
<type>(<scope>): <subject>

[optional body]

[optional footer with HU reference]
```

| Type | When |
|---|---|
| `feat` | New feature / new HU implemented |
| `fix` | Bug fix |
| `chore` | Tooling, config, deps |
| `docs` | Docs only |
| `refactor` | Code change with no behavior change |
| `test` | Adding or fixing tests |
| `obs` | Observability instrumentation change |

Example:
```
feat(triage): add eShop context retrieval to triage node

Pulls top-3 relevant excerpts from eshop-context/ before the
LLM call. Adds `eshop_files_consulted` attribute to the
agent.triage span.

HU-004
```

---

## Pull Request checklist

Copy this into your PR description and tick every box.

```
## Architecture compliance
- [ ] I read ARCHITECTURE.md §5 (rules) before writing this
- [ ] No new dependency added (or @architect approved it)
- [ ] No new exposed port in docker-compose.yml (or @architect approved it)
- [ ] No raw user input flows into an LLM prompt as instructions
- [ ] All tool calls use typed Pydantic args
- [ ] Layer dependency rules respected (see §6)

## Observability
- [ ] Every new/changed stage emits a Langfuse span
- [ ] Every new/changed stage emits a structured log line
- [ ] incident_id correlation ID is propagated end-to-end

## Security
- [ ] No hardcoded secrets / API keys / tokens
- [ ] No console.log / print() statements
- [ ] No `eval`, `exec`, or shell calls
- [ ] If touching guardrails: added unit test proving the new pattern blocks AND doesn't false-positive

## Quality
- [ ] Type hints on all public functions
- [ ] Tests added/updated and passing
- [ ] `docker compose up --build` works from a clean clone
- [ ] HU acceptance criteria met (link the HU)

## Demo impact
- [ ] The change is visible in the Langfuse trace
- [ ] If UI changed: still readable on a 1080p screen recording for the demo video
```

---

## Unbreakable rules

These come from `CLAUDE.md` (governance) and `ARCHITECTURE.md` (rules). They apply to humans and AI assistants alike.

1. **Never install a library without `@architect` approval.**
2. **Never hardcode credentials, tokens, or API keys.**
3. **Never commit `.env`. It is in `.gitignore`.**
4. **Never bypass the guardrails node — even "just for testing".**
5. **Never add ad-hoc orchestration in `api/` routes — only the LangGraph state machine orchestrates.**
6. **Never let an LLM produce a free-form URL, command, or shell string that flows into a tool call.**
7. **Never expose a new port in `docker-compose.yml` without `@architect` approval.**
8. **Never commit without explicit user approval.** (DELFOS governance rule.)
9. **Never push without explicit user approval.** (DELFOS governance rule.)

---

## Code style cheat sheet

- Python 3.11+, type hints on all public functions
- Pydantic v2 for all DTOs and tool args
- `async def` for FastAPI routes and IO calls. No blocking calls in handlers.
- Logs via `structlog`, never `print()`
- One stage = one file under `agent/nodes/`. If a node exceeds ~150 lines, extract helpers to a sibling module.
- Tests use `pytest` + `pytest-asyncio`. Mock LLM calls. Mock `mock-services` HTTP calls with `respx`.
