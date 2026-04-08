"""Tool list exposed to the Triage Agent's nodes during ReAct.

Backed by ToolFactory so we don't leak adapter classes into agent code.
"""
from __future__ import annotations

from typing import Any, Callable

from app.orchestration.shared.tool_factory import ToolFactory


def build_triage_tools(factory: ToolFactory) -> dict[str, Callable[..., Any]]:
    """Return the tools the Triage Agent may call keyed by tool name.

    Currently: semantic context search via IContextProvider.
    """
    return {
        "search_context": factory.make_search_context_tool(),
    }
