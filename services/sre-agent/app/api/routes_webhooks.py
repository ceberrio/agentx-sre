"""Webhook routes — DEC-006: async resolution triggered by the ticket system.

Flow:
    1. Mock-services (or real GitLab/Jira) calls POST /webhooks/resolution
       when a ticket is marked resolved.
    2. This handler retrieves the incident from storage, invokes the
       resolution graph (build_resolution_graph) asynchronously, and returns
       202 Accepted immediately so the caller does not time out.

Security:
    - Payload is validated by Pydantic (no raw dict forwarded to agents).
    - The incident_id from the payload is used to look up the canonical
      incident from storage — the payload is never trusted as the source of
      incident data. (SSRF / injection boundary.)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user_or_api_key
from app.domain.entities.user import User
from app.infrastructure.container import get_container
from app.orchestration.orchestrator import (
    CaseState,
    CaseStatus,
    build_resolution_graph,
)
from app.domain.entities import Ticket, TicketStatus

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks")

# Module-level singleton: the resolution graph is compiled once and reused
# for every incoming webhook. Compilation is deferred to the first request
# so the container is fully initialised by the time build_resolution_graph runs.
_resolution_graph: Optional[Any] = None


def _get_resolution_graph():
    """Return the cached compiled resolution graph, building it on first call."""
    global _resolution_graph
    if _resolution_graph is None:
        _resolution_graph = build_resolution_graph(get_container())
    return _resolution_graph


class ResolutionWebhookPayload(BaseModel):
    """Typed webhook body. Validates structure before we touch storage."""

    incident_id: str
    ticket_id: str
    ticket_url: str | None = None


async def _run_resolution_background(
    incident_id: str,
    ticket_id: str,
    ticket_url: str | None,
) -> None:
    """Background task: invoke the resolution graph without blocking the HTTP response."""
    container = get_container()
    incident = await container.storage.get_incident(incident_id)
    if incident is None:
        log.error(
            "webhook.resolution.incident_not_found",
            extra={"incident_id": incident_id, "ticket_id": ticket_id},
        )
        return

    # Build a Ticket domain object from the webhook payload.
    # We do NOT call container.ticket.get_ticket() here because the mock
    # ticket system may already have removed the ticket from memory.
    ticket = Ticket(
        id=ticket_id,
        incident_id=incident_id,
        provider=container.ticket.name,
        url=ticket_url,
        status=TicketStatus.RESOLVED,
    )

    graph = _get_resolution_graph()
    state: CaseState = {
        "case_id": incident_id,
        "incident": incident,
        "ticket": ticket,
        "status": CaseStatus.AWAITING_RESOLUTION,
        "events": [],
    }

    try:
        final_state = await graph.ainvoke(state)
        final_status = final_state.get("status", CaseStatus.AWAITING_RESOLUTION)
        log.info(
            "webhook.resolution.completed",
            extra={"incident_id": incident_id, "final_status": str(final_status)},
        )

        # Persist the RESOLVED status back into storage.
        await container.storage.update_incident(
            incident_id,
            {"status": "resolved", "blocked": False},
        )
    except Exception as exc:  # noqa: BLE001
        log.error(
            "webhook.resolution.failed",
            extra={"incident_id": incident_id, "error": str(exc)},
        )


@router.post("/resolution", status_code=202)
async def resolution_webhook(
    payload: ResolutionWebhookPayload,
    background_tasks: BackgroundTasks,
    _current_user: User = Depends(get_current_user_or_api_key),
) -> dict:
    """Receive a resolution event from the ticket system.

    Returns 202 Accepted immediately. The resolution graph runs in the
    background so the webhook caller does not block on LLM latency.
    """
    incident_id = payload.incident_id.strip()
    ticket_id = payload.ticket_id.strip()

    if not incident_id or not ticket_id:
        raise HTTPException(status_code=422, detail="incident_id and ticket_id are required")

    log.info(
        "webhook.resolution.received",
        extra={"incident_id": incident_id, "ticket_id": ticket_id},
    )

    background_tasks.add_task(
        _run_resolution_background,
        incident_id=incident_id,
        ticket_id=ticket_id,
        ticket_url=payload.ticket_url,
    )

    return {"accepted": True, "incident_id": incident_id, "ticket_id": ticket_id}
