"""HTTP layer — thin. Translates HTTP to Incident, runs the graph, returns JSON."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.domain.entities import Incident
from app.infrastructure.container import get_container
from app.orchestration.orchestrator import (
    CaseState,
    CaseStatus,
    build_orchestrator_graph,
    build_resolution_graph,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents")


@router.post("")
async def create_incident(
    reporter_email: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    log_file: UploadFile | None = None,
    image: UploadFile | None = None,
) -> dict:
    container = get_container()
    incident = Incident(
        id=str(uuid.uuid4()),
        reporter_email=reporter_email,
        title=title,
        description=description,
        has_log=log_file is not None,
        has_image=image is not None,
        log_text=(await log_file.read()).decode("utf-8", errors="replace") if log_file else None,
        image_bytes=await image.read() if image else None,
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
    return {
        "incident_id": incident.id,
        "case_status": final_status.value if hasattr(final_status, "value") else str(final_status),
        "blocked": final_status == CaseStatus.INTAKE_BLOCKED,
        "ticket_id": final_state["ticket"].id if final_state.get("ticket") else None,
        "severity": severity,
    }


@router.get("")
async def list_incidents() -> list[dict]:
    container = get_container()
    items = await container.storage.list_incidents()
    return [i.model_dump(mode="json") for i in items]


@router.get("/{incident_id}")
async def get_incident(incident_id: str) -> dict:
    container = get_container()
    incident = await container.storage.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")
    return incident.model_dump(mode="json")


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str) -> dict:
    """Manual resolution trigger (DEC-004)."""
    container = get_container()
    incident = await container.storage.get_incident(incident_id)
    if incident is None:
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
