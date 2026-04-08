"""mock-services — GitLab-Issues-compatible mock for hackathon demo.

Implements the full contract required by the sre-agent adapters:
  GET  /health
  POST /tickets                  -> create ticket
  GET  /tickets/{id}             -> get ticket
  POST /tickets/{id}/resolve     -> resolve ticket (triggers webhook to sre-agent)
  POST /notify/team              -> log team notification
  POST /notify/email             -> log email notification
  GET  /notifications            -> list all notifications (demo read-back)

All data is held in-memory (dict). Designed for hackathon demo only.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)

app = FastAPI(title="mock-services", version="1.0.0")

# In-memory stores
_tickets: dict[str, dict] = {}
_notifications: list[dict] = []

# Where to POST the resolution webhook — sre-agent webhook endpoint
SRE_AGENT_WEBHOOK_URL = os.getenv("SRE_AGENT_WEBHOOK_URL", "http://sre-agent:8000/webhooks/resolution")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class TicketCreateRequest(BaseModel):
    title: str
    description: str
    labels: list[str] = []
    incident_id: str


class TeamNotifyRequest(BaseModel):
    incident_id: str
    ticket_id: str
    title: str
    summary: str
    severity: str
    recipients: list[str] = []


class EmailNotifyRequest(BaseModel):
    incident_id: str
    ticket_id: str
    reporter_email: str
    subject: str
    body: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "tickets": len(_tickets),
        "notifications": len(_notifications),
    }


@app.post("/tickets", status_code=201)
async def create_ticket(req: TicketCreateRequest) -> dict:
    ticket_id = str(uuid.uuid4())[:8]
    ticket = {
        "id": ticket_id,
        "incident_id": req.incident_id,
        "title": req.title,
        "description": req.description,
        "labels": req.labels,
        "status": "open",
        "url": f"http://mock-services:9000/tickets/{ticket_id}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _tickets[ticket_id] = ticket
    log.info("ticket.created", extra={"ticket_id": ticket_id, "incident_id": req.incident_id})
    return ticket


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str) -> dict:
    ticket = _tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket_not_found")
    return ticket


@app.post("/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str) -> dict:
    ticket = _tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket_not_found")

    ticket["status"] = "resolved"
    ticket["resolved_at"] = datetime.now(timezone.utc).isoformat()
    _tickets[ticket_id] = ticket

    log.info("ticket.resolved", extra={"ticket_id": ticket_id})

    # Trigger resolution webhook to sre-agent asynchronously
    asyncio.create_task(_trigger_resolution_webhook(ticket))

    return ticket


async def _trigger_resolution_webhook(ticket: dict) -> None:
    """POST to sre-agent resolution webhook after a ticket is resolved."""
    payload = {
        "ticket_id": ticket["id"],
        "incident_id": ticket["incident_id"],
        "status": "resolved",
        "resolved_at": ticket.get("resolved_at"),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(SRE_AGENT_WEBHOOK_URL, json=payload)
            log.info(
                "webhook.sent",
                extra={"url": SRE_AGENT_WEBHOOK_URL, "status": r.status_code},
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("webhook.failed", extra={"error": str(exc)})


@app.post("/notify/team")
async def notify_team(req: TeamNotifyRequest) -> dict:
    notification = {
        "id": str(uuid.uuid4())[:8],
        "type": "team",
        "incident_id": req.incident_id,
        "ticket_id": req.ticket_id,
        "title": req.title,
        "summary": req.summary,
        "severity": req.severity,
        "recipients": req.recipients,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    _notifications.append(notification)
    log.info(
        "notify.team.received",
        extra={"incident_id": req.incident_id, "recipients": req.recipients},
    )
    return {"id": notification["id"], "delivered": True}


@app.post("/notify/email")
async def notify_email(req: EmailNotifyRequest) -> dict:
    notification = {
        "id": str(uuid.uuid4())[:8],
        "type": "email",
        "incident_id": req.incident_id,
        "ticket_id": req.ticket_id,
        "to": req.reporter_email,
        "subject": req.subject,
        "body": req.body,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    _notifications.append(notification)
    log.info(
        "notify.email.received",
        extra={"incident_id": req.incident_id, "to": req.reporter_email},
    )
    return {"id": notification["id"], "delivered": True}


@app.get("/notifications")
async def list_notifications() -> list[dict]:
    """Return all notifications — used by the demo UI."""
    return list(reversed(_notifications))
