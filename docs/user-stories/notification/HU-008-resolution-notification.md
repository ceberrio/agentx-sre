# HU-008 — Resolution Notification to Reporter

**Module:** Notification
**Epic:** N/A — Standalone HU
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** the SRE Agent
**I want** to notify the original incident reporter when their ticket is marked as resolved
**So that** the reporter knows the incident has been addressed, closing the E2E loop

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Resolution endpoint triggers notification | Given a ticket exists in the mock ticketing service, When `POST /tickets/:id/resolve` is called (by the UI button — DEC-004), Then the agent detects the resolution event and initiates the reporter notification |
| AC-02 | Reporter notification sent via email channel | Given the resolution event is received, When the agent processes it, Then `POST /notify/email` is called with the reporter's email address and a resolution message |
| AC-03 | Reporter notification payload is correct | Given `POST /notify/email` is called for resolution, When examined, Then it contains: `{ to: reporter_email, subject: "Incident INC-XXXXXXXX has been resolved", body: string }` where body references the incident and ticket |
| AC-04 | Resolution event logged | Given the resolution stage runs, When the notification is attempted, Then a structured log entry is emitted: `{ stage: "resolved", event: "resolution_received|reporter_notified|reporter_notify_failed", incident_id, ticket_id, duration_ms }` |
| AC-05 | UI "Mark as Resolved" button triggers flow | Given the incident detail page is open, When the user (acting as the technical team) clicks "Mark as Resolved", Then `POST /tickets/:id/resolve` is called by the frontend and the backend orchestrates the resolution notification |
| AC-06 | Ticket status updated after resolution | Given resolution is triggered, When the process completes, Then the ticket status in the mock service is updated to "resolved" and `GET /tickets/:id` returns `{ status: "resolved" }` |
| AC-07 | UI reflects resolved state | Given the ticket is resolved, When the user views the incident detail, Then the incident status shows "Resolved" and the "Mark as Resolved" button is no longer active |
| AC-08 | Resolution notification visible in demo | Given the resolution flow runs, When the mock email service receives the notification, Then it prints the payload to stdout so the demo observer can confirm "reporter was notified" |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | The resolution trigger is a manual endpoint exposed by the UI (`POST /tickets/:id/resolve`) — this is the demo mechanism (DEC-004) |
| BR-02 | In SCALING.md, the production path must be documented as: real ticketing system sends a webhook to the agent when a ticket transitions to "resolved" status |
| BR-03 | The reporter email must be stored at incident creation time and retrieved when resolution is triggered — the resolution endpoint does not require the reporter to be present |
| BR-04 | Resolution notification is sent via `POST /notify/email` on the mock-services container (DEC-003) |
| BR-05 | An incident can only be resolved once — calling `POST /tickets/:id/resolve` on an already-resolved ticket returns HTTP 409 Conflict |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Resolve called for non-existent ticket ID | Mock service returns HTTP 404; agent logs the error; UI shows "Ticket not found" |
| Resolve called before ticket is created (race condition) | HTTP 404 returned; no notification sent |
| Reporter email was not captured at intake | Resolution notification is skipped; log entry with warning: "reporter_email_missing"; pipeline does not fail |
| Mock email service unavailable at resolution time | Logged as `reporter_notify_failed`; ticket is still marked resolved — notification failure does not undo resolution |
| "Mark as Resolved" clicked multiple times | Second click is disabled after first resolution; or returns 409 from the backend |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| Incident Detail — Mark as Resolved Button | No design — UI to be defined by @architect | Button should be prominent; disabled after resolution |
| Incident Detail — Resolved Status Indicator | No design — UI to be defined by @architect | Visual badge: "Resolved" with timestamp |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-006 | Must complete before: ticket must exist before it can be resolved |
| HU-011 | Shares entity: `POST /tickets/:id/resolve` is on the mock-services container (HU-011) |
| HU-001 | Shares entity: reporter email captured at incident submission (HU-001 form) must be stored for retrieval here |
| HU-009 | Shares logging contract |

---

## Technical Notes

- Reporter email must be captured in the `POST /incidents` request body (HU-001 form) — this needs to be an optional or required field in the intake form. @architect to decide if email is required or optional.
- If email is not captured: resolution notification is best-effort (warn and skip)
- The "Mark as Resolved" UI flow: Frontend calls `POST /tickets/:id/resolve` → Backend receives it → Calls mock service to update ticket status → Calls `POST /notify/email` with reporter email → Returns success to frontend
- The SCALING.md note for production: "In production, the ticketing system (GitLab, Jira, Linear) sends a webhook to `POST /webhooks/ticket-resolved` when a ticket transitions to resolved state. The mock manual trigger in the demo emulates this webhook event."

---

## Pending Questions

| # | Question | Directed To | Status |
|---|----------|------------|--------|
| 1 | Should reporter email be required at intake (mandatory field) or optional? | @architect / PO | Pending — does not block development, default to optional with warning |

---

## Change History

| Version | Date | Change | Reason |
|---------|------|--------|--------|
| v1 | 2026-04-07 | Initial creation | DEC-004 injected — manual UI resolution trigger selected |
