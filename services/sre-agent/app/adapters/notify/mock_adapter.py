"""MockNotifyAdapter — talks to mock-services /notify/team and /notify/email."""
from __future__ import annotations

import httpx

from app.domain.entities import (
    NotificationReceipt,
    ReporterNotification,
    TeamNotification,
)
from app.domain.ports import INotifyProvider


class MockNotifyAdapter(INotifyProvider):
    name = "mock"

    def __init__(self, base_url: str, timeout_s: float = 10.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout_s
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def notify_team(self, msg: TeamNotification) -> NotificationReceipt:
        r = await self._client.post("/notify/team", json=msg.model_dump())
        r.raise_for_status()
        return NotificationReceipt(
            delivered=True,
            provider=self.name,
            channel="team",
            message_id=r.json().get("id"),
        )

    async def notify_reporter(self, msg: ReporterNotification) -> NotificationReceipt:
        r = await self._client.post("/notify/email", json=msg.model_dump())
        r.raise_for_status()
        return NotificationReceipt(
            delivered=True,
            provider=self.name,
            channel="reporter",
            message_id=r.json().get("id"),
        )
