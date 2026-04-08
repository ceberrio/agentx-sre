"""Layer 1 — strip control chars, zero-width Unicode, enforce length limit.

Also provides PII redaction and credential hard-block detection (SEC-MJ-005).
"""
from __future__ import annotations

import re
import unicodedata

MAX_LEN = 8000
ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}

# ---------------------------------------------------------------------------
# PII redaction patterns (replace with placeholder — do NOT block)
# ---------------------------------------------------------------------------

_REDACT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "<EMAIL>"),
    (re.compile(r"\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "<PHONE>"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "<SSN>"),
    (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"), "<CARD>"),
]

# ---------------------------------------------------------------------------
# Credential hard-block patterns (these MUST NOT reach the LLM — SEC-MJ-005)
# ---------------------------------------------------------------------------

_CREDENTIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                                         # AWS access key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                                      # GitHub personal token
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),                           # Bearer token
    re.compile(r"-----BEGIN"),                                                 # PEM block
]


def sanitize(text: str) -> str:
    if not text:
        return ""
    text = "".join(c for c in text if c not in ZERO_WIDTH)
    text = "".join(c for c in text if unicodedata.category(c)[0] != "C" or c in "\n\t ")
    return text[:MAX_LEN]


def redact_pii(text: str) -> str:
    """Replace PII tokens with safe placeholders.

    Emails, phones, SSNs, and credit-card numbers are replaced with typed
    tokens so downstream agents never see the raw values. This does NOT block
    the request — use contains_credentials() for hard-block decisions.
    """
    if not text:
        return text
    for pattern, placeholder in _REDACT_RULES:
        text = pattern.sub(placeholder, text)
    return text


def contains_credentials(text: str) -> bool:
    """Return True if the text contains a hard-block credential pattern.

    AWS keys, GitHub tokens, Bearer tokens, and PEM blocks must never reach
    the LLM — the caller should hard-block the request on True.
    """
    if not text:
        return False
    return any(p.search(text) for p in _CREDENTIAL_PATTERNS)
