"""Triage value objects — the structured contract for ILLMProvider."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .incident import Severity
from .context import ContextDoc


class TriagePrompt(BaseModel):
    """Inputs the triage call needs. Pure data — no LLM-specific fields."""

    incident_id: str
    title: str
    description: str
    log_excerpt: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_mime: Optional[str] = None
    context_docs: list[ContextDoc] = Field(default_factory=list)


class TriageResult(BaseModel):
    """Structured output every ILLMProvider.triage() must return."""

    severity: Severity
    summary: str
    suspected_root_cause: str
    suggested_owners: list[str] = Field(default_factory=list)
    needs_human_review: bool = False
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    used_fallback: bool = False
    degraded: bool = False
    # Provider-agnostic cost populated by the LLM adapter (ARC-002).
    # Avoids agent code importing adapter-specific pricing constants.
    cost_usd: float = 0.0


class InjectionVerdict(BaseModel):
    """Output of ILLMProvider.classify_injection() — layer-3 guardrail."""

    verdict: Literal["yes", "no", "uncertain"]
    score: float = Field(ge=0.0, le=1.0)
    reason: Optional[str] = None
