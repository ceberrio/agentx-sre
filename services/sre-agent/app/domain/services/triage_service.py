"""TriageService — pure use case. Wires ports together with zero framework knowledge.

This is the canonical example of the hexagonal pattern in this codebase:
nothing in this file imports FastAPI, LangGraph, httpx, SQLAlchemy, or any LLM SDK.
"""
from __future__ import annotations

from app.domain.entities import (
    Incident,
    TriagePrompt,
    TriageResult,
)
from app.domain.ports import IContextProvider, ILLMProvider


class TriageService:
    """Build a TriagePrompt from an Incident + retrieved context, call the LLM."""

    def __init__(self, llm: ILLMProvider, context: IContextProvider) -> None:
        self._llm = llm
        self._context = context

    async def run(self, incident: Incident) -> TriageResult:
        query = f"{incident.title}\n{incident.description}"
        docs = await self._context.search_context(query, k=5)
        prompt = TriagePrompt(
            incident_id=incident.id,
            title=incident.title,
            description=incident.description,
            log_excerpt=incident.log_text,
            image_bytes=incident.image_bytes,
            image_mime="image/png" if incident.has_image else None,
            context_docs=docs,
        )
        return await self._llm.triage(prompt)
