# HU-006 — Ticket Creation (Mock GitLab-compatible API)

**Module:** Ticket Management
**Epic:** N/A — Standalone HU
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** the SRE Agent
**I want** to create a ticket in the ticketing system after a successful triage
**So that** the incident has a trackable, referenceable record that the technical team can work from and eventually mark as resolved

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Ticket created after successful triage | Given the triage summary (HU-005) is available for an incident, When the ticket creation stage runs, Then `POST /tickets` is called on the mock ticketing service |
| AC-02 | Ticket body includes triage data | Given the POST request is made, When the body is examined, Then it contains: `{ title: string, description: string, priority: "P1|P2|P3|P4", incident_id: string, affected_service: string, severity: string }` |
| AC-03 | Ticket ID stored for the incident | Given the mock ticketing service responds with `{ ticket_id: string }`, When the response is received, Then the ticket_id is stored and associated with the incident in the system |
| AC-04 | Priority mapped from severity | Given the triage severity is "critical", When the ticket is created, Then priority is "P1". Given severity "high" → "P2". Given severity "medium" → "P3". Given severity "low" → "P4" |
| AC-05 | Ticket creation logged | Given the ticket stage runs, When the POST call completes (success or failure), Then a structured log entry is emitted: `{ stage: "ticket", event: "ticket_created|ticket_failed", incident_id, ticket_id, duration_ms }` |
| AC-06 | Ticket creation failure handled | Given the mock ticketing service returns a 5xx error, When the failure occurs, Then the agent retries once after 2 seconds; if still failing, logs `ticket_failed` and does NOT proceed to the notification stage |
| AC-07 | Ticket retrievable after creation | Given a ticket was created, When `GET /tickets/:ticket_id` is called on the mock service, Then the full ticket data is returned |
| AC-08 | Ticket ID visible in UI incident view | Given a ticket was successfully created, When the user views the incident detail, Then the ticket ID is displayed with a link or reference |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | Ticket creation is triggered automatically by the agent after triage — no manual user action is required |
| BR-02 | Tickets are created in the mock GitLab-compatible service (DEC-001) — real GitLab integration is out of scope for hackathon |
| BR-03 | The ticket title must be derived from the triage summary's affected_service and a brief description (e.g., "INC-A3F9B12C: Catalog API failure") |
| BR-04 | One ticket per incident — duplicate ticket creation for the same incident_id must be prevented |
| BR-05 | The notification stage (HU-007) must not run if ticket creation fails — the pipeline is sequential at this point |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Ticket creation called twice for same incident (retry edge case) | Idempotency check: if a ticket already exists for the incident_id, return existing ticket_id without creating a duplicate |
| Mock ticketing service is unreachable (container not started) | Return error with clear message: "Ticketing service unavailable" — logged as `ticket_failed` |
| Triage summary has affected_service = "unknown" | Ticket title becomes "INC-XXXXXXXX: Unknown service — review required" |
| Very long triage summary (>2000 characters) | Truncate description field to 2000 characters and append "... [truncated]" |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| Incident Detail — Ticket Reference | No design — UI to be defined by @architect | Show ticket_id, status (open/resolved), link if applicable |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-005 | Must complete before: ticket creation reads the triage summary |
| HU-007 | Ticket ID produced here is used by HU-007 for team notification |
| HU-008 | Ticket ID used by HU-008 for resolution tracking |
| HU-011 | Shares entity: the mock GitLab-compatible API is part of the mock-services container (HU-011) |
| HU-009 | Shares logging contract |

---

## Technical Notes

- Mock GitLab-compatible API endpoints used (DEC-001):
  - `POST /tickets` — create ticket
  - `GET /tickets/:id` — retrieve ticket
  - `POST /tickets/:id/resolve` — mark ticket as resolved (used by HU-008)
- The mock service is in the `mock-services` Docker container (HU-011)
- Ticket body `description` field should be a markdown-formatted string for readability in the demo
- Idempotency: use `incident_id` as an idempotency key — if the mock service doesn't support this natively, implement a check in the agent before calling the API

---

## Pending Questions

| # | Question | Directed To | Status |
|---|----------|------------|--------|
| — | No pending questions — DEC-001 resolved ticketing approach | — | — |

---

## Change History

| Version | Date | Change | Reason |
|---------|------|--------|--------|
| v1 | 2026-04-07 | Initial creation | DEC-001 injected — mock GitLab API selected |
