# HU-010 — Trace Correlation Across Agent Stages

**Module:** Observability
**Epic:** EPIC-003 — Observability
**Priority:** Medium
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** a system operator and hackathon judge
**I want** all log entries and processing steps for a single incident to be linked by a common trace ID
**So that** the complete lifecycle of any incident can be reconstructed from logs in a single query or filter

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Trace ID generated at intake | Given an incident report is received at the intake endpoint, When the request is processed, Then a unique trace ID (`trace_id`) is generated for that incident |
| AC-02 | Trace ID propagated to all stages | Given a trace ID exists for an incident, When each subsequent stage runs (triage, ticket, notify, resolved), Then the same `trace_id` appears in every log entry for that incident |
| AC-03 | Trace ID format correct | Given a trace ID is generated, When examined, Then it is a UUID v4 string (e.g., `550e8400-e29b-41d4-a716-446655440000`) |
| AC-04 | Trace ID distinct per incident | Given two incidents are submitted concurrently, When their log entries are compared, Then each incident has a unique `trace_id` — no sharing |
| AC-05 | Trace ID present in log schema | Given HU-009 log entries are examined, When a `trace_id` is present, Then it appears as a top-level field in every log entry: `{ trace_id, stage, event, incident_id, ... }` |
| AC-06 | Filtering by trace ID reconstructs full lifecycle | Given the application is running and has processed at least one incident, When `docker compose logs agent | grep "TRACE_ID_VALUE"` is run, Then all log entries for that incident appear in sequence |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | The `trace_id` is equivalent to the `incident_id` for this system — they may be the same value or the `trace_id` may be a derived UUID. @architect decides the mapping |
| BR-02 | Trace ID must never be reused across incidents |
| BR-03 | Trace correlation is required for hackathon observability evaluation — "traces" is an explicit requirement in the assignment |
| BR-04 | For hackathon scope, a lightweight custom trace implementation is acceptable — full OpenTelemetry instrumentation is optional (listed as bonus) |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Trace ID lost between service calls (e.g., passed to mock-services) | Trace ID is included as a request header `X-Trace-ID` in all outbound HTTP calls to mock-services — even if mock-services ignores it |
| Two concurrent incidents — trace ID collision | UUID v4 collision probability is negligible; no collision handling required |
| Log entry missing trace_id (developer error) | CI check or code review catches this; no runtime guard needed |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| — | No design — pure logging/instrumentation concern | Optional: observability dashboard showing trace timelines is a bonus extra |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-009 | Extends: trace_id is added as a field to the structured log entries defined in HU-009 |

---

## Technical Notes

- Simplest implementation: use `incident_id` as the `trace_id` (they are generated at the same time and are both unique per incident)
- If @architect selects OpenTelemetry: use the W3C Trace Context standard (traceparent header) — this enables future dashboard integration (Jaeger, Zipkin, LangFuse)
- The X-Trace-ID header should be forwarded to all outbound HTTP calls (mock-services endpoints) even if not consumed by the mock
- This HU is a pre-condition for any observability dashboard bonus feature

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
