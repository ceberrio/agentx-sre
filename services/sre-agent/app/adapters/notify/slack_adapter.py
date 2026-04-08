"""SlackNotifyAdapter — production. Uses Slack incoming webhook URL."""
from __future__ import annotations

import httpx

from app.domain.entities import (
    NotificationReceipt,
    ReporterNotification,
    TeamNotification,
)
from app.domain.ports import INotifyProvider


class SlackNotifyAdapter(INotifyProvider):
    name = "slack"

    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=10.0)

    async def notify_team(self, msg: TeamNotification) -> NotificationReceipt:
        r = await self._client.post(
            self._webhook_url,
            json={
                "text": f"[{msg.severity}] {msg.title}",
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": f"[{msg.severity}] {msg.title}"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": msg.summary}},
                    {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Ticket: {msg.ticket_id} | Incident: {msg.incident_id}"}]},
                ],
            },
        )
        r.raise_for_status()
        return NotificationReceipt(delivered=True, provider=self.name, channel="team")

    async def notify_reporter(self, msg: ReporterNotification) -> NotificationReceipt:
        # Slack is not appropriate for reporter notifications.
        # Container should pair SlackNotifyAdapter with EmailNotifyAdapter for reporter.
        raise NotImplementedError(
            "SlackNotifyAdapter does not support reporter notifications. "
            "Use a CompositeNotifyAdapter or set NOTIFY_PROVIDER=email for reporters."
        )
