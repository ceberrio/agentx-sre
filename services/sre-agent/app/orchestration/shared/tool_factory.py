"""ToolFactory — wraps domain ports as callable tools for agent nodes.

Why this exists:
    Agents reason via ReAct and need callable "tools". But our domain layer
    only knows about ports (IStorageProvider, ITicketProvider, ...). This
    factory adapts each port method into an async callable the agent can invoke,
    without leaking adapter details into agent code (ARC-012).

Tools are plain async callables, not LangChain/LangGraph tool objects, to keep
the layer thin and framework-agnostic. Agents call them directly inside _act().
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.infrastructure.container import Container

log = logging.getLogger(__name__)


class ToolFactory:
    """Builds tool callables from the resolved Container."""

    def __init__(self, container: Container) -> None:
        self._container = container

    # ---- Triage tools ---------------------------------------------------

    def make_search_context_tool(self) -> Callable[..., Any]:
        """Tool: semantic search over the eShop knowledge base.

        Returns an async callable: search_context(query: str, k: int = 5)
        -> list[dict] where each dict has keys: source, title, content, score.
        """
        context_port = self._container.context

        async def search_context(query: str, k: int = 5) -> list[dict]:
            docs = await context_port.search_context(query, k=k)
            return [
                {
                    "source": doc.source,
                    "title": doc.title,
                    "content": doc.content,
                    "score": doc.score,
                }
                for doc in docs
            ]

        search_context.__name__ = "search_context"
        return search_context

    # ---- Persistence (used by every agent) -----------------------------

    def make_persist_status_tool(self) -> Callable[..., Any]:
        """Tool: persist incident status updates via IStorageProvider."""
        storage_port = self._container.storage

        async def persist_status(incident_id: str, patch: dict[str, Any]) -> bool:
            try:
                await storage_port.update_incident(incident_id, patch)
                return True
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "tool.persist_status.failed",
                    extra={"incident_id": incident_id, "error": str(exc)},
                )
                return False

        persist_status.__name__ = "persist_status"
        return persist_status
