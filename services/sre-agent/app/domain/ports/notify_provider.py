"""INotifyProvider — abstracts Slack / Email / Teams / mock."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities import (
    NotificationReceipt,
    ReporterNotification,
    TeamNotification,
)


class INotifyProvider(ABC):
    name: str

    @abstractmethod
    async def notify_team(self, msg: TeamNotification) -> NotificationReceipt: ...

    @abstractmethod
    async def notify_reporter(
        self, msg: ReporterNotification
    ) -> NotificationReceipt: ...
