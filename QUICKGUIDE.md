# Quick Guide — Run the Demo in 5 Minutes

> Goal: from `git clone` to a running 6-stage agent demo in under 5 minutes.

---

## Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2)
- **An LLM API key** — pick one:
  - Google Gemini (recommended, free tier): https://aistudio.google.com/app/apikey
  - OpenRouter (single key, many models): https://openrouter.ai/keys

That's it. **No Python, no Node, no anything else** needs to be installed on the host.

---

## Steps

### 1. Clone

```bash
git clone https://github.com/<org>/<repo>.git
cd <repo>
```

### 2. Configure

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in **at least one** of:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...your-key-here...
```

…or, if you prefer OpenRouter:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...your-key-here...
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free
```

> **OpenRouter tip:** OpenRouter is the easiest way to switch providers without changing code. You can point `OPENROUTER_MODEL` at any model in their catalog (Gemini, Claude, GPT-4o, Mistral, etc.) and the agent will use it. Useful if your primary key gets rate-limited mid-demo.

### 3. Run

```bash
docker compose up --build
```

First build takes ~2 minutes (Langfuse stack pulls Postgres). Subsequent runs are instant.

When the logs go quiet, the system is ready.

### 4. Open the URLs

| URL | What you'll see |
|---|---|
| http://localhost:8000 | **The agent UI** — submit an incident here |
| http://localhost:3000 | **Langfuse** — login with `demo@demo.com` / `demo` (first run creates it). Watch the 6 stages light up live as the agent runs. |
| http://localhost:9000/docs | **Mock services** Swagger — see tickets created and notifications fired |

### 5. Run the demo flow

1. Go to http://localhost:8000
2. Fill the form: title, description, your email, and **upload a screenshot or log file** (multimodal is mandatory)
3. Click **Submit Incident**
4. Watch the page show stages 1–5 turning green in real time
5. Click the resulting ticket → **Mark as Resolved**
6. Stage 6 (Resolve Notify) lights up — you'll see the reporter notification in the Langfuse trace and at `http://localhost:9000/notifications`

### 6. Inspect the traces

Open Langfuse → **Traces** → click the latest trace. You'll see one root span per incident with 6 child spans (`agent.ingest`, `agent.guardrails`, `agent.triage`, `agent.ticket.create`, `agent.notify.team`, `agent.notify.resolve`), each with inputs, outputs, latency, and token usage.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Port 3000/8000/9000 already in use | Edit `docker-compose.yml` → change the host-side port |
| `GEMINI_API_KEY missing` in logs | Ensure `.env` exists at repo root and contains the key |
| Langfuse UI blank after login | Refresh once — first launch initializes the project |
| Want to skip Langfuse for a faster boot | Set `LANGFUSE_ENABLED=false` in `.env` and remove the langfuse services from the compose file |

---

## Stop everything

```bash
docker compose down            # stop containers
docker compose down -v         # also remove Langfuse DB volume
```
