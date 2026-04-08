# HU-011 — Mock Services Container

**Module:** Mock Services
**Epic:** N/A — Standalone HU
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** a developer and demo presenter
**I want** a single Docker container that exposes all mocked integrations (ticketing API, team webhook, email webhook)
**So that** the entire E2E flow is demoable without any external service credentials or internet connectivity

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Container starts via docker compose | Given `docker compose up --build` is run from the repository root, When all containers start, Then the `mock-services` container starts successfully and its health check passes |
| AC-02 | POST /tickets endpoint available | Given the mock-services container is running, When `POST /tickets` is called with a valid body, Then the service responds with `{ ticket_id: string, status: "open", created_at: timestamp }` and HTTP 201 |
| AC-03 | GET /tickets/:id endpoint available | Given a ticket was created via AC-02, When `GET /tickets/:id` is called, Then the service returns the full ticket data and HTTP 200 |
| AC-04 | POST /tickets/:id/resolve endpoint available | Given a ticket exists, When `POST /tickets/:id/resolve` is called, Then the ticket status is updated to "resolved", the service returns HTTP 200, and the agent is notified to trigger reporter notification |
| AC-05 | POST /notify/team endpoint available | Given the mock-services container is running, When `POST /notify/team` is called with a valid payload, Then the service responds with `{ status: "delivered", channel: "team", received_at: timestamp }` and HTTP 200 |
| AC-06 | POST /notify/email endpoint available | Given the mock-services container is running, When `POST /notify/email` is called with a valid payload, Then the service responds with `{ status: "delivered", channel: "email", received_at: timestamp }` and HTTP 200 |
| AC-07 | All received payloads printed to stdout | Given any of the 5 endpoints receives a request, When the request is processed, Then the full request payload is printed to stdout in the format: `[MOCK] [endpoint] received: { ...payload }` so it appears in `docker compose logs mock-services` |
| AC-08 | No external dependencies | Given the mock-services container is started in isolation, When it runs, Then it operates completely without internet access — no external API calls, no npm registry downloads at runtime |
| AC-09 | GET /tickets/:id returns 404 for unknown ticket | Given a ticket ID that does not exist, When `GET /tickets/:id` is called, Then HTTP 404 is returned: `{ error: "Ticket not found", ticket_id }` |
| AC-10 | POST /tickets/:id/resolve returns 409 for already-resolved ticket | Given a ticket with status "resolved", When `POST /tickets/:id/resolve` is called again, Then HTTP 409 is returned: `{ error: "Ticket already resolved", ticket_id }` |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | All mock endpoints must be in a single container named `mock-services` in docker-compose.yml |
| BR-02 | Data is in-memory only — no persistence across container restarts (acceptable for demo) |
| BR-03 | The mock service must NOT be exposed on a public port accessible from outside the Docker network (except for the demo host — localhost binding only) |
| BR-04 | The mock service must be reachable by the agent container via the Docker internal network using the service name `mock-services` (e.g., `http://mock-services:8080`) |
| BR-05 | The mock service must start before the agent container — use `depends_on` in docker-compose.yml |
| BR-06 | All mock API contracts must be documented in README.md or AGENTS_USE.md |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Agent container calls mock before it is ready | `depends_on` with health check prevents this; if health check not implemented, the agent should retry on connection error |
| Mock service receives malformed JSON body | Returns HTTP 400: `{ error: "Invalid request body" }` |
| POST /tickets called 1000 times in a demo (stress test) | In-memory store grows unboundedly — acceptable for hackathon; note in SCALING.md |
| Mock service crashes and restarts | All in-memory ticket data is lost; demo must restart from the beginning |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| — | No design — pure infrastructure/backend service | |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-006 | Depends on: ticket endpoints are consumed by HU-006 |
| HU-007 | Depends on: notification endpoints are consumed by HU-007 |
| HU-008 | Depends on: resolve endpoint is consumed by HU-008 |

---

## Technical Notes

- Recommended implementation: lightweight HTTP server in any language (e.g., Express.js, FastAPI, or a Go net/http server)
- All data stored in a process-level in-memory map: `tickets: Map<string, Ticket>`
- Ticket ID generation: UUID v4
- Port: suggest 8080 internal, exposed as localhost:8081 to avoid conflict with the main agent service
- docker-compose.yml snippet (guidance for @architect):
  ```yaml
  mock-services:
    build: ./mock-services
    ports:
      - "8081:8080"
    networks:
      - agent-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 5s
      timeout: 3s
      retries: 3
  ```
- A `GET /health` endpoint must be implemented for the health check

---

## Pending Questions

| # | Question | Directed To | Status |
|---|----------|------------|--------|
| — | No pending questions — DEC-001 and DEC-003 define all required endpoints | — | — |

---

## Change History

| Version | Date | Change | Reason |
|---------|------|--------|--------|
| v1 | 2026-04-07 | Initial creation | DEC-001 and DEC-003 injected — all mock endpoints consolidated into single container |
