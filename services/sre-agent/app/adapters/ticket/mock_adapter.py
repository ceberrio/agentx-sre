"""MockTicketAdapter — talks to the mock-services container.

The mock service exposes a GitLab-Issues-compatible API at MOCK_SERVICES_URL.
This adapter is the default for hackathon demo runs.
"""
from __future__ import annotations

import httpx

from app.domain.entities import Ticket, TicketDraft, TicketStatus
from app.domain.ports import ITicketProvider


class MockTicketAdapter(ITicketProvider):
    name = "mock"

    def __init__(self, base_url: str, timeout_s: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout_s)

    async def create_ticket(self, draft: TicketDraft) -> Ticket:
        r = await self._client.post(
            "/tickets",
            json={
                "title": draft.title,
                "description": draft.description,
                "labels": draft.labels + [f"severity:{draft.severity.value}"],
                "incident_id": draft.incident_id,
            },
        )
        r.raise_for_status()
        data = r.json()
        return Ticket(
            id=str(data["id"]),
            incident_id=draft.incident_id,
            provider=self.name,
            url=data.get("url"),
            status=TicketStatus.OPEN,
        )

    async def get_ticket(self, ticket_id: str) -> Ticket:
        r = await self._client.get(f"/tickets/{ticket_id}")
        r.raise_for_status()
        data = r.json()
        return Ticket(
            id=str(data["id"]),
            incident_id=data["incident_id"],
            provider=self.name,
            url=data.get("url"),
            status=TicketStatus(data.get("status", "open")),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def resolve_ticket(self, ticket_id: str) -> Ticket:
        r = await self._client.post(f"/tickets/{ticket_id}/resolve")
        r.raise_for_status()
        data = r.json()
        return Ticket(
            id=str(data["id"]),
            incident_id=data["incident_id"],
            provider=self.name,
            url=data.get("url"),
            status=TicketStatus.RESOLVED,
        )
