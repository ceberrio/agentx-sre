"""Context document — the unit returned by IContextProvider."""
from __future__ import annotations

from pydantic import BaseModel


class ContextDoc(BaseModel):
    """A retrieved snippet of code/docs from the eShop reference repo."""

    source: str  # file path or doc id
    title: str
    content: str
    score: float = 0.0
