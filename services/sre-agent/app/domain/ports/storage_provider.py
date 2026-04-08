"""IStorageProvider — abstracts in-memory / Postgres."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.domain.entities import Incident


class IStorageProvider(ABC):
    name: str

    @abstractmethod
    async def save_incident(self, incident: Incident) -> None: ...

    @abstractmethod
    async def get_incident(self, incident_id: str) -> Optional[Incident]: ...

    @abstractmethod
    async def update_incident(
        self, incident_id: str, patch: dict[str, Any]
    ) -> Incident: ...

    @abstractmethod
    async def list_incidents(self, limit: int = 50) -> list[Incident]: ...
