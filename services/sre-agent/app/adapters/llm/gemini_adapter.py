"""Gemini adapter — primary LLM provider.

Implements ILLMProvider via the google-generativeai SDK.
Uses structured JSON output for triage to enforce the TriageResult schema.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.domain.entities import (
    InjectionVerdict,
    Severity,
    TriagePrompt,
    TriageResult,
)
from app.domain.ports import ILLMProvider
from app.llm.prompt_registry import PROMPT_REGISTRY

log = logging.getLogger(__name__)

# Approximate pricing for gemini-2.0-flash (per 1M tokens, in USD)
_COST_PER_INPUT_TOKEN = 0.075 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 0.30 / 1_000_000


class GeminiLLMAdapter(ILLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._api_key = api_key
        self._model_name = model
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(model)
        self._genai = genai

    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        """Run structured triage using Gemini. Returns TriageResult."""
        import asyncio

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

        # Build content parts (text + optional image)
        parts: list[Any] = [rendered]
        if prompt.image_bytes and prompt.image_mime:
            parts.insert(0, {
                "mime_type": prompt.image_mime,
                "data": prompt.image_bytes,
            })

        try:
            response = await asyncio.to_thread(
                self._client.generate_content,
                parts,
                generation_config={"response_mime_type": "application/json"},
            )
            raw = response.text.strip()
            data = json.loads(raw)

            tokens_in = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            tokens_out = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            severity_map = {"P1": Severity.P1, "P2": Severity.P2, "P3": Severity.P3, "P4": Severity.P4}
            severity_raw = data.get("severity", "P3")
            severity = severity_map.get(severity_raw, Severity.P3)

            cost_usd = (
                tokens_in * _COST_PER_INPUT_TOKEN
                + tokens_out * _COST_PER_OUTPUT_TOKEN
            )
            return TriageResult(
                severity=severity,
                summary=data.get("summary", ""),
                suspected_root_cause=data.get("suspected_root_cause", ""),
                suggested_owners=data.get("suggested_owners", []),
                needs_human_review=data.get("needs_human_review", False),
                confidence=float(data.get("confidence", 0.7)),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                model=self._model_name,
                used_fallback=False,
                degraded=False,
                cost_usd=cost_usd,
            )
        except Exception as exc:
            log.error(
                "gemini.triage_failed",
                extra={"incident_id": prompt.incident_id, "error": str(exc)},
            )
            raise

    async def classify_injection(self, text: str) -> InjectionVerdict:
        """Layer-3 guardrail: LLM-based injection classification."""
        import asyncio

        template = PROMPT_REGISTRY.get("intake-guard", "1.0.0")
        rendered = template.render(incident_text=text[:4000])  # hard cap for safety

        try:
            response = await asyncio.to_thread(
                self._client.generate_content,
                rendered,
                generation_config={"response_mime_type": "application/json"},
            )
            raw = response.text.strip()
            data = json.loads(raw)
            verdict_raw = data.get("verdict", "uncertain")
            # Map to InjectionVerdict.verdict enum
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
            log.error("gemini.classify_injection_failed", extra={"error": str(exc)})
            # Fail-closed on error: treat as uncertain
            return InjectionVerdict(verdict="uncertain", score=0.5, reason="llm_error")

    async def generate(self, prompt: str) -> str:
        """Generate free-form text from a rendered prompt string."""
        import asyncio

        response = await asyncio.to_thread(self._client.generate_content, prompt)
        return response.text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using text-embedding-004."""
        import asyncio

        results: list[list[float]] = []
        for text in texts:
            try:
                response = await asyncio.to_thread(
                    self._genai.embed_content,
                    model="models/text-embedding-004",
                    content=text,
                    task_type="retrieval_document",
                )
                results.append(response["embedding"])
            except Exception as exc:
                log.error("gemini.embed_failed", extra={"error": str(exc)})
                raise
        return results
