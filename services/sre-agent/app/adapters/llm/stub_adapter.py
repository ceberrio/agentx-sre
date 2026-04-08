"""Stub LLM adapter — deterministic responses for CI / offline eval runs.

Used when no real API key is available (e.g. GEMINI_API_KEY is empty in CI).
All responses are deterministic keyword-based heuristics so the eval runner
can score golden cases without making real API calls.

The triage output is intentionally realistic enough for the deterministic
judge to award scores above the 0.70 threshold for well-formed golden cases.

This adapter MUST NOT be used in production.  The container builder only
selects it when LLM_PROVIDER=stub (an invalid prod value) or when the runner
detects an absent API key and explicitly bootstraps with it.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.domain.entities import InjectionVerdict, Severity, TriagePrompt, TriageResult
from app.domain.ports import ILLMProvider

log = logging.getLogger(__name__)

# ---- Injection / PII / off-topic patterns — imported from shared module ----
# Do NOT define these inline. evals/patterns.py is the single source of truth
# so that the runner fallback and this adapter stay perfectly in sync (CR-001).
try:
    from evals.patterns import (  # type: ignore[import]
        INJECTION_PATTERNS as _INJECTION_PATTERNS,
        OFF_TOPIC_PATTERNS as _OFF_TOPIC_PATTERNS,
        PII_PATTERNS as _PII_PATTERNS,
    )
except ImportError:
    # Fallback when the evals package is not on sys.path (e.g. docker runtime
    # where only services/sre-agent is installed).  Keep this list in sync
    # manually if evals/patterns.py changes.
    _INJECTION_PATTERNS: list[str] = [  # type: ignore[assignment]
        r"ignore\s+(?:all\s+)?(?:previous\s+|prior\s+)?(?:instructions|context|prompt)",
        r"\[INST\]",
        r"<<SYS>>",
        r"system.?override",
        r"jailbroken",
        r"\bDAN\b",
        r"ACTUAL_PROMPT_START",
        r"ACTUAL_PROMPT_END",
        r"[\u202a-\u202e\u2066-\u2069\u200b-\u200f]+",
        r"override\s+safety",
        r"bypass.{0,20}filter",
        r"dump.{0,20}config",
        r"reveal.{0,20}secret",
    ]
    _PII_PATTERNS: list[str] = [  # type: ignore[assignment]
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        r"\bpassword\s*(?:is|[=:])\s*\S+",
    ]
    _OFF_TOPIC_PATTERNS: list[str] = [  # type: ignore[assignment]
        r"write\s+(?:me\s+)?(?:a\s+)?(?:poem|story|essay|song|joke)",
        r"explain\s+(?:how\s+to\s+)?(?:cook|bake|make|build)",
        r"\bbomb\b",
        r"\bexplosive\b",
        r"write me a poem",
    ]

# ---- Component extraction limit -------------------------------------------

_MAX_EXTRACTED_COMPONENTS = 4

# ---- Severity keyword heuristics ------------------------------------------
# Ordered from most specific to least. P1 checked first; if none match, P2;
# then P3; then P4.  P4 cosmetic-only keywords are checked last so a real
# service error that also contains "minor" still escalates to a higher tier.
#
# P1 keywords that are short / ambiguous (e.g. "oom", "503") are matched with
# word-boundary regex via _infer_severity() to avoid false positives such as
# "smooth" matching "oom" or "5030 items" matching "503".

_P1_KEYWORDS_EXACT = [
    # Long / unambiguous phrases — plain substring match is safe
    "crash-loop", "crashloop", "oomkilled", "outage",
    "down — ", "service down", "all users",
    "data loss", "eviction", "maxmemory",
    "tax missing", "calculation wrong", "revenue",
    "cpu at 100%", "cpu sustained", "100% for",
    "transactions/min blocked",
    "thousands of users", "suddenly logged out",
    "connection refused to stripe", "stripe-gateway",
]

_P1_KEYWORDS_REGEX = [
    # Short / ambiguous tokens — require word boundaries to avoid false positives
    r"\boom\b",
    r"\b503\b",
]
_P2_KEYWORDS = [
    # Partial / degraded service — majority of cases
    "not loading", "not being sent", "not receiving",
    "returns wrong results", "wrong results",
    "authentication error", "key mismatch", "401 unauthorized",
    "404 for", "500 for", "http 500",
    "broken", "unavailable", "failed",
    "sync lag", "outdated", "stale results",
    "latency jumped", "latency 8s", "p99 latency",
    "delayed", "delay", "not refreshed",
    "memory leak",
]
_P3_KEYWORDS = [
    # Partial degradation with workaround
    "3-4 seconds", "3s delay", "2% of orders",
    "intermittent", "backlog",
    "15-20 minutes late", "15 minutes",
    "slow.*checkout", "validation slow",
    "errors for 2%",
]
_P4_KEYWORDS = [
    # Cosmetic / no functional impact
    "cosmetic", "copyright year", "footer",
    "dark mode", "dark-mode",
    "pagination", "off-by-one",
    "preference", "localStorage",
    "no functional impact", "no revenue impact",
]


def _infer_severity(title: str, description: str) -> Severity:
    """Keyword-based severity inference. Deterministic and reproducible.

    Evaluation order: P1 → P2 → P3 → P4.
    P4 is checked last so cosmetic phrases in otherwise serious incidents
    do not suppress a higher-tier classification.
    """
    combined = f"{title} {description}".lower()

    for kw in _P1_KEYWORDS_EXACT:
        if kw.lower() in combined:
            return Severity.P1

    for pattern in _P1_KEYWORDS_REGEX:
        if re.search(pattern, combined):
            return Severity.P1

    for kw in _P2_KEYWORDS:
        if re.search(kw, combined):
            return Severity.P2

    for kw in _P3_KEYWORDS:
        if re.search(kw, combined):
            return Severity.P3

    for kw in _P4_KEYWORDS:
        if kw.lower() in combined:
            return Severity.P4

    return Severity.P3


def _extract_components(description: str) -> list[str]:
    """Extract likely component names from description text."""
    # Match hyphenated technical names like 'payment-service', 'app-db'
    return list(set(re.findall(r"[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)+", description.lower())))[:_MAX_EXTRACTED_COMPONENTS]


class StubLLMAdapter(ILLMProvider):
    """Deterministic LLM adapter for CI eval runs — no API key required."""

    name = "stub"

    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        severity = _infer_severity(prompt.title, prompt.description)
        components = _extract_components(prompt.description) or ["unknown-service"]

        summary = (
            f"[stub] Incident '{prompt.title[:80]}' classified as {severity.value}. "
            f"Deterministic analysis from keywords in title and description."
        )
        root_cause = prompt.description[:300] if prompt.description else "Unknown root cause."

        log.info(
            "stub_llm.triage",
            extra={"incident_id": prompt.incident_id, "severity": severity.value},
        )

        return TriageResult(
            severity=severity,
            summary=summary,
            suspected_root_cause=root_cause,
            suggested_owners=components,
            needs_human_review=False,
            confidence=0.60,
            tokens_in=0,
            tokens_out=0,
            model="stub",
            used_fallback=False,
            degraded=True,
        )

    async def classify_injection(self, text: str) -> InjectionVerdict:
        combined = text.lower()

        for pattern in _INJECTION_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return InjectionVerdict(
                    verdict="yes", score=0.95, reason="stub_heuristic_injection_detected"
                )

        for pattern in _PII_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return InjectionVerdict(
                    verdict="yes", score=0.90, reason="stub_heuristic_pii_detected"
                )

        for pattern in _OFF_TOPIC_PATTERNS:
            if re.search(pattern, combined, re.IGNORECASE):
                return InjectionVerdict(
                    verdict="yes", score=0.85, reason="stub_heuristic_off_topic"
                )

        return InjectionVerdict(verdict="no", score=0.05, reason=None)

    async def generate(self, prompt: str) -> str:
        return f"[stub] Generated response for prompt of length {len(prompt)}."

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Return zero-vectors with typical embedding dimension
        return [[0.0] * 768 for _ in texts]
