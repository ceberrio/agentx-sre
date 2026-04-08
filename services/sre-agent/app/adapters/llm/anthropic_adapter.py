"""Anthropic adapter — alternative LLM provider."""
from __future__ import annotations

from app.domain.entities import InjectionVerdict, TriagePrompt, TriageResult
from app.domain.ports import ILLMProvider


class AnthropicLLMAdapter(ILLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-latest") -> None:
        self._api_key = api_key
        self._model = model
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)

    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        raise NotImplementedError("@developer: implement Anthropic triage")

    async def classify_injection(self, text: str) -> InjectionVerdict:
        raise NotImplementedError("@developer: implement Anthropic guardrail")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError(
            "Anthropic does not provide embeddings — use Gemini for embeddings"
        )

    async def generate(self, prompt: str) -> str:
        raise NotImplementedError("@developer: implement Anthropic generate")
