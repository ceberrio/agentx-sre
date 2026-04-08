"""AgentLocalState — the per-agent scratchpad inside a subgraph.

This is intentionally separate from CaseState (ARC-013):
  - CaseState lives in the orchestrator and is the source of truth.
  - AgentLocalState lives INSIDE one subgraph invocation and dies with it.

An agent reads its Projection (immutable), thinks/loops/calls tools using
its AgentLocalState, and finally emits ONE AgentEvent which the orchestrator
folds back into CaseState.
"""
from __future__ import annotations

from typing import Any, TypedDict


class AgentLocalState(TypedDict, total=False):
    """Generic ReAct-style scratchpad for an agent subgraph.

    Specific agents may subclass this TypedDict (or define their own next to
    their agent.py) when they need richer fields.
    """

    projection: Any           # the immutable input handed by the orchestrator
    scratchpad: list[dict]    # ReAct trace: [{thought, action, observation}, ...]
    tool_calls: int           # safety: cap iterations to avoid runaway loops
    final_event: Any          # AgentEvent to return upstream
