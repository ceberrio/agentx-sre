"""EmailNotifyAdapter — production. Stub: @developer plugs SMTP / SES / SendGrid."""
from __future__ import annotations

from app.domain.entities import (
    NotificationReceipt,
    ReporterNotification,
    TeamNotification,
)
from app.domain.ports import INotifyProvider


class EmailNotifyAdapter(INotifyProvider):
    name = "email"

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password

    async def notify_team(self, msg: TeamNotification) -> NotificationReceipt:
        raise NotImplementedError("@developer: implement SMTP send to team distribution list")

    async def notify_reporter(self, msg: ReporterNotification) -> NotificationReceipt:
        raise NotImplementedError("@developer: implement SMTP send to reporter")
