"""Tools for the Resolution Agent.

The Resolution Agent is a deterministic two-step subgraph (summarize →
notify_reporter → emit) rather than a ReAct loop. It does not require
LangGraph tool bindings — side effects are called directly through ports
inside the agent nodes.

This module is kept as a placeholder for future extensions (e.g. a
feedback-loop tool that stores resolution quality signals).
"""
from __future__ import annotations

from app.orchestration.shared.tool_factory import ToolFactory


def build_resolution_tools(factory: ToolFactory) -> list:
    """Return tool list for the Resolution Agent (currently empty).

    The resolution flow is deterministic; tools are reserved for future use.
    """
    return []
