"""ITicketProvider — abstracts GitLab / Jira / mock."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities import Ticket, TicketDraft


class ITicketProvider(ABC):
    name: str

    @abstractmethod
    async def create_ticket(self, draft: TicketDraft) -> Ticket: ...

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Ticket: ...

    @abstractmethod
    async def resolve_ticket(self, ticket_id: str) -> Ticket: ...
