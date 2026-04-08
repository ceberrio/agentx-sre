# HU-002 — Multimodal File Attachment

**Module:** Incident Intake
**Epic:** EPIC-001 — Incident Intake
**Priority:** High
**Status:** Approved
**Version:** v1
**Last updated:** 2026-04-07

---

## User Story

**As** an incident reporter
**I want** to attach a file (screenshot, log file, or video) alongside my incident text description
**So that** the SRE Agent has richer multimodal context to produce a more accurate triage summary

---

## Acceptance Criteria

| ID | Criterion | Condition |
|----|-----------|-----------|
| AC-01 | File attachment control is present | Given the incident form is displayed, When the page loads, Then a file upload control (drag-and-drop area or browse button) is visible adjacent to the text input |
| AC-02 | Accepted file types enforced on client | Given the file upload control is displayed, When the user attempts to select a file of unsupported type (e.g., .exe, .zip), Then the browser file picker filters to only allowed types: image (jpg, png, gif, webp), log text (txt, log), video (mp4, webm) |
| AC-03 | File size limit enforced | Given the user selects a file, When the file exceeds 50 MB, Then the control displays an error: "File too large. Maximum size is 50 MB" and does not include the file in the submission |
| AC-04 | Selected file shown before submit | Given the user selects a valid file, When the file is chosen, Then the filename and type icon are displayed in the UI so the user can confirm the selection |
| AC-05 | File removed before submit | Given a file is selected, When the user clicks the remove/clear control, Then the file is deselected and the upload control returns to its empty state |
| AC-06 | Submission includes file when present | Given the user submits the form with text + file, When the request is sent, Then the backend receives the file content (base64-encoded or multipart form-data) alongside the text payload |
| AC-07 | Submission succeeds without file | Given the user submits the form with text only (no file), When the request is sent, Then the submission completes successfully — file is optional |
| AC-08 | File type sent to backend | Given a file is attached, When submitted, Then the backend receives the MIME type of the file so the triage agent knows which modality to process |

---

## Business Rules

| ID | Rule |
|----|------|
| BR-01 | Multimodal input is mandatory at the system level (per hackathon requirements), but the file attachment is optional per individual submission — the reporter may submit text-only |
| BR-02 | Accepted modalities: image (jpg, png, gif, webp), log file (txt, log), video (mp4, webm) — these are the three modalities referenced in the assignment |
| BR-03 | Maximum file size: 50 MB — selected to balance demo viability within Docker Compose and multimodal LLM API limits |
| BR-04 | Only one file attachment per incident report — multiple file support is out of scope for hackathon |
| BR-05 | File content must reach the triage LLM — it cannot be stored only on disk without being passed to the agent pipeline |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User attaches file with wrong extension but valid content | Client-side filter rejects by extension; does not inspect file content |
| File attachment on mobile browser | Standard HTML file input used — mobile camera/gallery access works natively |
| User drags unsupported file type onto drop zone | Error message shown: "File type not supported" |
| File upload control on slow connection (large file) | Show upload progress indicator if file exceeds 5 MB; do not block UI thread |
| LLM provider does not support video modality | This is a triage-layer concern (HU-004) — intake layer always accepts video per accepted types |

---

## Design Reference

| Screen / Component | Reference | Notes |
|-------------------|-----------|-------|
| File Upload Control | No design — UI to be defined by @architect | Drag-and-drop preferred; fallback to browse button |
| File Preview / Selected State | No design — UI to be defined by @architect | Show filename, size, type icon |
| File Error States | No design — UI to be defined by @architect | Inline error below upload control |

---

## Dependencies

| HU | Dependency Type |
|----|----------------|
| HU-001 | Runs in parallel — this HU extends the form defined in HU-001 |
| HU-004 | Must complete before: HU-004 defines how the multimodal payload is consumed by the triage LLM |

---

## Technical Notes

- File transfer strategy: base64-encoded in JSON body for simplicity within Docker Compose (avoids shared volume complexity); @architect may override to multipart form-data
- The `POST /incidents` request body shape (with file): `{ text: string, file: { name: string, mime_type: string, content_base64: string } }`
- Without file: `{ text: string }`
- MIME type must be preserved and forwarded to the LLM API call in HU-004
- 50 MB limit should also be enforced server-side (not only client-side)

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
