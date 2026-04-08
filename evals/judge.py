"""LLM-as-judge — DEC-008, ARC-016.

Evaluates the quality of a triage result against a golden case.
Uses the 'judge' prompt registered in PROMPT_REGISTRY (1.0.0).

The judge calls Gemini via the LLM port so the eval pipeline does not
bypass the adapter layer. All metrics are normalized to [0.0, 1.0].

Scoring formula (from judge.yaml):
    overall = 0.4 * severity_score + 0.4 * root_cause_score + 0.2 * components_score

Usage:
    from evals.judge import JudgeResult, score_triage
    result = await score_triage(golden_case, triage_output)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, replace as dataclasses_replace
from typing import Any, Optional

log = logging.getLogger(__name__)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a float to [lo, hi]. Guards against LLM returning values outside [0, 1]."""
    return max(lo, min(hi, value))


@dataclass
class JudgeResult:
    """Structured output of one judge evaluation."""

    case_id: str
    severity_correct: bool
    severity_score: float
    root_cause_score: float
    components_score: float
    overall_score: float
    judge_reasoning: str
    error: Optional[str] = None

    @property
    def passed(self) -> bool:
        """True if overall_score meets the minimum threshold (0.70)."""
        return self.overall_score >= 0.70


def _compute_jaccard(expected: list[str], actual: list[str]) -> float:
    """Jaccard similarity between two lists treated as sets (case-insensitive)."""
    set_a = {x.lower().strip() for x in expected}
    set_b = {x.lower().strip() for x in actual}
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _keyword_recall(expected_keywords: list[str], actual_text: str) -> float:
    """Fraction of expected keywords found in actual_text (case-insensitive)."""
    if not expected_keywords:
        return 1.0
    lower_text = actual_text.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in lower_text)
    return found / len(expected_keywords)


def _compute_local_score(golden: dict[str, Any], triage: dict[str, Any]) -> JudgeResult:
    """Deterministic fallback when the LLM judge is not available."""
    case_id: str = golden.get("id", "unknown")
    expected = golden.get("expected", {})

    expected_severity: str = expected.get("severity", "P3")
    actual_severity: str = triage.get("severity", "")
    severity_correct = expected_severity.upper() == actual_severity.upper()
    severity_score = 1.0 if severity_correct else 0.0

    expected_keywords: list[str] = expected.get("root_cause_keywords", [])
    actual_root_cause: str = triage.get("suspected_root_cause", "") + " " + triage.get("summary", "")
    root_cause_score = _keyword_recall(expected_keywords, actual_root_cause)

    expected_components: list[str] = expected.get("affected_components", [])
    actual_owners: list[str] = triage.get("suggested_owners", [])
    components_score = _compute_jaccard(expected_components, actual_owners)

    overall = 0.4 * severity_score + 0.4 * root_cause_score + 0.2 * components_score

    return JudgeResult(
        case_id=case_id,
        severity_correct=severity_correct,
        severity_score=severity_score,
        root_cause_score=root_cause_score,
        components_score=components_score,
        overall_score=round(overall, 4),
        judge_reasoning="Deterministic evaluation (LLM judge not available).",
    )


async def score_triage(
    golden_case: dict[str, Any],
    triage_output: dict[str, Any],
    llm_provider: Any = None,
) -> JudgeResult:
    """Evaluate a triage result using the LLM-as-judge.

    Args:
        golden_case: One record from golden.jsonl — contains 'id', 'input', 'expected'.
        triage_output: The TriageResult serialized as a dict from the triage agent.
        llm_provider: An ILLMProvider instance. If None, falls back to deterministic scoring.

    Returns:
        JudgeResult with all scores filled in.
    """
    case_id: str = golden_case.get("id", "unknown")

    if llm_provider is None:
        log.info("judge.deterministic_mode", extra={"case_id": case_id})
        return _compute_local_score(golden_case, triage_output)

    try:
        from app.llm.prompt_registry import PROMPT_REGISTRY

        template = PROMPT_REGISTRY.get("judge", "1.0.0")
        expected = golden_case.get("expected", {})

        rendered = template.render(
            golden_input=json.dumps(golden_case.get("input", {}), ensure_ascii=False),
            expected_severity=expected.get("severity", "P3"),
            expected_components=", ".join(expected.get("affected_components", [])),
            expected_keywords=", ".join(expected.get("root_cause_keywords", [])),
            actual_severity=triage_output.get("severity", ""),
            actual_summary=triage_output.get("summary", "")[:400],
            actual_root_cause=triage_output.get("suspected_root_cause", "")[:400],
            actual_owners=", ".join(triage_output.get("suggested_owners", [])),
        )

        # Use generate() for plain text-in / JSON-out — classify_injection is a
        # specialized port method for injection detection and must not be abused
        # as a generic text generator (CR-003).
        raw_response = await llm_provider.generate(rendered)

        json_match = re.search(r"\{[\s\S]+\}", raw_response)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            # Response was not JSON — fall back to deterministic.
            log.warning("judge.response_not_json", extra={"case_id": case_id, "raw": raw_response[:200]})
            return _compute_local_score(golden_case, triage_output)

        severity_correct = bool(parsed.get("severity_correct", False))
        # Clamp all float scores to [0.0, 1.0] — LLM may return percentages (MN-004).
        severity_score = _clamp(float(parsed.get("severity_score", 0.0)))
        root_cause_score = _clamp(float(parsed.get("root_cause_score", 0.0)))
        components_score = _clamp(float(parsed.get("components_score", 0.0)))
        overall_score = _clamp(float(parsed.get("overall_score", 0.0)))
        reasoning = str(parsed.get("judge_reasoning", ""))

        return JudgeResult(
            case_id=case_id,
            severity_correct=severity_correct,
            severity_score=severity_score,
            root_cause_score=root_cause_score,
            components_score=components_score,
            overall_score=round(overall_score, 4),
            judge_reasoning=reasoning,
        )

    except Exception as exc:  # noqa: BLE001
        log.error("judge.llm_failed", extra={"case_id": case_id, "error": str(exc)})
        result = _compute_local_score(golden_case, triage_output)
        return dataclasses_replace(result, error=str(exc))


async def score_adversarial(case: dict[str, Any], blocked: bool) -> bool:
    """Verify that an adversarial case was blocked.

    Returns True if the outcome matches expectation (blocked == expected.blocked).
    """
    expected_blocked: bool = case.get("expected", {}).get("blocked", True)
    return blocked == expected_blocked
