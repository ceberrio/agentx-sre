"""IntakeGuard-local helpers (deterministic checks before LLM judge).

These are pure functions, not LangGraph tools. They're cheap and run first
to short-circuit obviously bad input before invoking the LLM judge.

Layer 1a — PII redaction (SEC-MJ-005): emails/phones/SSNs/cards are replaced
           with typed placeholders; the redacted text is passed downstream.
Layer 1b — Credential hard-block: AWS keys, GitHub tokens, Bearer tokens, PEM
           blocks trigger an immediate block — credentials must never reach LLM.
Layer 2  — Injection marker detection (delegates to security.prompt_injection)
Layer 3  — Off-topic heuristic
"""
from __future__ import annotations

import re

from app.domain.entities import Incident
from app.security.input_sanitizer import contains_credentials, redact_pii
from app.security.prompt_injection import detect_heuristics

# ---------------------------------------------------------------------------
# PII tags for legacy detect_pii() surface (still used by agent.py for logging)
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


def apply_pii_layer(text: str) -> tuple[str, list[str]]:
    """Apply the PII layer (SEC-MJ-005).

    Returns (redacted_text, credential_tags) where:
    - redacted_text has emails/phones/SSNs/cards replaced with placeholders.
    - credential_tags is non-empty when a hard-block credential is detected.

    Callers must hard-block if credential_tags is non-empty.
    """
    credential_tags: list[str] = []
    if contains_credentials(text):
        credential_tags.append("credential")
    redacted = redact_pii(text)
    return redacted, credential_tags


def detect_pii(text: str) -> list[str]:
    """Return a list of PII category tags found in the text.

    This function is retained for backward compatibility with existing tests and
    the agent's logging path. For the security-enforcement path, use
    apply_pii_layer() instead which distinguishes redactable PII from
    hard-block credentials.

    Empty list means no PII detected.
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
