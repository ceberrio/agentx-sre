"""Layer 2 — heuristic prompt-injection detection.

Layer 3 (LLM judge) lives in the orchestration node and calls ILLMProvider.classify_injection().
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PATTERNS = [
    r"ignore (all )?previous (instructions|prompts)",
    r"disregard the (system|above)",
    r"you are now",
    r"\bsystem:\s",
    r"\bassistant:\s",
    r"<\s*system\s*>",
    r"reveal (your )?(system )?prompt",
    r"jailbreak",
]
COMPILED = [re.compile(p, re.IGNORECASE) for p in PATTERNS]


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
