"""Router — pure functions that decide the next step from CaseState.

CONTRACT (ARC-014):
- These functions MUST be pure: no I/O, no LLM calls, no adapter access.
- They take CaseState (or a slice of it) and return a string label that
  LangGraph maps to the next node.
- Escalation policy lives here. To change routing behavior, edit this file
  and only this file.
"""
from __future__ import annotations

from app.orchestration.orchestrator.state import CaseState, CaseStatus

# Sentinel labels — keep in sync with edges declared in graph.py
ROUTE_INTAKE = "intake_guard"
ROUTE_TRIAGE = "triage_agent"
ROUTE_INTEGRATION = "integration"
ROUTE_END = "__end__"


def route_after_intake(state: CaseState) -> str:
    """After IntakeGuard: continue to triage or terminate the case."""
    status = state.get("status")
    if status == CaseStatus.INTAKE_BLOCKED:
        return ROUTE_END
    # Both INTAKE_OK and any error fall through — if error the triage agent
    # will handle it and produce an agent.error event.
    return ROUTE_TRIAGE


def route_after_triage(state: CaseState) -> str:
    """After Triage: always proceed to Integration unless triage failed."""
    if state.get("error"):
        return ROUTE_END
    status = state.get("status")
    if status == CaseStatus.FAILED:
        return ROUTE_END
    return ROUTE_INTEGRATION


def route_after_integration(state: CaseState) -> str:
    """After Integration: terminate the synchronous graph.

    Resolution is handled by a separate async subgraph (DEC-006), triggered
    by an external webhook — never inline.
    """
    return ROUTE_END


def should_escalate(state: CaseState) -> bool:
    """Escalation policy hook.

    For the hackathon scope this is always False. Kept as a named extension
    point so we can plug a real policy (severity, repeated failures, low
    LLM confidence) without touching the graph topology.
    """
    return False
