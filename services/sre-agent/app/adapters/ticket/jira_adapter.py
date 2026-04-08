"""JiraTicketAdapter — production stub. @developer fills the auth + payload details."""
from __future__ import annotations

import httpx

from app.domain.entities import Ticket, TicketDraft, TicketStatus
from app.domain.ports import ITicketProvider


class JiraTicketAdapter(ITicketProvider):
    name = "jira"

    def __init__(self, base_url: str, token: str, project_key: str) -> None:
        self._project_key = project_key
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )

    async def create_ticket(self, draft: TicketDraft) -> Ticket:
        raise NotImplementedError("@developer: implement Jira REST v3 createIssue")

    async def get_ticket(self, ticket_id: str) -> Ticket:
        raise NotImplementedError("@developer: implement Jira getIssue")

    async def resolve_ticket(self, ticket_id: str) -> Ticket:
        raise NotImplementedError("@developer: implement Jira transition to Done")
