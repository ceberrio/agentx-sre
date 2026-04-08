"""IntakeGuard-local helpers (deterministic checks before LLM judge).

These are pure functions, not LangGraph tools. They're cheap and run first
to short-circuit obviously bad input before invoking the LLM judge.

Layer 1 — PII detection
Layer 2 — Injection marker detection (delegates to security.prompt_injection)
Layer 3 — Off-topic heuristic
"""
from __future__ import annotations

import re

from app.domain.entities import Incident
from app.security.prompt_injection import detect_heuristics

# ---------------------------------------------------------------------------
# PII patterns (Layer 1)
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[str, str]] = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "ssn"),                          # US SSN
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "credit_card"),            # 16-digit card
    (r"\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "phone"),
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "email"),
    (r"\b(?:password|passwd|secret|token|api[_-]key)\s*[:=]\s*\S+", "credential"),
]

_PII_COMPILED = [(re.compile(p, re.IGNORECASE), tag) for p, tag in _PII_PATTERNS]

# ---------------------------------------------------------------------------
# Off-topic keywords — things a legitimate SRE eShop incident might mention
# If NONE of these appear the incident is probably off-topic.
# ---------------------------------------------------------------------------

_ESHOP_KEYWORDS = {
    "api", "service", "database", "db", "error", "timeout", "latency",
    "crash", "exception", "container", "kubernetes", "k8s", "pod",
    "deploy", "deployment", "redis", "postgres", "postgresql", "sql",
    "http", "response", "request", "queue", "rabbitmq", "message",
    "catalog", "basket", "ordering", "payment", "identity", "auth",
    "checkout", "webhook", "cpu", "memory", "disk", "network", "502",
    "503", "504", "500", "down", "outage", "unavailable", "alert",
    "prometheus", "grafana", "log", "trace", "metric", "health",
    "eshop", "microservice", "endpoint", "load", "spike", "high",
    "slow", "failed", "failure", "issue", "incident",
}


def detect_pii(text: str) -> list[str]:
    """Return a list of PII category tags found in the text.

    Empty list means clean.
    """
    if not text:
        return []
    found: list[str] = []
    for pattern, tag in _PII_COMPILED:
        if pattern.search(text) and tag not in found:
            found.append(tag)
    return found


def detect_injection_markers(text: str) -> bool:
    """Return True if text contains classic prompt-injection markers.

    Delegates to the canonical pattern set in security.prompt_injection.
    """
    if not text:
        return False
    verdict = detect_heuristics(text)
    return verdict.blocked


def is_off_topic(incident: Incident) -> bool:
    """Return True if the incident seems unrelated to SRE / eShop operations.

    Uses a conservative keyword overlap heuristic. Borderline cases fall through
    to the LLM judge (Layer 4). Returns False (i.e. "on-topic") when uncertain
    so we don't over-block legitimate incidents.
    """
    combined = f"{incident.title} {incident.description}".lower()
    matches = sum(1 for kw in _ESHOP_KEYWORDS if kw in combined)
    # Threshold: at least 1 keyword match required to be considered on-topic.
    # This is deliberately permissive to avoid false positives.
    return matches == 0
