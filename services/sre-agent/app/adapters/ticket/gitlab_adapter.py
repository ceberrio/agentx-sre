"""GitLabTicketAdapter — production. Talks to /api/v4/projects/:id/issues."""
from __future__ import annotations

import httpx

from app.domain.entities import Ticket, TicketDraft, TicketStatus
from app.domain.ports import ITicketProvider


class GitLabTicketAdapter(ITicketProvider):
    name = "gitlab"

    def __init__(self, base_url: str, token: str, project_id: str) -> None:
        self._project_id = project_id
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"PRIVATE-TOKEN": token},
            timeout=15.0,
        )

    async def create_ticket(self, draft: TicketDraft) -> Ticket:
        r = await self._client.post(
            f"/api/v4/projects/{self._project_id}/issues",
            json={
                "title": draft.title,
                "description": draft.description,
                "labels": ",".join(draft.labels + [f"severity:{draft.severity.value}"]),
            },
        )
        r.raise_for_status()
        data = r.json()
        return Ticket(
            id=str(data["iid"]),
            incident_id=draft.incident_id,
            provider=self.name,
            url=data.get("web_url"),
            status=TicketStatus.OPEN,
        )

    async def get_ticket(self, ticket_id: str) -> Ticket:
        r = await self._client.get(
            f"/api/v4/projects/{self._project_id}/issues/{ticket_id}"
        )
        r.raise_for_status()
        data = r.json()
        return Ticket(
            id=str(data["iid"]),
            incident_id=str(data.get("description_incident_id", "")),
            provider=self.name,
            url=data.get("web_url"),
            status=TicketStatus.OPEN if data.get("state") == "opened" else TicketStatus.RESOLVED,
        )

    async def resolve_ticket(self, ticket_id: str) -> Ticket:
        r = await self._client.put(
            f"/api/v4/projects/{self._project_id}/issues/{ticket_id}",
            json={"state_event": "close"},
        )
        r.raise_for_status()
        return await self.get_ticket(ticket_id)
