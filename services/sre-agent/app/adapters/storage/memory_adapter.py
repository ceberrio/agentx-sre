"""MemoryStorageAdapter — for tests and ultra-fast demo mode (STORAGE_PROVIDER=memory)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from app.domain.entities import Incident
from app.domain.ports import IStorageProvider


class MemoryStorageAdapter(IStorageProvider):
    name = "memory"

    def __init__(self) -> None:
        self._store: dict[str, Incident] = {}
        self._lock = asyncio.Lock()

    async def save_incident(self, incident: Incident) -> None:
        async with self._lock:
            self._store[incident.id] = incident

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self._store.get(incident_id)

    async def update_incident(
        self, incident_id: str, patch: dict[str, Any]
    ) -> Incident:
        async with self._lock:
            current = self._store.get(incident_id)
            if current is None:
                raise KeyError(incident_id)
            updated = current.model_copy(update={**patch, "updated_at": datetime.now(timezone.utc)})
            self._store[incident_id] = updated
            return updated

    async def list_incidents(self, limit: int = 50) -> list[Incident]:
        items = sorted(self._store.values(), key=lambda i: i.created_at, reverse=True)
        return items[:limit]
