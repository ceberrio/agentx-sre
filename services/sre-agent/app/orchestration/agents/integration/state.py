"""Local state for the Integration subgraph."""
from __future__ import annotations

from typing import Optional

from app.domain.entities import Ticket
from app.orchestration.orchestrator.state import AgentEvent, IntegrationProjection
from app.orchestration.shared.agent_state import AgentLocalState


class IntegrationState(AgentLocalState, total=False):
    projection: IntegrationProjection
    ticket: Optional[Ticket]
    notified: bool
    sub_events: list[AgentEvent]   # internal trail (ticket_created, team_notified)
    final_event: AgentEvent        # the LAST event, returned to the orchestrator
