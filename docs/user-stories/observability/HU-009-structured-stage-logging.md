# HU-009 — Structured Stage Logging

**Module:** Observability
**Epic:** EPIC-003 — Observability
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** a system operator and hackathon judge
**I want** every stage of the SRE Agent pipeline to emit structured JSON log entries
**So that** the system's behavior is fully observable, debuggable, and demonstrates engineering discipline to evaluators

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Ingest stage logged | Given an incident report is received, When the intake endpoint processes it, Then a log entry is emitted: `{ stage: "ingest", event: "report_received", incident_id, timestamp, reporter_id_or_ip, modalities: string[] }` |
| AC-02 | Guardrail check logged | Given the guardrail layer runs (HU-003), When the check completes, Then a log entry is emitted: `{ stage: "ingest", event: "guardrail_check", result: "pass|reject", reason: string, incident_id, timestamp }` |
| AC-03 | Triage start and completion logged | Given the triage LLM call runs, When the call starts and when it completes, Then two log entries are emitted: `{ stage: "triage", event: "llm_call_start", incident_id, model, timestamp }` and `{ stage: "triage", event: "llm_call_complete", incident_id, duration_ms, severity, timestamp }` |
| AC-04 | Triage failure logged | Given the LLM returns an error, When the failure occurs, Then a log entry is emitted: `{ stage: "triage", event: "llm_call_failed", incident_id, error_code, timestamp }` |
| AC-05 | Ticket stage logged | Given the ticket creation call runs, When it completes, Then a log entry is emitted: `{ stage: "ticket", event: "ticket_created|ticket_failed", incident_id, ticket_id, duration_ms, timestamp }` |
| AC-06 | Notify stage logged | Given the team notification runs, When each channel call completes, Then a log entry is emitted per channel: `{ stage: "notify", event: "team_notified|email_sent|notify_failed", incident_id, ticket_id, channel, status_code, duration_ms, timestamp }` |
| AC-07 | Resolution stage logged | Given the resolution event is received and reporter notification runs, When it completes, Then a log entry is emitted: `{ stage: "resolved", event: "resolution_received|reporter_notified|reporter_notify_failed", incident_id, ticket_id, duration_ms, timestamp }` |
| AC-08 | All logs are valid JSON | Given any log entry is emitted, When examined, Then it is parseable JSON on a single line (newline-delimited JSON / NDJSON format) — not free-form text |
| AC-09 | Logs visible via docker compose logs | Given the application is running via `docker compose up --build`, When `docker compose logs -f agent` is run, Then structured JSON log lines for all stages appear in the terminal output |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | ALL 5 pipeline stages must have log coverage: ingest, triage, ticket, notify, resolved — partial coverage is a failing criterion per the hackathon evaluation |
| BR-02 | Log format must be structured JSON (not plain text) — this is a hackathon evaluation criterion for observability |
| BR-03 | The `stage` field must use exactly these values: "ingest", "triage", "ticket", "notify", "resolved" — consistent naming is required for log analysis |
| BR-04 | The `incident_id` field must be present in every log entry after intake — it is the correlation key for tracing a full incident lifecycle |
| BR-05 | Log entries must not contain sensitive data: no LLM API keys, no full file content, no personal reporter data beyond ID |
| BR-06 | Timestamps must be ISO 8601 format (e.g., `2026-04-07T14:30:00.000Z`) |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Log emission itself throws an error | Exception is swallowed and printed to stderr — log failures must NEVER crash the agent pipeline |
| Very high log volume (many concurrent incidents) | Each log entry is atomic — no interleaved JSON across entries (one JSON object per line) |
| Docker container restarts | Previous logs are lost (no persistent log storage required for hackathon); this is acceptable |
| Incident ID not yet assigned (before intake completes) | Log entry uses `"incident_id": null` for the first event only |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| — | No design — pure backend logging | Log output visible via `docker compose logs` |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-003 | Shares logging schema — guardrail events use this format |
| HU-004 | Shares logging schema — triage events use this format |
| HU-005 | Shares logging schema — summary storage events use this format |
| HU-006 | Shares logging schema — ticket events use this format |
| HU-007 | Shares logging schema — notification events use this format |
| HU-008 | Shares logging schema — resolution events use this format |
| HU-010 | Runs in parallel — HU-010 adds trace IDs that correlate with these log entries |

---

## Technical Notes

- Recommended log library: any structured JSON logger available in the chosen stack (e.g., Winston for Node.js, structlog for Python, Serilog for .NET)
- Log output to stdout — Docker collects stdout by default, making logs visible via `docker compose logs`
- NDJSON format: each log entry is a single JSON object on one line, followed by `\n`
- The `duration_ms` field should be calculated for any event that represents a completed operation (not for "start" events)
- Consider adding a `correlation_id` (trace ID) field per HU-010 to link all log entries for a single incident

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
