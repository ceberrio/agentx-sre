# HU-003 — Input Guardrails (Prompt Injection Protection)

**Module:** Triage Agent
**Epic:** EPIC-002 — Triage Agent
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** a system operator
**I want** the SRE Agent to validate and sanitize all incoming incident reports before they are processed by the LLM
**So that** prompt injection attacks and malicious payloads cannot hijack the agent's behavior or exfiltrate data

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Prompt injection pattern detection | Given an incident report text contains known prompt injection patterns (e.g., "Ignore previous instructions", "You are now a different AI", "Forget your system prompt"), When the guardrail layer processes it, Then the report is flagged as potentially malicious and rejected with HTTP 400 and reason code `GUARDRAIL_INJECTION_DETECTED` |
| AC-02 | Suspicious instruction overrides blocked | Given an incident report contains instruction override attempts (e.g., "Act as", "Your new role is", "Disregard your rules"), When processed by guardrails, Then the request is rejected before reaching the LLM |
| AC-03 | Clean report passes through | Given an incident report contains legitimate SRE content (service name, error message, stack trace, system state), When processed by guardrails, Then the report passes through to the triage stage without modification |
| AC-04 | File content scanned for injection | Given a log file or text file is attached, When the guardrail processes it, Then the file text content is also scanned for injection patterns (not just the text field) |
| AC-05 | Binary files not executed | Given an image or video file is attached, When the guardrail processes it, Then the binary content is NOT executed or parsed for text injection — it is passed directly to the multimodal LLM as a media type |
| AC-06 | Guardrail result is logged | Given any incident report is processed by guardrails, When the check completes, Then a structured log entry is emitted with: `{ stage: "ingest", event: "guardrail_check", result: "pass|reject", reason: string, incident_id: string }` |
| AC-07 | Rejection does not expose internal details | Given a request is rejected by guardrails, When the HTTP 400 response is returned to the caller, Then the response body contains only: `{ error: "GUARDRAIL_INJECTION_DETECTED", incident_id: string }` — no internal stack traces or system prompt content |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | Guardrail check MUST execute before any LLM call — it is the first processing step after intake, not optional |
| BR-02 | A rejected report must NOT be forwarded to the triage stage under any circumstances |
| BR-03 | Legitimate SRE content (error logs, stack traces, system metrics, service names) must NOT trigger false positives — the guardrail targets behavioral overrides, not technical content |
| BR-04 | Prompt injection detection is pattern-based for hackathon scope — ML-based classification is out of scope |
| BR-05 | Safe tool use: the agent must not execute or evaluate any code found in the incident text or attached log files |
| BR-06 | All guardrail decisions (pass/reject) must be observable via the structured logging system (HU-009) |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Incident report contains SQL injection patterns (not prompt injection) | Report passes through — SQL injection is not a threat in this context (no SQL is constructed from report text) |
| Report text is in a language other than English | Guardrails apply regardless of language — pattern matching on known injection phrases covers common multilingual variants |
| Attached log file contains "sudo" commands | Not a prompt injection — passes through; the agent does not execute file content |
| Extremely long text (>10,000 characters) | Guardrail scans the full text; no truncation before scanning |
| Empty text field (only file attached) | If the UI allows this edge case, guardrail processes the file content only; no false positives on empty text |
| Attacker encodes injection in base64 within text | Out of scope for hackathon — base64 decoding detection is not required |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| — | No design — pure backend logic | Guardrail is a server-side processing layer with no dedicated UI |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-001 | Guardrail receives input from the incident submission endpoint defined in HU-001 |
| HU-002 | File content for scanning comes from the multimodal attachment defined in HU-002 |
| HU-004 | Must complete before: HU-004 (triage) only executes if HU-003 guardrail passes |
| HU-009 | Shares logging contract — guardrail events must conform to the structured log schema |

---

## Technical Notes

- Guardrail implementation: pattern-matching list of known prompt injection phrases stored in a config file (not hardcoded)
- Minimum injection patterns to cover: "ignore previous instructions", "disregard", "you are now", "act as", "your new role", "forget your", "override", "system prompt", "jailbreak"
- The guardrail runs as a middleware/function call BEFORE the LLM invocation — not as a separate LLM call (to avoid latency and circular injection risk)
- The rejection HTTP status is 400 (Bad Request) — not 403 — because the content is malformed from the system's perspective
- Log field `result` values: `"pass"` or `"reject"`
- This HU covers text injection; image/video content injection via steganography is explicitly out of scope

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
