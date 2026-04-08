"""Local state for the Resolution subgraph (async, webhook-triggered)."""
from __future__ import annotations

from app.orchestration.orchestrator.state import AgentEvent, ResolutionProjection
from app.orchestration.shared.agent_state import AgentLocalState


class ResolutionState(AgentLocalState, total=False):
    projection: ResolutionProjection
    summary: str
    final_event: AgentEvent
