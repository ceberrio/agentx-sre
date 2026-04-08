"""BaseAgent — common contract for every agent subgraph.

Each concrete agent module exposes a `build_<name>_agent(container)` function
that returns a compiled LangGraph. This base class is OPTIONAL — it exists to
keep the four agents structurally similar and to centralize cross-cutting
concerns (max iterations, error handling, event emission).

ARC-012: agents depend ONLY on ports (passed in via Container at build time),
never on concrete adapters.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.infrastructure.container import Container
from app.orchestration.orchestrator.state import AgentEvent


class BaseAgent(ABC):
    """Abstract base every agent subgraph follows.

    Subclasses implement `build()` returning a compiled LangGraph runnable
    whose input is `{"projection": <Projection>}` and whose output contains
    a `final_event: AgentEvent` field.
    """

    name: str = "base"
    max_iterations: int = 6  # ReAct safety cap

    def __init__(self, container: Container) -> None:
        self.container = container

    @abstractmethod
    def build(self) -> Any:
        """Return a compiled LangGraph subgraph."""
        raise NotImplementedError

    # ----- helpers shared across agents -----

    def emit(self, kind: str, payload: dict | None = None, error: str | None = None) -> AgentEvent:
        """Build an AgentEvent tagged with this agent's name."""
        return AgentEvent(
            kind=kind,  # type: ignore[arg-type]
            agent=self.name,
            payload=payload or {},
            error=error,
        )
