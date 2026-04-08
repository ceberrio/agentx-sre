"""Local state for the IntakeGuard subgraph."""
from __future__ import annotations

from typing import Optional

from app.orchestration.orchestrator.state import AgentEvent, IntakeProjection
from app.orchestration.shared.agent_state import AgentLocalState


class IntakeGuardState(AgentLocalState, total=False):
    projection: IntakeProjection
    blocked: bool
    blocked_reason: Optional[str]
    injection_score: float          # Layer-4 LLM judge confidence score
    needs_human_review: bool        # True when verdict is "uncertain"
    final_event: AgentEvent
