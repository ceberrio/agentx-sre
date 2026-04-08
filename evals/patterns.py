"""Shared detection pattern lists — single source of truth (ARC-016 / CR-001 / CR-004).

These lists are imported by:
  - evals/runner.py   — deterministic fallback in _simulate_intake()
  - services/sre-agent/app/adapters/llm/stub_adapter.py — StubLLMAdapter

Any change to these patterns must be reflected in both consumers automatically
because they share this module. Keep patterns sorted by category and add a
comment for every non-obvious regex.
"""
from __future__ import annotations

INJECTION_PATTERNS: list[str] = [
    # Multi-word ignore-previous-instructions variants
    r"ignore\s+(?:all\s+)?(?:previous\s+|prior\s+)?(?:instructions|context|prompt)",
    r"\[INST\]",
    r"<<SYS>>",
    r"system.?override",  # e.g. system_override, system-override, {system_override:
    r"jailbroken",
    r"\bDAN\b",
    r"ACTUAL_PROMPT_START",
    r"ACTUAL_PROMPT_END",
    # Unicode obfuscation — zero-width / directional control characters
    r"[\u202a-\u202e\u2066-\u2069\u200b-\u200f]+",
    # override safety / bypass patterns
    r"override\s+safety",
    r"bypass.{0,20}filter",
    r"dump.{0,20}config",
    r"reveal.{0,20}secret",
]

PII_PATTERNS: list[str] = [
    r"\b\d{3}-\d{2}-\d{4}\b",                    # SSN
    r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",  # credit card
    r"\bpassword\s*(?:is|[=:])\s*\S+",            # password leak — "password is X" or "password: X" or "password=X"
]

OFF_TOPIC_PATTERNS: list[str] = [
    r"write\s+(?:me\s+)?(?:a\s+)?(?:poem|story|essay|song|joke)",
    r"explain\s+(?:how\s+to\s+)?(?:cook|bake|make|build)",
    r"\bbomb\b",
    r"\bexplosive\b",
    r"write me a poem",
]
