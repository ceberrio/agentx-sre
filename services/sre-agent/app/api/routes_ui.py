"""UI routes — serves the HTMX + Tailwind form and result partial.

HU-001: Submit incident via form
HU-002: Upload image/log attachment

Jinja2 templates live in app/ui/templates/.
All heavy logic is in routes_incidents.py — this is a thin UI layer.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.domain.entities import Incident, IncidentStatus
from app.infrastructure.config import settings
from app.infrastructure.container import get_container
from app.orchestration.orchestrator import (
    CaseState,
    CaseStatus,
    build_orchestrator_graph,
)
from app.observability.metrics import incidents_received_total, active_incidents

router = APIRouter(prefix="/ui")

_templates_dir = Path(__file__).parent.parent / "ui" / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the main incident submission form."""
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/submit", response_class=HTMLResponse)
async def submit_incident(
    request: Request,
    reporter_email: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    log_file: UploadFile | None = None,
    image: UploadFile | None = None,
) -> HTMLResponse:
    """HTMX endpoint: run the pipeline, return the result partial."""
    container = get_container()

    # Read file content with size enforcement
    log_text: str | None = None
    image_bytes: bytes | None = None
    image_mime: str | None = None

    if log_file and log_file.filename:
        raw = await log_file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            return templates.TemplateResponse(
                "result_partial.html",
                {
                    "request": request,
                    "error": f"Log file exceeds {settings.max_upload_size_mb} MB limit.",
                },
            )
        log_text = raw.decode("utf-8", errors="replace")

    if image and image.filename:
        raw = await image.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            return templates.TemplateResponse(
                "result_partial.html",
                {
                    "request": request,
                    "error": f"Image exceeds {settings.max_upload_size_mb} MB limit.",
                },
            )
        image_bytes = raw
        image_mime = image.content_type or "image/jpeg"

    incident = Incident(
        id=str(uuid.uuid4()),
        reporter_email=reporter_email,
        title=title,
        description=description,
        status=IncidentStatus.RECEIVED,
        has_log=log_text is not None,
        has_image=image_bytes is not None,
        log_text=log_text,
        image_bytes=image_bytes,
    )

    incidents_received_total.inc()
    active_incidents.inc()

    # Persist the incident before running the pipeline
    await container.storage.save_incident(incident)

    graph = build_orchestrator_graph(container)
    initial_state: CaseState = {
        "case_id": incident.id,
        "incident": incident,
        "status": CaseStatus.NEW,
        "events": [],
    }

    try:
        final_state = await graph.ainvoke(initial_state)
        final_status = final_state.get("status", CaseStatus.NEW)
        triage = final_state.get("triage")
        ticket = final_state.get("ticket")
        blocked = final_status == CaseStatus.INTAKE_BLOCKED
        blocked_reason = final_state.get("blocked_reason")

        # Persist updated state
        patch: dict = {"status": IncidentStatus.RESOLVED if not blocked else IncidentStatus.BLOCKED}
        if triage:
            patch["severity"] = triage.severity
        await container.storage.update_incident(incident.id, patch)

    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).error("ui.pipeline_failed", extra={"error": str(exc)})
        active_incidents.dec()
        return templates.TemplateResponse(
            "result_partial.html",
            {"request": request, "error": f"Pipeline error: {str(exc)[:200]}"},
        )

    active_incidents.dec()

    return templates.TemplateResponse(
        "result_partial.html",
        {
            "request": request,
            "incident_id": incident.id,
            "blocked": blocked,
            "blocked_reason": blocked_reason,
            "triage": triage,
            "ticket": ticket,
            "case_status": final_status.value if hasattr(final_status, "value") else str(final_status),
        },
    )
