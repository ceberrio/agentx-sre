"""Notification value objects."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class TeamNotification(BaseModel):
    incident_id: str
    ticket_id: str
    title: str
    summary: str
    severity: str
    recipients: list[str] = Field(default_factory=list)


class ReporterNotification(BaseModel):
    incident_id: str
    ticket_id: str
    reporter_email: str
    subject: str
    body: str


class NotificationReceipt(BaseModel):
    delivered: bool
    provider: str
    channel: str  # "team" | "reporter"
    message_id: Optional[str] = None
    delivered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
