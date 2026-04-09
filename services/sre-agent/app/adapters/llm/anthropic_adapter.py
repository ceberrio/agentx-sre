"""Anthropic adapter — alternative LLM provider.

Implements ILLMProvider via the anthropic SDK.
Uses structured JSON output for triage to enforce the TriageResult schema.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

try:
    from anthropic import AsyncAnthropic
except ImportError as exc:
    raise ImportError(
        "anthropic package is required for AnthropicLLMAdapter. "
        "Install it with: pip install anthropic"
    ) from exc

from app.domain.entities import (
    InjectionVerdict,
    Severity,
    TriagePrompt,
    TriageResult,
)
from app.domain.ports import ILLMProvider
from app.llm.prompt_registry import PROMPT_REGISTRY

log = logging.getLogger(__name__)

# --- Module-level constants (FINDING-03) ---
_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_TRIAGE_MAX_TOKENS = 1024
_CLASSIFY_MAX_TOKENS = 256
_GENERATE_MAX_TOKENS = 1024
_CLASSIFY_INPUT_CHAR_LIMIT = 4000


def _strip_markdown_fence(text: str) -> str:
    """Remove markdown code fences that some LLMs inject around JSON responses.

    Handles: ```json ... ``` and ``` ... ``` (case-insensitive, strips closing fence too).
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    after_fence = stripped.split("```", maxsplit=1)[1]
    if after_fence.lower().startswith("json"):
        after_fence = after_fence[4:]
    if "```" in after_fence:
        after_fence = after_fence.rsplit("```", maxsplit=1)[0]
    return after_fence.strip()


class AnthropicLLMAdapter(ILLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        # FINDING-07: api_key is passed directly to the client; no need to retain it.
        self._model = model
        self._client = AsyncAnthropic(api_key=api_key)

    def capabilities(self) -> frozenset[str]:
        """embed is intentionally excluded — Anthropic has no embeddings API."""
        return frozenset({"triage", "classify_injection", "generate"})

    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        """Run structured triage using Claude. Returns TriageResult."""
        template = PROMPT_REGISTRY.get("triage-analysis", "1.0.0")
        log_section = f"Log excerpt:\n{prompt.log_excerpt}" if prompt.log_excerpt else ""
        image_section = "[Image attached — multimodal analysis enabled]" if prompt.image_bytes else ""

        context_text = "\n\n".join(
            f"[{doc.title}]\n{doc.content}" for doc in prompt.context_docs
        ) if prompt.context_docs else "No additional context retrieved."

        rendered = template.render(
            incident_title=prompt.title,
            incident_description=prompt.description,
            log_section=log_section,
            image_section=image_section,
            context_docs=context_text,
        )

        system_prompt = (
            "You are an expert SRE triage assistant. "
            "Always respond with valid JSON matching the requested schema. "
            "Do not include markdown fences or any text outside the JSON object."
        )

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=_TRIAGE_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": rendered}],
            )
            raw = _strip_markdown_fence(response.content[0].text)
            data = json.loads(raw)

            tokens_in = response.usage.input_tokens if response.usage else 0
            tokens_out = response.usage.output_tokens if response.usage else 0

            severity_map = {
                "P1": Severity.P1, "P2": Severity.P2,
                "P3": Severity.P3, "P4": Severity.P4,
            }
            severity_raw = data.get("severity", "P3")
            severity = severity_map.get(severity_raw, Severity.P3)

            return TriageResult(
                severity=severity,
                summary=data.get("summary", ""),
                suspected_root_cause=data.get("suspected_root_cause", ""),
                suggested_owners=data.get("suggested_owners", []),
                needs_human_review=data.get("needs_human_review", False),
                confidence=float(data.get("confidence", 0.7)),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                model=self._model,
                used_fallback=False,
                degraded=False,
            )
        except Exception as exc:
            log.error(
                "anthropic.triage_failed",
                extra={"incident_id": prompt.incident_id, "error": str(exc)},
            )
            raise

    async def classify_injection(self, text: str) -> InjectionVerdict:
        """Layer-3 guardrail: LLM-based injection classification."""
        template = PROMPT_REGISTRY.get("intake-guard", "1.0.0")
        rendered = template.render(incident_text=text[:_CLASSIFY_INPUT_CHAR_LIMIT])

        system_prompt = (
            "You are a security classifier. "
            "Always respond with valid JSON. No markdown, no extra text."
        )

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=_CLASSIFY_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": rendered}],
            )
            raw = _strip_markdown_fence(response.content[0].text)
            data = json.loads(raw)
            verdict_raw = data.get("verdict", "uncertain")

            # FINDING-06: explicit Literal annotation eliminates the type: ignore
            verdict: Literal["yes", "no", "uncertain"]
            if verdict_raw in ("injection", "pii", "off_topic"):
                verdict = "yes"
            elif verdict_raw == "safe":
                verdict = "no"
            else:
                verdict = "uncertain"

            return InjectionVerdict(
                verdict=verdict,
                score=float(data.get("score", 0.5)),
                reason=data.get("reason"),
            )
        except Exception as exc:
            log.error("anthropic.classify_injection_failed", extra={"error": str(exc)})
            return InjectionVerdict(verdict="uncertain", score=0.5, reason="llm_error")

    async def generate(self, prompt: str) -> str:
        """Generate free-form text from a rendered prompt string."""
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=_GENERATE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:
            log.error("anthropic.generate_failed", extra={"error": str(exc)})
            raise

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Anthropic does not provide an embeddings API.

        This adapter should never be wired as primary when the embedding
        pipeline is active. Use GeminiLLMAdapter for embed calls.
        Callers should check capabilities() before calling embed().
        """
        raise NotImplementedError(
            "AnthropicLLMAdapter does not support embed(). "
            "Check capabilities() before routing embed calls to this adapter."
        )
