"""HTTP layer — thin. Translates HTTP to Incident, runs the graph, returns JSON.

Auth (HU-P018):
  POST /incidents            — any authenticated user (Bearer JWT or X-API-Key)
  GET  /incidents            — any authenticated user
  GET  /incidents/{id}       — any authenticated user
  POST /incidents/{id}/resolve — operator, flow_configurator, admin, superadmin
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from app.api.deps import get_current_user_or_api_key, require_role
from app.domain.entities import Incident
from app.domain.entities.user import User, UserRole
from app.infrastructure.config import settings
from app.infrastructure.container import get_container
from app.orchestration.orchestrator import (
    CaseState,
    CaseStatus,
    build_orchestrator_graph,
    build_resolution_graph,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents")


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Stream-read an upload file, aborting if it exceeds max_bytes (SEC-MJ-007).

    Reading the entire file into RAM before any size check would allow an
    attacker to exhaust container memory with a crafted multipart request.
    This helper reads in 64 KiB chunks and raises HTTP 413 as soon as the
    running total exceeds the configured limit.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(65536):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Upload exceeds size limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("")
async def create_incident(
    reporter_email: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    log_file: UploadFile | None = None,
    image: UploadFile | None = None,
    _current_user: User = Depends(get_current_user_or_api_key),
) -> dict:
    container = get_container()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    log_text: str | None = None
    if log_file is not None:
        raw = await _read_limited(log_file, max_bytes)
        log_text = raw.decode("utf-8", errors="replace")

    image_bytes: bytes | None = None
    if image is not None:
        image_bytes = await _read_limited(image, max_bytes)

    incident = Incident(
        id=str(uuid.uuid4()),
        reporter_email=reporter_email,
        title=title,
        description=description,
        has_log=log_file is not None,
        has_image=image is not None,
        log_text=log_text,
        image_bytes=image_bytes,
    )

    # Persist the incident before running the pipeline so it is retrievable
    # by subsequent endpoints (feedback, webhooks) regardless of pipeline outcome.
    await container.storage.save_incident(incident)

    graph = build_orchestrator_graph(container)
    state: CaseState = {
        "case_id": incident.id,
        "incident": incident,
        "status": CaseStatus.NEW,
        "events": [],
    }
    try:
        final_state = await graph.ainvoke(state)
    except Exception as exc:
        log.error("api.graph_invocation_failed", extra={"incident_id": incident.id, "error": str(exc)})
        raise HTTPException(status_code=500, detail="incident_processing_failed")

    final_status = final_state.get("status", CaseStatus.NEW)
    severity = None
    if final_state.get("triage") is not None:
        severity = final_state["triage"].severity.value
    is_blocked = final_status == CaseStatus.INTAKE_BLOCKED
    response: dict = {
        "incident_id": incident.id,
        "case_status": final_status.value if hasattr(final_status, "value") else str(final_status),
        "blocked": is_blocked,
        "ticket_id": final_state["ticket"].id if final_state.get("ticket") else None,
        "severity": severity,
    }
    if is_blocked:
        response["blocked_reason"] = final_state.get("blocked_reason")
    return response


@router.get("")
async def list_incidents(
    current_user: User = Depends(get_current_user_or_api_key),
) -> list[dict]:
    container = get_container()
    items = await container.storage.list_incidents()
    # RBAC filter: operators only see their own incidents (ARC-022, least-privilege).
    if current_user.role == UserRole.OPERATOR:
        items = [i for i in items if i.reporter_email == current_user.email]
    return [i.model_dump(mode="json") for i in items]


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    current_user: User = Depends(get_current_user_or_api_key),
) -> dict:
    container = get_container()
    incident = await container.storage.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    # IDOR guard (VUL-M03): operators may only access their own incidents.
    if current_user.role == UserRole.OPERATOR and incident.reporter_email != current_user.email:
        raise HTTPException(status_code=404, detail="incident_not_found")
    return incident.model_dump(mode="json")


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    current_user: User = Depends(
        require_role(
            UserRole.OPERATOR,
            UserRole.FLOW_CONFIGURATOR,
            UserRole.ADMIN,
            UserRole.SUPERADMIN,
        )
    ),
) -> dict:
    """Manual resolution trigger (DEC-004).

    Requires at minimum operator role. Viewers cannot trigger resolution.
    """
    container = get_container()
    incident = await container.storage.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    # IDOR guard (VUL-M03): operators may only resolve their own incidents.
    if current_user.role == UserRole.OPERATOR and incident.reporter_email != current_user.email:
        raise HTTPException(status_code=404, detail="incident_not_found")

    # Look up the ticket via provider — in mock mode this round-trips through mock-services
    # The ticket id is recovered from the incident description in the mock; in real adapters,
    # it would be persisted alongside the incident. (See SCALING.md for migration note.)
    ticket = await container.ticket.resolve_ticket(incident_id)
    graph = build_resolution_graph(container)
    state: CaseState = {
        "case_id": incident_id,
        "incident": incident,
        "ticket": ticket,
        "status": CaseStatus.AWAITING_RESOLUTION,
        "events": [],
    }
    await graph.ainvoke(state)
    return {"incident_id": incident_id, "status": "resolved"}
