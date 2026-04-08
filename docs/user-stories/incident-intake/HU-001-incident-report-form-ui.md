# HU-001 — Incident Report Form UI

**Module:** Incident Intake
**Epic:** EPIC-001 — Incident Intake
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** an incident reporter (SRE engineer or on-call team member)
**I want** a web UI form where I can describe an incident in text and optionally attach a file (image, log, or video)
**So that** the SRE Agent receives a complete and structured incident report to begin automated triage

---

## Acceptance Criteria

> ACs are verifiable conditions. Each one must be independently testable.

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | Form renders on load | Given the user opens the application URL, When the page loads, Then an incident report form is displayed with a text field, a file attachment area, and a submit button |
| AC-02 | Text input is mandatory | Given the form is displayed, When the user clicks Submit without entering any text, Then the form shows a validation error: "Incident description is required" and does not submit |
| AC-03 | Successful submission with text only | Given the user enters a valid text description, When the user clicks Submit, Then the form submits successfully and the user sees a confirmation message containing the assigned incident ID |
| AC-04 | Successful submission with text + file | Given the user enters text and attaches a valid file (image, log file, or video), When the user clicks Submit, Then the payload is sent with both the text and file reference, and the user sees confirmation with incident ID |
| AC-05 | Submit button shows loading state | Given the form is submitted, When the request is in flight, Then the Submit button is disabled and shows a loading indicator until the response is received |
| AC-06 | API error handled gracefully | Given the backend returns a 5xx error, When the submission fails, Then the user sees an error message: "Submission failed. Please try again." and the form data is preserved |
| AC-07 | Confirmation includes incident ID | Given a successful submission, When the response is received, Then the UI displays the incident ID returned by the backend (format: INC-XXXXXXXX) |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | Text description is the only mandatory field — all file attachments are optional |
| BR-02 | The form must be accessible without authentication for hackathon demo purposes |
| BR-03 | The incident ID displayed to the reporter must match the ID stored in the backend and used for all subsequent stages |
| BR-04 | Form must be functional within Docker Compose environment — no external CDN dependencies that would break in offline demo |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User submits empty form | Validation error shown; no API call made |
| Network timeout on submission | Error message shown after timeout; form data preserved |
| User submits and immediately closes browser | The backend still processes the report; no data loss |
| Very long text input (>10,000 characters) | Form accepts the text; backend handles truncation if needed (not a UI concern) |
| Multiple rapid submit clicks | Only one submission sent (button disabled after first click) |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| Incident Report Form | No design — UI to be defined by @architect | Single-page form layout |
| Confirmation / Success State | No design — UI to be defined by @architect | Must display INC-XXXXXXXX format ID |
| Error State | No design — UI to be defined by @architect | Inline form error messages |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-002 | Runs in parallel — HU-002 defines the multimodal file attachment behavior embedded in this form |
| HU-004 | Must complete before: HU-004 defines the triage endpoint that this form's submit action calls |

---

## Technical Notes

- The form submit action calls `POST /incidents` on the backend API
- The backend endpoint must return `{ incident_id: "INC-XXXXXXXX" }` in the success response
- File payload is handled by HU-002; this HU covers text submission and response display
- All UI must be served from within the Docker Compose network — no external stylesheet dependencies that require internet access during demo
- Incident ID format: `INC-` prefix followed by 8 alphanumeric characters (e.g., INC-A3F9B12C)

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
