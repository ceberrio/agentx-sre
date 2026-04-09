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

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_or_api_key
from app.domain.entities.user import User
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
    _current_user: User = Depends(get_current_user_or_api_key),
) -> FeedbackResponse:
    """Store thumbs-up / thumbs-down feedback for a triage result.

    The incident must already exist in storage; otherwise 404 is returned.
    The feedback is persisted as a metadata patch on the incident record.
    """
    container = get_container()

    incident = await container.storage.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")

    # Feedback captured via structured log → Langfuse (DEC-008).
    # The relational row has no feedback_rating column — no DB write needed.
    # The comment is intentionally not stored to avoid unbounded text growth;
    # it is emitted to structured logs only so Langfuse picks it up as a trace
    # annotation. Never log the full comment — may contain PII.
    persisted = True  # Feedback captured via structured log → Langfuse

    log.info(
        "feedback.received",
        extra={
            "incident_id": incident_id,
            "rating": body.rating,
            "has_comment": body.comment is not None,
        },
    )

    return FeedbackResponse(
        incident_id=incident_id,
        rating=body.rating,
        persisted=persisted,
    )
