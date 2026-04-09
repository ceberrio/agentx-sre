"""Orchestrator graph — wires the multi-agent topology.

This module declares the TOP-LEVEL LangGraph that the API hits. It composes
each agent as a compiled SUBGRAPH (DEC-005). The orchestrator is the only
component that knows how to assemble agents into a flow.

Two graphs are exposed:

  build_orchestrator_graph(container)
      Synchronous pipeline: intake_guard → triage → integration → END
      Used by POST /incidents.

  build_resolution_graph(container)
      Asynchronous one-shot: resolution
      Used by the resolution webhook (DEC-006). Kept as a separate compiled
      graph so the sync pipeline never blocks waiting for human action.

Hexagonal note (ARC-012):
    This file imports Container — fine, it's the wiring layer.
    It does NOT import any concrete adapter directly.
"""
from __future__ import annotations

import logging
from functools import partial

from langgraph.graph import END, StateGraph

from app.infrastructure.container import Container

try:
    from langgraph.graph.graph import CompiledGraph
except ImportError:
    from typing import Any as CompiledGraph  # type: ignore[assignment]
from app.observability import tracing
from app.observability.metrics import escalations_by_reason_total, incidents_escalated_total
from app.orchestration.agents.integration.agent import build_integration_agent
from app.orchestration.agents.intake_guard.agent import build_intake_guard_agent
from app.orchestration.agents.resolution.agent import build_resolution_agent
from app.orchestration.agents.triage.agent import build_triage_agent
from app.orchestration.orchestrator.router import (
    ROUTE_END,
    ROUTE_INTEGRATION,
    ROUTE_TRIAGE,
    EscalationDecision,
    route_after_integration,
    route_after_intake,
    route_after_triage,
    should_escalate,
)
from app.orchestration.orchestrator.state import (
    AgentEvent,
    CaseState,
    CaseStatus,
    IntakeProjection,
    IntegrationProjection,
    ResolutionProjection,
    TriageProjection,
)

log = logging.getLogger(__name__)


def build_orchestrator_graph(container: Container) -> CompiledGraph:
    """Compile the synchronous multi-agent graph.

    The orchestrator owns CaseState (ARC-013). Each `partial`-bound node:
      1. Builds a read-only projection from CaseState
      2. Invokes the agent subgraph
      3. Receives an AgentEvent
      4. Applies the event to CaseState (this is the ONLY mutation point)

    Returns a compiled LangGraph runnable accepting/returning CaseState.
    """
    g = StateGraph(CaseState)

    # Each agent is itself a compiled subgraph (LangGraph supports nesting).
    intake = build_intake_guard_agent(container)
    triage = build_triage_agent(container)
    integration = build_integration_agent(container)

    g.add_node("intake_guard", partial(_run_intake, subgraph=intake))
    g.add_node("triage_agent", partial(_run_triage, subgraph=triage))
    g.add_node("integration", partial(_run_integration, subgraph=integration))

    g.set_entry_point("intake_guard")
    g.add_conditional_edges(
        "intake_guard",
        route_after_intake,
        {ROUTE_TRIAGE: "triage_agent", ROUTE_END: END},
    )
    g.add_conditional_edges(
        "triage_agent",
        route_after_triage,
        {ROUTE_INTEGRATION: "integration", ROUTE_END: END},
    )
    g.add_conditional_edges(
        "integration",
        route_after_integration,
        {ROUTE_END: END},
    )

    return g.compile()


def build_resolution_graph(container: Container) -> CompiledGraph:
    """Compile the async resolution one-shot graph (DEC-006).

    Triggered by a webhook (ticket-system → /webhooks/resolution).
    Single node: the Resolution Agent. Kept as its own compiled graph so it
    can be invoked independently of the synchronous pipeline.
    """
    g = StateGraph(CaseState)
    resolution = build_resolution_agent(container)

    g.add_node("resolution", partial(_run_resolution, subgraph=resolution))
    g.set_entry_point("resolution")
    g.add_edge("resolution", END)

    return g.compile()


# ---------------------------------------------------------------------------
# Subgraph adapters — orchestrator-owned mutation points (ARC-012).
# Each function is the ONLY place CaseState gets mutated for its node.
# ---------------------------------------------------------------------------


async def _run_intake(state: CaseState, subgraph) -> CaseState:
    """Build IntakeProjection → run subgraph → fold AgentEvent into CaseState."""
    proj = IntakeProjection(
        case_id=state["case_id"],
        incident=state["incident"],
    )
    try:
        result = await subgraph.ainvoke({"projection": proj})
        event: AgentEvent = result["final_event"]
    except Exception as exc:  # noqa: BLE001
        log.error(
            "orchestrator._run_intake.failed",
            extra={"case_id": state["case_id"], "error": str(exc)},
        )
        event = AgentEvent(
            kind="agent.error",
            agent="intake_guard",
            error=str(exc),
        )

    if event.kind == "intake.blocked":
        state["status"] = CaseStatus.INTAKE_BLOCKED
        state["blocked_reason"] = event.payload.get("reason", "blocked_by_guardrails")
    elif event.kind == "agent.error":
        state["status"] = CaseStatus.FAILED
        state["error"] = event.error
    else:
        state["status"] = CaseStatus.INTAKE_OK

    events = list(state.get("events", []))
    events.append(event)
    state["events"] = events
    return state


async def _run_triage(state: CaseState, subgraph) -> CaseState:
    """Build TriageProjection → run subgraph → fold AgentEvent into CaseState."""
    proj = TriageProjection(
        case_id=state["case_id"],
        incident=state["incident"],
    )
    try:
        result = await subgraph.ainvoke({"projection": proj})
        event: AgentEvent = result["final_event"]
    except Exception as exc:  # noqa: BLE001
        log.error(
            "orchestrator._run_triage.failed",
            extra={"case_id": state["case_id"], "error": str(exc)},
        )
        event = AgentEvent(
            kind="agent.error",
            agent="triage",
            error=str(exc),
        )

    if event.kind == "triage.completed":
        triage_result = event.payload.get("triage")
        state["triage"] = triage_result
        state["status"] = CaseStatus.TRIAGED
        # Mirror severity onto the incident object for convenience
        if triage_result is not None:
            state["incident"] = state["incident"].model_copy(
                update={"severity": triage_result.severity}
            )
        # Escalation check — reads governance from state (pure, no I/O — ARC-014)
        escalation = should_escalate(state)
        if escalation.escalate:
            state["status"] = CaseStatus.ESCALATED
            state["blocked_reason"] = f"escalated_by_governance:{escalation.trigger}"
            incidents_escalated_total.labels(agent_name="triage").inc()
            escalations_by_reason_total.labels(reason=escalation.trigger or "unknown").inc()
            log.info(
                "orchestrator.escalation_triggered",
                extra={
                    "case_id": state["case_id"],
                    "trigger": escalation.trigger,
                    "confidence": triage_result.confidence if triage_result else None,
                },
            )
    elif event.kind == "agent.error":
        state["status"] = CaseStatus.FAILED
        state["error"] = event.error

    events = list(state.get("events", []))
    events.append(event)
    state["events"] = events
    return state


async def _run_integration(state: CaseState, subgraph) -> CaseState:
    """Build IntegrationProjection → run subgraph → fold AgentEvent into CaseState.

    The Integration Agent emits two internal events (ticket_created, team_notified)
    and returns the FINAL event. The full sub-sequence is in event.payload["events"].
    """
    triage_result = state.get("triage")
    if triage_result is None:
        log.error("orchestrator._run_integration.no_triage", extra={"case_id": state["case_id"]})
        state["status"] = CaseStatus.FAILED
        state["error"] = "triage_result_missing"
        return state

    proj = IntegrationProjection(
        case_id=state["case_id"],
        incident=state["incident"],
        triage=triage_result,
    )
    try:
        result = await subgraph.ainvoke({"projection": proj, "sub_events": []})
        event: AgentEvent = result["final_event"]
    except Exception as exc:  # noqa: BLE001
        log.error(
            "orchestrator._run_integration.failed",
            extra={"case_id": state["case_id"], "error": str(exc)},
        )
        event = AgentEvent(
            kind="agent.error",
            agent="integration",
            error=str(exc),
        )

    if event.kind == "agent.error":
        state["status"] = CaseStatus.FAILED
        state["error"] = event.error
    else:
        # The final event from integration is "integration.team_notified"
        # Ticket is in the payload
        ticket = event.payload.get("ticket")
        if ticket is not None:
            state["ticket"] = ticket
        state["status"] = CaseStatus.NOTIFIED

    # Append the full audit sub-trail plus the final event
    sub_events: list[AgentEvent] = event.payload.get("events", [])
    events = list(state.get("events", []))
    events.extend(sub_events)
    if event not in sub_events:
        events.append(event)
    state["events"] = events
    return state


async def _run_resolution(state: CaseState, subgraph) -> CaseState:
    """Build ResolutionProjection → run subgraph → fold AgentEvent into CaseState."""
    ticket = state.get("ticket")
    if ticket is None:
        log.error("orchestrator._run_resolution.no_ticket", extra={"case_id": state["case_id"]})
        state["status"] = CaseStatus.FAILED
        state["error"] = "ticket_missing_for_resolution"
        return state

    proj = ResolutionProjection(
        case_id=state["case_id"],
        incident=state["incident"],
        ticket=ticket,
    )
    try:
        with tracing.span_resolution_run(
            incident_id=state["case_id"],
            ticket_id=ticket.id,
        ):
            result = await subgraph.ainvoke({"projection": proj})
            event: AgentEvent = result["final_event"]
    except Exception as exc:  # noqa: BLE001
        log.error(
            "orchestrator._run_resolution.failed",
            extra={"case_id": state["case_id"], "error": str(exc)},
        )
        event = AgentEvent(
            kind="agent.error",
            agent="resolution",
            error=str(exc),
        )

    if event.kind == "resolution.completed":
        state["status"] = CaseStatus.RESOLVED
    elif event.kind == "agent.error":
        state["status"] = CaseStatus.FAILED
        state["error"] = event.error

    events = list(state.get("events", []))
    events.append(event)
    state["events"] = events
    return state
