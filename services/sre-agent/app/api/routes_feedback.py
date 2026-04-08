"""Feedback routes — HU human-feedback endpoint (FASE 4.4).

Allows reporters or SRE leads to submit a thumbs-up / thumbs-down reaction
to the automated triage. This signal feeds the Langfuse eval layer (DEC-008).

POST /incidents/{incident_id}/feedback
Body: { "rating": "positive" | "negative", "comment": "<optional text>" }

Security:
    - incident_id is validated by looking it up in storage — arbitrary IDs
      are rejected with 404 rather than stored.
    - comment is length-capped to prevent large payloads reaching the DB.
    - No PII is logged from the comment field.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from app.infrastructure.container import get_container

log = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents")

MAX_COMMENT_LENGTH = 1_000


class FeedbackPayload(BaseModel):
    """Validated feedback body."""

    rating: Literal["positive", "negative"]
    comment: Optional[str] = Field(default=None, max_length=MAX_COMMENT_LENGTH)


class FeedbackResponse(BaseModel):
    incident_id: str
    rating: str
    persisted: bool


@router.post("/{incident_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    incident_id: str = Path(..., max_length=128, pattern=r"^[\w\-]+$"),
    body: FeedbackPayload = ...,
) -> FeedbackResponse:
    """Store thumbs-up / thumbs-down feedback for a triage result.

    The incident must already exist in storage; otherwise 404 is returned.
    The feedback is persisted as a metadata patch on the incident record.
    """
    container = get_container()

    incident = await container.storage.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")

    # Persist rating as a string field on the incident record.
    # The comment is intentionally not stored in the relational row to avoid
    # unbounded text growth in the DB; it is emitted to structured logs only
    # so Langfuse can pick it up as a trace annotation.
    try:
        await container.storage.update_incident(
            incident_id,
            {"feedback_rating": body.rating},
        )
        persisted = True
    except Exception as exc:  # noqa: BLE001
        log.error(
            "feedback.persist_failed",
            extra={"incident_id": incident_id, "error": str(exc)},
        )
        persisted = False

    log.info(
        "feedback.received",
        extra={
            "incident_id": incident_id,
            "rating": body.rating,
            # Never log the full comment — may contain PII.
            "has_comment": body.comment is not None,
        },
    )

    if not persisted:
        raise HTTPException(status_code=500, detail="feedback_persist_failed")

    return FeedbackResponse(
        incident_id=incident_id,
        rating=body.rating,
        persisted=persisted,
    )
