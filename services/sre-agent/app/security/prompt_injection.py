"""Layer 2 — heuristic prompt-injection detection.

Layer 3 (LLM judge) lives in the orchestration node and calls ILLMProvider.classify_injection().

Pattern source: evals/patterns.py is the single source of truth (ARC-016).
The runtime detection list is imported from there so the eval suite and the
live guard are always in sync. A fallback list is provided for environments
where evals/ is not on sys.path (e.g. restricted Docker images).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from evals.patterns import INJECTION_PATTERNS
except ImportError:
    # Fallback for environments where evals/ is not on sys.path.
    # Keep this list identical to evals/patterns.py — any divergence is a bug.
    INJECTION_PATTERNS = [
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

COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


@dataclass
class HeuristicVerdict:
    blocked: bool
    reason: str | None = None
    score: float = 0.0


def detect_heuristics(text: str) -> HeuristicVerdict:
    if not text:
        return HeuristicVerdict(blocked=False, score=0.0)
    hits = [p.pattern for p in COMPILED if p.search(text)]
    if hits:
        return HeuristicVerdict(blocked=True, reason=f"heuristic_match:{hits[0]}", score=1.0)
    return HeuristicVerdict(blocked=False, score=0.0)
