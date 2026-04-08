# HU-004 — LLM Triage Analysis (eShop Codebase Context)

**Module:** Triage Agent
**Epic:** EPIC-002 — Triage Agent
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** the SRE Agent
**I want** to analyze the incident report (text + optional file) using a multimodal LLM with the eShop codebase and documentation as context
**So that** the triage produces an accurate, technically grounded initial assessment of what is failing and why

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Triage executes after guardrail passes | Given a report has passed the HU-003 guardrail check, When the triage stage begins, Then the multimodal LLM is called with the incident text and any attached file |
| AC-02 | eShop context injected into LLM prompt | Given the triage LLM is called, When the system prompt is constructed, Then it includes relevant eShop architectural context (service names, key modules, known failure patterns from eShop documentation) — not the entire repo, but curated context |
| AC-03 | Text-only report processed successfully | Given the incident report contains only text (no file), When the LLM is called, Then the triage completes successfully using the text and eShop context |
| AC-04 | Image modality processed | Given the incident report includes an image (jpg, png, gif, webp), When the LLM is called, Then the image is passed to the multimodal LLM alongside the text (not discarded) |
| AC-05 | Log file modality processed | Given the incident report includes a log file (txt, log), When the LLM is called, Then the log file text content is included in the LLM context |
| AC-06 | Video modality handled | Given the incident report includes a video (mp4, webm), When the LLM is called, Then the video is passed to the multimodal LLM if the provider supports it; if not supported, the agent logs a warning and proceeds with text-only triage |
| AC-07 | Technical summary produced | Given the LLM returns a response, When triage completes, Then a technical summary object is produced containing: `{ summary: string, affected_service: string, severity: "low|medium|high|critical", key_findings: string[] }` |
| AC-08 | LLM failure handled | Given the LLM API returns a 5xx error or timeout, When the failure occurs, Then the incident is not silently dropped — a structured error is logged and the incident status is set to `triage_failed` |
| AC-09 | Triage does not mutate the original report | Given the triage runs, When it completes, Then the original incident text and file are preserved unchanged in storage — triage only produces an additional summary object |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | The LLM used MUST be multimodal (capable of processing text + image at minimum) — this is a mandatory hackathon requirement |
| BR-02 | eShop context must be pre-processed and curated into the system prompt — the entire repository MUST NOT be passed verbatim (token limit concern) |
| BR-03 | The LLM must operate in a constrained role: "You are an SRE triage assistant. Analyze this incident report in the context of the eShop e-commerce system." — role must not be overridable by incident content |
| BR-04 | Severity classification must always be one of: low, medium, high, critical — free-form severity text is not acceptable |
| BR-05 | The LLM must not have access to any tools that execute code or make network calls — only read-only context access |
| BR-06 | Triage must complete within 60 seconds — if the LLM does not respond within this window, it is treated as a failure |
| BR-07 | The affected_service field must reference eShop service names where possible (e.g., "Catalog API", "Ordering API", "Basket API", "Identity API") |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| LLM returns malformed JSON or free-text instead of structured output | Agent attempts to parse; if parsing fails, wraps the raw response in `{ summary: raw_text, affected_service: "unknown", severity: "medium", key_findings: [] }` and logs a parse warning |
| LLM API rate limit hit | Retry once after 2 seconds; if still rate-limited, set status to `triage_failed` and log the error |
| Incident text is very short (e.g., "site is down") | Triage proceeds with minimal context; LLM produces a best-effort summary noting limited information |
| eShop context does not match the described incident (novel failure) | LLM produces a summary noting "no matching eShop component identified" — does not hallucinate a specific service |
| Multiple rapid incidents submitted concurrently | Each triage runs independently and in parallel — no shared mutable state between triage invocations |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| — | No design — pure backend logic | Triage is an agent pipeline stage with no dedicated UI component |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-003 | Must complete before: triage only runs if guardrail passes |
| HU-005 | Shares entity: HU-005 consumes the technical summary object produced by this HU |
| HU-009 | Shares logging contract: triage events (LLM call started, completed, failed) must be logged per the observability schema |

---

## Technical Notes

- eShop context preparation: pre-extract key services, endpoints, and common failure patterns from the eShop repository into a static markdown document bundled with the agent service. This document forms the "knowledge base" injected into the system prompt.
- eShop target repo: Microsoft eShop (MIT license) — DEC-002 confirmed
- LLM provider decision is @architect's responsibility — this HU only requires the provider to be multimodal and support structured output (JSON mode or function calling)
- The structured output schema must be enforced via the LLM API's structured output feature (not just prompt instruction) to guarantee parseable responses
- Triage stage observability log entry format: `{ stage: "triage", event: "llm_call_start|llm_call_complete|llm_call_failed", incident_id: string, duration_ms: number, model: string }`

---

## Pending Questions

| # | Question | Directed To | Status |
|---|----------|------------|--------|
| — | No pending questions — eShop and multimodal LLM decided (DEC-002) | — | — |

---

## Change History

| Version | Date | Change | Reason |
|---------|------|--------|--------|
| v1 | 2026-04-07 | Initial creation | First refinement pass — hackathon kick-off |
