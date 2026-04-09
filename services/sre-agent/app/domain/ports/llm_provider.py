"""ILLMProvider — the only way the domain talks to a Large Language Model."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities import (
    InjectionVerdict,
    TriagePrompt,
    TriageResult,
)


class ILLMProvider(ABC):
    """Implementations live in app/adapters/llm/."""

    name: str

    @abstractmethod
    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        """Run the structured triage call. MUST return a TriageResult."""

    @abstractmethod
    async def classify_injection(self, text: str) -> InjectionVerdict:
        """Layer-3 guardrail: cheap classification of suspected prompt injection."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts. Used by the FAISS context adapter at index time and query time."""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Generate free-form text from a rendered prompt string."""
        ...

    def capabilities(self) -> frozenset[str]:
        """Return the set of capabilities this adapter supports.
        Default: all four. Override in adapters that intentionally omit one.
        Mandatory capabilities: triage, classify_injection, generate.
        Optional: embed (not all providers offer an embeddings API).
        """
        return frozenset({"triage", "classify_injection", "embed", "generate"})
