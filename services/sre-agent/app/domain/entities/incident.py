"""Incident entity — the central aggregate of the domain."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStatus(str, Enum):
    RECEIVED = "received"
    TRIAGING = "triaging"
    TICKETED = "ticketed"
    RESOLVED = "resolved"
    BLOCKED = "blocked"
    FAILED = "failed"


class Incident(BaseModel):
    """Reported by a user; carried through the 6-stage pipeline."""

    id: str
    reporter_email: str
    title: str
    description: str
    status: IncidentStatus = IncidentStatus.RECEIVED
    severity: Optional[Severity] = None
    blocked: bool = False
    blocked_reason: Optional[str] = None
    has_image: bool = False
    has_log: bool = False
    image_bytes: Optional[bytes] = Field(default=None, exclude=True, repr=False)
    log_text: Optional[str] = Field(default=None, exclude=True, repr=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
