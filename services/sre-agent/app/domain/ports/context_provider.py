"""IContextProvider — abstracts static excerpts / FAISS / future vector DBs."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities import ContextDoc


class IContextProvider(ABC):
    name: str

    @abstractmethod
    async def search_context(self, query: str, k: int = 5) -> list[ContextDoc]: ...
