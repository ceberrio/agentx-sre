"""Integration Agent — creates the ticket and notifies the on-call team.

Deterministic two-step sequence (ticket -> notify). Implemented as a subgraph
for uniformity and consistent observability across agents.

Emits internal events (ticket_created, team_notified) and returns the LAST
one as final_event. The full sequence is in payload["events"] for audit.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.domain.entities import TicketDraft, TeamNotification
from app.infrastructure.container import Container
from app.observability import tracing
from app.orchestration.agents.integration.state import IntegrationState
from app.orchestration.orchestrator.state import AgentEvent
from app.orchestration.shared.base_agent import BaseAgent

log = logging.getLogger(__name__)


class IntegrationAgent(BaseAgent):
    name = "integration"

    def build(self):
        g = StateGraph(IntegrationState)
        g.add_node("create_ticket", self._create_ticket)
        g.add_node("notify_team", self._notify_team)
        g.add_node("emit", self._emit)

        g.set_entry_point("create_ticket")
        g.add_edge("create_ticket", "notify_team")
        g.add_edge("notify_team", "emit")
        g.add_edge("emit", END)
        return g.compile()

    # ----- nodes -----

    async def _create_ticket(self, state: IntegrationState) -> IntegrationState:
        """Call ITicketProvider.create_ticket via container."""
        proj = state["projection"]
        incident = proj.incident
        triage = proj.triage

        draft = TicketDraft(
            incident_id=incident.id,
            title=f"[{triage.severity.value}] {incident.title}",
            description=(
                f"**Reporter:** {incident.reporter_email}\n\n"
                f"**Incident description:**\n{incident.description}\n\n"
                f"**Severity:** {triage.severity.value}\n"
                f"**Summary:** {triage.summary}\n"
                f"**Root cause:** {triage.suspected_root_cause}\n"
                f"**Suggested owners:** {', '.join(triage.suggested_owners)}\n"
                f"**Confidence:** {triage.confidence:.0%}\n"
                f"**Needs human review:** {triage.needs_human_review}"
            ),
            severity=triage.severity,
            labels=["sre-agent", "auto-triaged"] + (["human-review"] if triage.needs_human_review else []),
        )

        with tracing.span_ticket_create(
            incident_id=incident.id,
            ticket_id="pending",
            ticket_provider=self.container.ticket.name,
            severity=triage.severity.value,
        ):
            ticket = await self.container.ticket.create_ticket(draft)

        log.info(
            "ticket.created",
            extra={
                "incident_id": incident.id,
                "ticket_id": ticket.id,
                "provider": ticket.provider,
            },
        )

        state["ticket"] = ticket

        ticket_event = AgentEvent(
            kind="integration.ticket_created",
            agent=self.name,
            payload={"ticket_id": ticket.id, "ticket_url": ticket.url},
        )
        sub_events = list(state.get("sub_events") or [])
        sub_events.append(ticket_event)
        state["sub_events"] = sub_events

        return state

    async def _notify_team(self, state: IntegrationState) -> IntegrationState:
        """Call INotifyProvider.notify_team via container."""
        proj = state["projection"]
        incident = proj.incident
        triage = proj.triage
        ticket = state.get("ticket")

        if ticket is None:
            log.error(
                "integration.notify_team.no_ticket",
                extra={"incident_id": incident.id},
            )
            sub_events = list(state.get("sub_events") or [])
            state["sub_events"] = sub_events
            state["notified"] = False
            return state

        msg = TeamNotification(
            incident_id=incident.id,
            ticket_id=ticket.id,
            title=f"[{triage.severity.value}] {incident.title}",
            summary=triage.summary,
            severity=triage.severity.value,
            recipients=triage.suggested_owners or ["sre-oncall"],
        )

        with tracing.span_notify_team(
            incident_id=incident.id,
            ticket_id=ticket.id,
            notify_provider=self.container.notify.name,
            recipients_count=len(msg.recipients),
        ):
            receipt = await self.container.notify.notify_team(msg)

        state["notified"] = receipt.delivered
        log.info(
            "notify.team.sent",
            extra={
                "incident_id": incident.id,
                "ticket_id": ticket.id,
                "delivered": receipt.delivered,
            },
        )

        notify_event = AgentEvent(
            kind="integration.team_notified",
            agent=self.name,
            payload={
                "ticket_id": ticket.id,
                "recipients": msg.recipients,
                "delivered": receipt.delivered,
            },
        )
        sub_events = list(state.get("sub_events") or [])
        sub_events.append(notify_event)
        state["sub_events"] = sub_events
        return state

    async def _emit(self, state: IntegrationState) -> IntegrationState:
        """Set final_event = last sub_event with payload[events] = full trail."""
        sub_events = list(state.get("sub_events") or [])
        ticket = state.get("ticket")

        if not sub_events:
            state["final_event"] = self.emit(
                "agent.error",
                error="integration_produced_no_events",
            )
            return state

        last_event = sub_events[-1]
        # Build final event carrying the full audit trail + ticket for CaseState
        final_payload = dict(last_event.payload)
        final_payload["events"] = sub_events
        if ticket is not None:
            final_payload["ticket"] = ticket

        state["final_event"] = AgentEvent(
            kind=last_event.kind,
            agent=self.name,
            payload=final_payload,
            ts=last_event.ts,
        )
        return state


def build_integration_agent(container: Container):
    return IntegrationAgent(container).build()
