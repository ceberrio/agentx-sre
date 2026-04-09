"""OpenRouter adapter — fallback LLM provider (OpenAI-compatible API).

Used when the primary Gemini provider is unavailable (circuit breaker open).
Model: google/gemini-2.0-flash-exp:free (or configurable via OPENROUTER_MODEL).
"""
from __future__ import annotations

import json
import logging

from app.domain.entities import InjectionVerdict, Severity, TriagePrompt, TriageResult
from app.domain.ports import ILLMProvider
from app.llm.prompt_registry import PROMPT_REGISTRY

log = logging.getLogger(__name__)


class OpenRouterLLMAdapter(ILLMProvider):
    name = "openrouter"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key, base_url="https://openrouter.ai/api/v1"
        )

    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        """Run structured triage via OpenRouter (OpenAI-compatible)."""
        template = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        log_section = f"Log excerpt:\n{prompt.log_excerpt}" if prompt.log_excerpt else ""
        image_section = "[Image provided — text-only analysis mode (OpenRouter)]" if prompt.image_bytes else ""
        context_text = "\n\n".join(
            f"[{doc.title}]\n{doc.content}" for doc in prompt.context_docs
        ) if prompt.context_docs else "No context retrieved."

        rendered = template.render(
            incident_title=prompt.title,
            incident_description=prompt.description,
            log_section=log_section,
            image_section=image_section,
            context_docs=context_text,
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": rendered}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)

            tokens_in = response.usage.prompt_tokens if response.usage else 0
            tokens_out = response.usage.completion_tokens if response.usage else 0

            severity_map = {"P1": Severity.P1, "P2": Severity.P2, "P3": Severity.P3, "P4": Severity.P4}
            severity = severity_map.get(data.get("severity", "P3"), Severity.P3)

            return TriageResult(
                severity=severity,
                summary=data.get("summary", ""),
                suspected_root_cause=data.get("suspected_root_cause", ""),
                suggested_owners=data.get("suggested_owners", []),
                needs_human_review=data.get("needs_human_review", False),
                confidence=float(data.get("confidence", 0.6)),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                model=self._model,
                used_fallback=True,
                degraded=False,
                # OpenRouter free-tier: cost is 0 (provider populates cost_usd per ARC-002)
                cost_usd=0.0,
            )
        except Exception as exc:
            log.error(
                "openrouter.triage_failed",
                extra={"incident_id": prompt.incident_id, "error": str(exc)},
            )
            raise

    async def classify_injection(self, text: str) -> InjectionVerdict:
        """Layer-3 guardrail via OpenRouter."""
        template = PROMPT_REGISTRY.get("intake-guard", "1.0.0")
        rendered = template.render(incident_text=text[:4000])

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": rendered}],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            raw = response.choices[0].message.content or "{}"
            data = json.loads(raw)
            verdict_raw = data.get("verdict", "uncertain")
            if verdict_raw in ("injection", "pii", "off_topic"):
                verdict = "yes"
            elif verdict_raw == "safe":
                verdict = "no"
            else:
                verdict = "uncertain"
            return InjectionVerdict(
                verdict=verdict,  # type: ignore[arg-type]
                score=float(data.get("score", 0.5)),
                reason=data.get("reason"),
            )
        except Exception as exc:
            log.error("openrouter.classify_injection_failed", extra={"error": str(exc)})
            return InjectionVerdict(verdict="uncertain", score=0.5, reason="llm_error")

    async def generate(self, prompt: str) -> str:
        """Generate free-form text from a rendered prompt string."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """OpenRouter does not expose embeddings.

        This should never be called — the container wires embeddings through
        GeminiLLMAdapter even when OpenRouter is the primary LLM.
        """
        raise NotImplementedError(
            "OpenRouterLLMAdapter.embed: use GeminiLLMAdapter for embeddings. "
            "Wire the FAISS adapter against the Gemini instance, not the circuit breaker."
        )
