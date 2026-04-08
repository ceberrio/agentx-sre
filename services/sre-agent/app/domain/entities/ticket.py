"""Ticket entity — produced by ITicketProvider, never by the domain itself."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .incident import Severity


class TicketStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class TicketDraft(BaseModel):
    """The domain hands this to ITicketProvider.create_ticket()."""

    incident_id: str
    title: str
    description: str
    severity: Severity
    labels: list[str] = Field(default_factory=list)


class Ticket(BaseModel):
    """The provider hands this back."""

    id: str
    incident_id: str
    provider: str  # "mock" | "gitlab" | "jira"
    url: Optional[str] = None
    status: TicketStatus = TicketStatus.OPEN
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
