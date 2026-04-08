"""Resolution Agent — async, webhook-triggered (DEC-006).

Flow:
    1. External ticket system marks a ticket as resolved.
    2. It POSTs to /webhooks/resolution on this service.
    3. The webhook handler builds a ResolutionProjection and invokes
       `build_resolution_graph(container)` (NOT the orchestrator graph).
    4. This agent summarizes the resolution and notifies the original reporter.

Why a separate graph (DEC-006):
    The synchronous incident graph must NEVER block waiting on a human/ticket
    system. Resolution is decoupled into its own compiled graph so the API
    response time is bounded by triage+integration alone.

Emits exactly ONE AgentEvent:
    - "resolution.completed"  (status -> RESOLVED)
    - "agent.error"           on failure
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.domain.entities import ReporterNotification
from app.infrastructure.container import Container
from app.llm.prompt_registry import PROMPT_REGISTRY
from app.observability import tracing
from app.observability.metrics import incidents_total
from app.orchestration.agents.resolution.state import ResolutionState
from app.orchestration.shared.base_agent import BaseAgent

log = logging.getLogger(__name__)


class ResolutionAgent(BaseAgent):
    name = "resolution"

    def build(self):
        g = StateGraph(ResolutionState)
        g.add_node("summarize", self._summarize)
        g.add_node("notify_reporter", self._notify_reporter)
        g.add_node("emit", self._emit)

        g.set_entry_point("summarize")
        g.add_edge("summarize", "notify_reporter")
        g.add_edge("notify_reporter", "emit")
        g.add_edge("emit", END)
        return g.compile()

    # ----- nodes -----

    async def _summarize(self, state: ResolutionState) -> ResolutionState:
        """LLM step: build a short, user-friendly resolution summary.

        Uses the LLM port (ARC-012) — no direct SDK imports allowed in agents.
        Falls back to a template string on LLM failure (fail-open for reporter UX).
        """
        proj = state["projection"]
        incident = proj.incident
        ticket = proj.ticket

        _fallback_summary = (
            f"Your incident '{incident.title}' has been resolved. "
            f"Ticket {ticket.id} has been closed. "
            f"Thank you for reporting — our SRE team has addressed the issue."
        )

        try:
            template = PROMPT_REGISTRY.get("resolution-summary", "1.0.0")
            rendered = template.render(
                incident_title=incident.title,
                incident_description=incident.description[:500],
                ticket_id=ticket.id,
                ticket_url=ticket.url or "N/A",
                severity="N/A",  # not carried in projection for resolution
                root_cause="See ticket for details.",
                owners="SRE team",
            )

            with tracing.span_resolution_summarize(
                incident_id=incident.id,
                llm_prompt_name="resolution-summary",
                llm_prompt_version="1.0.0",
            ):
                summary = await self.container.llm.generate(rendered)
            if not summary:
                summary = _fallback_summary

            state["summary"] = summary
            log.info("resolution.summary_generated", extra={"incident_id": incident.id})
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "resolution.summarize_failed",
                extra={"incident_id": incident.id, "error": str(exc)},
            )
            state["summary"] = _fallback_summary

        return state

    async def _notify_reporter(self, state: ResolutionState) -> ResolutionState:
        """Send the resolution summary to the original reporter."""
        proj = state["projection"]
        incident = proj.incident
        ticket = proj.ticket
        summary = state.get("summary", "Your incident has been resolved.")

        msg = ReporterNotification(
            incident_id=incident.id,
            ticket_id=ticket.id,
            reporter_email=incident.reporter_email,
            subject=f"Resolved: {incident.title} [{ticket.id}]",
            body=summary,
        )

        with tracing.span_resolve_notify(
            incident_id=incident.id,
            ticket_id=ticket.id,
            reporter_email=incident.reporter_email,
        ):
            try:
                receipt = await self.container.notify.notify_reporter(msg)
                log.info(
                    "notify.email.sent",
                    extra={
                        "incident_id": incident.id,
                        "reporter": incident.reporter_email,
                        "delivered": receipt.delivered,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "resolution.notify_reporter_failed",
                    extra={"incident_id": incident.id, "error": str(exc)},
                )
                state["notify_error"] = str(exc)

        return state

    async def _emit(self, state: ResolutionState) -> ResolutionState:
        """Build and store the final AgentEvent and emit observability signals.

        If _notify_reporter recorded a notify_error the notification did not
        reach the reporter, so the incident MUST NOT be marked RESOLVED.
        """
        proj = state["projection"]
        notify_error = state.get("notify_error")

        if notify_error:
            state["final_event"] = self.emit(
                "agent.error",
                payload={
                    "incident_id": proj.incident.id,
                    "ticket_id": proj.ticket.id,
                    "error": notify_error,
                },
            )
            incidents_total.labels(status="failed").inc()
            log.error(
                "resolution.emit.notify_failed",
                extra={"incident_id": proj.incident.id, "error": notify_error},
            )
        else:
            state["final_event"] = self.emit(
                "resolution.completed",
                payload={
                    "summary": state.get("summary", ""),
                    "incident_id": proj.incident.id,
                    "ticket_id": proj.ticket.id,
                },
            )
            incidents_total.labels(status="resolved").inc()
            log.info(
                "resolution.summarize.completed",
                extra={"incident_id": proj.incident.id},
            )
        return state


def build_resolution_agent(container: Container):
    return ResolutionAgent(container).build()
