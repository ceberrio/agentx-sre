"""Local state for the Triage subgraph (ReAct loop)."""
from __future__ import annotations

from typing import Optional

from app.domain.entities import TriageResult
from app.orchestration.orchestrator.state import AgentEvent, TriageProjection
from app.orchestration.shared.agent_state import AgentLocalState


class TriageState(AgentLocalState, total=False):
    projection: TriageProjection
    retrieved_context: list[dict]
    triage_result: Optional[TriageResult]
    final_event: AgentEvent
