# HU-007 — Team Notification (Mock Webhook)

**Module:** Notification
**Epic:** N/A — Standalone HU
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** the SRE Agent
**I want** to notify the technical team via the mock webhook service after a ticket is created
**So that** the team is immediately informed of the new incident and can begin working on resolution

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Team notification sent after ticket creation | Given a ticket was successfully created (HU-006), When the notification stage runs, Then `POST /notify/team` is called on the mock webhook service |
| AC-02 | Team notification payload is complete | Given the POST request is made to `/notify/team`, When the body is examined, Then it contains: `{ incident_id, ticket_id, summary, severity, affected_service, timestamp }` |
| AC-03 | Email notification also sent | Given the notification stage runs, When called, Then `POST /notify/email` is also called on the mock webhook service (in addition to `/notify/team`) |
| AC-04 | Email notification payload is complete | Given the POST to `/notify/email` is made, When examined, Then it contains: `{ to: string, subject: string, body: string }` where subject includes the incident_id and severity |
| AC-05 | Notification logged | Given either notification call completes, When result is received, Then a structured log entry is emitted: `{ stage: "notify", event: "team_notified|email_sent|notify_failed", incident_id, ticket_id, channel: "webhook|email", status_code, duration_ms }` |
| AC-06 | Notification failure handled | Given the mock webhook service returns a 5xx error, When the failure occurs, Then the failure is logged as `notify_failed` and the pipeline continues (notification failure does not block resolution notification) |
| AC-07 | Both channels attempted independently | Given the team webhook call fails, When this happens, Then the email call still runs independently — one failure does not cancel the other |
| AC-08 | Mock webhook response displayed in demo | Given the mock service receives a notification request, When the demo is running, Then the mock service logs or echoes the received payload in a visible way (for demo purposes — the reviewer can see the notification was "delivered") |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | Two notification channels are required: team communicator (DEC-003: `POST /notify/team`) and email (DEC-003: `POST /notify/email`) |
| BR-02 | Both notification channels use the mock webhook local service (DEC-003) — no real Slack, Teams, or email service is required |
| BR-03 | Notification is triggered automatically by the agent — no manual user action |
| BR-04 | A notification failure must NOT stop the pipeline — the resolution notification stage (HU-008) must still be reachable |
| BR-05 | The email `to` field must use a placeholder address defined in `.env.example` (e.g., `TEAM_EMAIL=team@example.com`) |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Mock webhook service container is not running | Both notification calls fail; both logged as `notify_failed`; pipeline continues to resolution stage |
| Notification called twice for same incident | Both calls execute (no idempotency required for notifications — duplicate alerts are acceptable) |
| Triage summary is very long | Email body truncated to 1000 characters; full summary available via ticket reference |
| Severity is "critical" | Email subject includes "[CRITICAL]" prefix to visually distinguish in the demo |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| — | No design — pure backend + mock service logic | Mock service may output received payloads to Docker logs for demo visibility |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-006 | Must complete before: ticket_id from HU-006 is required for the notification payload |
| HU-011 | Shares entity: mock webhook endpoints `/notify/team` and `/notify/email` are in the mock-services container (HU-011) |
| HU-009 | Shares logging contract |

---

## Technical Notes

- Both `POST /notify/team` and `POST /notify/email` are on the mock-services container (DEC-003)
- The mock service should respond with `{ status: "delivered", channel: "team|email", received_at: timestamp }` for demo visibility
- The mock service should print received payloads to stdout so they appear in `docker compose logs` during the demo — this is how the judge sees "notification delivered"
- TEAM_EMAIL env var should be defined in `.env.example` with a placeholder value
- Consider calling both channels concurrently (parallel HTTP calls) to minimize pipeline latency

---

## Pending Questions

| # | Question | Directed To | Status |
|---|----------|------------|--------|
| — | No pending questions — DEC-003 resolved notification approach | — | — |

---

## Change History

| Version | Date | Change | Reason |
|---------|------|--------|--------|
| v1 | 2026-04-07 | Initial creation | DEC-003 injected — mock webhook local selected |
