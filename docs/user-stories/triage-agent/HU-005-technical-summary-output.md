# HU-005 — Technical Summary Output

**Module:** Triage Agent
**Epic:** EPIC-002 — Triage Agent
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** the SRE Agent pipeline
**I want** to persist the triage technical summary and make it retrievable by subsequent pipeline stages
**So that** the ticket creation (HU-006) and team notification (HU-007) stages can access the full triage output without re-running the LLM

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Summary persisted after triage | Given the LLM triage (HU-004) completes successfully, When the summary is produced, Then it is stored in the system associated with the incident ID and retrievable via `GET /incidents/:id/summary` |
| AC-02 | Summary visible in the UI | Given a triage summary exists for an incident, When a user navigates to the incident detail page (or the confirmation page), Then the technical summary, affected service, severity, and key findings are displayed |
| AC-03 | Summary format correct | Given the summary is returned from the API, When consumed by any stage, Then it contains exactly: `{ incident_id, summary (string), affected_service (string), severity ("low"|"medium"|"high"|"critical"), key_findings (string[]) }` |
| AC-04 | Summary accessible by ticket stage | Given the ticket creation stage (HU-006) runs, When it needs triage data, Then it retrieves the summary via `GET /incidents/:id/summary` and includes it in the ticket body |
| AC-05 | Summary accessible by notification stage | Given the team notification stage (HU-007) runs, When it constructs the notification message, Then it includes the summary text and severity from the stored summary |
| AC-06 | Triage failure state stored | Given triage fails (LLM error), When the failure is recorded, Then the incident status is set to `triage_failed` and `GET /incidents/:id/summary` returns `{ error: "triage_failed", incident_id }` |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | The summary is immutable after creation — subsequent pipeline stages read it but never modify it |
| BR-02 | The severity field drives the ticket priority in HU-006 — the mapping is: low → P4, medium → P3, high → P2, critical → P1 |
| BR-03 | The summary must remain associated with the incident for the full lifecycle of the incident (intake through resolution) |
| BR-04 | For hackathon scope, in-memory storage is acceptable; persistent database is optional |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| `GET /incidents/:id/summary` called before triage completes | Returns HTTP 202 with `{ status: "triage_in_progress" }` |
| `GET /incidents/:id/summary` called for non-existent incident ID | Returns HTTP 404 |
| Triage summary has empty key_findings array | Valid state — stored and returned as empty array `[]` |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| Incident Summary View | No design — UI to be defined by @architect | Should display severity with color coding (critical=red, high=orange, medium=yellow, low=green) |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-004 | Must complete before: this HU persists and exposes the output produced by HU-004 |
| HU-006 | Shares entity: ticket creation reads the summary stored by this HU |
| HU-007 | Shares entity: team notification reads the summary stored by this HU |

---

## Technical Notes

- Storage: in-memory map (incident_id → summary) is acceptable for hackathon; Redis or SQLite can be used if @architect decides persistence is needed for demo stability
- The `GET /incidents/:id/summary` endpoint should be implemented by the same backend service that runs the triage, not by the mock-services container
- Severity-to-priority mapping must be documented in SCALING.md as a configurable business rule

---

## Pending Questions

| # | Question | Directed To | Status |
|---|----------|------------|--------|
| — | No pending questions | — | — |

---

## Change History

| Version | Date | Change | Reason |
|---------|------|--------|--------|
| v1 | 2026-04-07 | Initial creation | First refinement pass — hackathon kick-off |
