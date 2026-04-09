# Quick Guide — Run the Demo in 5 Minutes

> Goal: from `git clone` to a running SRE Incident Triage Platform demo in minutes.

---

## Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2)
- **An LLM API key** (optional for first boot — configure from the UI after startup):
  - Google Gemini (recommended): https://aistudio.google.com/app/apikey
  - OpenRouter (single key, many models): https://openrouter.ai/keys

That's it. **No Python, no Node, no anything else** needs to be installed on the host.

---

## Steps

### 1. Clone

```bash
git clone https://github.com/ceberrio/agentx-sre.git
cd agentx-sre
```

### 2. Configure

```bash
cp .env.example .env
```

`.env.example` already contains working demo values — **no manual generation needed** for a local demo. The copy is immediately ready to use.

> **For production deployments only:** Replace `CONFIG_ENCRYPTION_KEY`, `LANGFUSE_NEXTAUTH_SECRET`, and `LANGFUSE_SALT` with securely generated values before any non-local deployment. See the comments in `.env.example` for generation commands.

> **Important:** If you already ran `docker compose up` with placeholder values, run `docker compose down -v` before starting again — Langfuse seeds its DB on first boot and needs the correct secrets from the start.

> **LLM API key — do NOT put it in `.env`.**
> The system boots in `stub` mode (keyword-based triage, no API key needed).
> Once running, go to **http://localhost:5173 → LLM Config → enter your key → Save & Reload**.
> The key is stored encrypted in the DB. Hot-reload takes < 5s. No container restart needed.

### 3. Run

```bash
docker compose up --build
```

First build takes **15–20 minutes** (downloads PyTorch, FAISS, sentence-transformers). Subsequent runs use cache and start in < 30 seconds.

When you see `app.started` in the logs, the system is ready.

### 4. URLs

| URL | What you'll see |
|-----|-----------------|
| **http://localhost:5173** | **React UI** — main platform (login here) |
| http://localhost:8000/docs | FastAPI Swagger — test endpoints directly |
| http://localhost:8000/health | Backend health check (no auth required) |
| http://localhost:9000/docs | Mock services — see tickets and notifications |
| http://localhost:3000 | Langfuse — traces dashboard (`demo@demo.com` / `demo1234`) |

> **Port 5173 is the UI.** Port 8000 is the backend API only.

### 5. Login

Open **http://localhost:5173** and use one of these demo accounts:

| Email | Role | Access |
|-------|------|--------|
| `admin@softserve.com` | superadmin | Everything — including LLM config |
| `sre-lead@softserve.com` | admin | Config, user list |
| `config@softserve.com` | flow_configurator | Agents, governance |
| `operator@softserve.com` | operator | Create and resolve incidents |
| `viewer@softserve.com` | viewer | Dashboard only (read-only) |

Click **Sign in with Google** — no password needed (mock auth for demo).

### 6. Demo flow

1. Go to **http://localhost:5173/incidents/new**
2. Fill in: title, description, reporter email
3. Optionally attach a screenshot or log file
4. Click **Submit** — watch the 4-stage progress animation
5. You'll be redirected to the incident detail page
6. See the triage result: severity, root cause, suggested owners, confidence score
7. Click **Resolve** (admin/superadmin) → confirm in the modal
8. Go to **http://localhost:9000/docs** → see the ticket created and notification sent

### 7. Configure LLM from the UI

1. Login as `admin@softserve.com`
2. Sidebar → **LLM Config**
3. Change provider, model, API key
4. Click **Save & Reload** — hot-reload in < 5s, no container restart needed

### 8. Inspect traces in Langfuse

Open **http://localhost:3000** → **Traces** → click the latest trace.

You'll see spans for each agent stage:
`agent.ingest` → `agent.guardrails` → `agent.triage` → `agent.ticket.create` → `agent.notify.team`

Each span shows inputs, outputs, latency, and token usage.

---

## API Access (curl / Postman)

**Get a JWT token:**
```bash
curl -s -X POST http://localhost:8000/auth/mock-google-login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@softserve.com"}'
```

**Use the token:**
```bash
curl http://localhost:8000/incidents \
  -H "Authorization: Bearer <access_token>"
```

**Or use API Key (no login needed, for CI/scripts):**
```bash
curl http://localhost:8000/incidents -H "X-API-Key: sre-demo-key"
```

**Public endpoints (no auth):**
- `GET /health`
- `GET /metrics`
- `GET /context/status`
- `POST /auth/mock-google-login`

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `CONFIG_ENCRYPTION_KEY is required` | Add `CONFIG_ENCRYPTION_KEY=<fernet_key>` to `.env` (see Step 2) |
| `nginx: chown failed (Operation not permitted)` | Already fixed in Dockerfile — run `docker compose up --build sre-web` |
| `npm ci` error on build | Already fixed — Dockerfile uses `npm install` |
| Port already in use | Edit `docker-compose.yml` → change the host-side port |
| `container.llm_hydration_failed` in logs | DB not ready yet at startup — normal on first boot. The app starts in stub mode; set your LLM key from the UI → LLM Config |
| Langfuse refuses connection / blank after login | Run `docker compose down -v` then `docker compose up -d` — placeholder secrets break the first-boot DB seed |
| Langfuse shows "Create Account" after `docker compose up` | The DB was seeded before the user init vars were added. Run `docker compose down -v && docker compose up --build` to re-seed with the demo user. |
| Want to skip Langfuse | Set `LANGFUSE_ENABLED=false` in `.env` |
| `faiss.build_failed` in logs | Normal if Gemini key not set — FAISS needs embeddings. Set a valid API key or switch to `CONTEXT_PROVIDER=static` in `.env` |

---

## Stop everything

```bash
docker compose down          # stop containers, keep volumes
docker compose down -v       # stop containers + delete all data (fresh start)
```
