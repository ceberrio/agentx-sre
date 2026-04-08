"""Tests for FASE 5 eval pipeline: judge.py and runner.py.

AC-01: JudgeResult.passed is True when overall_score >= 0.70.
AC-02: JudgeResult.passed is False when overall_score < 0.70.
AC-03: score_triage deterministic path returns a JudgeResult for any golden case.
AC-04: score_adversarial returns True when blocked matches expected.blocked.
AC-05: Datasets contain minimum required samples (MIN_GOLDEN=5, MIN_ADVERSARIAL=5).
BR-01: Jaccard similarity is 1.0 for identical sets and 0.0 for disjoint sets.
BR-02: Keyword recall is proportional to the fraction of keywords found.
BR-03: runner._validate_datasets raises ValueError when sample count is too low.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

# Make evals importable from the project root.
_REPO_ROOT = Path(__file__).parents[3]  # HACKATHON/
sys.path.insert(0, str(_REPO_ROOT))

from evals.judge import (
    JudgeResult,
    _compute_jaccard,
    _keyword_recall,
    _compute_local_score,
    score_triage,
    score_adversarial,
)
from evals.runner import (
    GOLDEN_PATH,
    ADVERSARIAL_PATH,
    MIN_GOLDEN_SAMPLES,
    MIN_ADVERSARIAL_SAMPLES,
    _load_jsonl,
    _validate_datasets,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_golden(
    case_id: str = "test-001",
    severity: str = "P1",
    keywords: list[str] | None = None,
    components: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "input": {"title": "DB down", "description": "crash-loop connection refused stripe"},
        "expected": {
            "severity": severity,
            "root_cause_keywords": keywords or ["crash-loop", "connection refused"],
            "components": components or ["payment-service", "stripe-gateway"],
        },
    }


def _make_triage(
    severity: str = "P1",
    root_cause: str = "crash-loop connection refused stripe",
    owners: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "summary": "Payment service down due to stripe gateway crash.",
        "suspected_root_cause": root_cause,
        "suggested_owners": owners or ["payment-service", "stripe-gateway"],
    }


# ---------------------------------------------------------------------------
# BR-01: Jaccard similarity
# ---------------------------------------------------------------------------


class TestJaccardSimilarity:
    """BR-01: Jaccard similarity correctness."""

    def test_identical_sets_return_one(self):
        assert _compute_jaccard(["a", "b"], ["a", "b"]) == 1.0

    def test_disjoint_sets_return_zero(self):
        assert _compute_jaccard(["a", "b"], ["c", "d"]) == 0.0

    def test_partial_overlap(self):
        score = _compute_jaccard(["a", "b", "c"], ["b", "c", "d"])
        assert 0.0 < score < 1.0

    def test_empty_sets_return_one(self):
        assert _compute_jaccard([], []) == 1.0

    def test_case_insensitive(self):
        assert _compute_jaccard(["Payment-Service"], ["payment-service"]) == 1.0


# ---------------------------------------------------------------------------
# BR-02: Keyword recall
# ---------------------------------------------------------------------------


class TestKeywordRecall:
    """BR-02: Keyword recall proportionality."""

    def test_all_keywords_found_returns_one(self):
        score = _keyword_recall(["crash-loop", "stripe"], "crash-loop connection to stripe refused")
        assert score == 1.0

    def test_no_keywords_found_returns_zero(self):
        score = _keyword_recall(["timeout", "dns"], "everything is fine")
        assert score == 0.0

    def test_half_keywords_returns_half(self):
        score = _keyword_recall(["crash-loop", "stripe"], "only crash-loop mentioned here")
        assert score == pytest.approx(0.5)

    def test_empty_keywords_returns_one(self):
        assert _keyword_recall([], "any text") == 1.0


# ---------------------------------------------------------------------------
# AC-01/02: JudgeResult.passed threshold
# ---------------------------------------------------------------------------


class TestJudgeResultPassed:
    """AC-01/02: JudgeResult.passed boundary condition at 0.70."""

    def test_overall_exactly_070_is_passing(self):
        result = JudgeResult(
            case_id="x",
            severity_correct=True,
            severity_score=0.7,
            root_cause_score=0.7,
            components_score=0.7,
            overall_score=0.70,
            judge_reasoning="ok",
        )
        assert result.passed is True

    def test_overall_below_070_is_failing(self):
        result = JudgeResult(
            case_id="x",
            severity_correct=False,
            severity_score=0.0,
            root_cause_score=0.5,
            components_score=0.5,
            overall_score=0.30,
            judge_reasoning="poor",
        )
        assert result.passed is False

    def test_overall_above_070_is_passing(self):
        result = JudgeResult(
            case_id="x",
            severity_correct=True,
            severity_score=1.0,
            root_cause_score=0.9,
            components_score=0.8,
            overall_score=0.94,
            judge_reasoning="excellent",
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# AC-03: score_triage deterministic path
# ---------------------------------------------------------------------------


class TestScoreTriage:
    """AC-03: Deterministic judge returns a valid JudgeResult."""

    @pytest.mark.asyncio
    async def test_perfect_match_returns_high_score(self):
        golden = _make_golden(severity="P1", keywords=["crash-loop", "stripe"], components=["payment-service"])
        triage = _make_triage(severity="P1", root_cause="crash-loop stripe gateway", owners=["payment-service"])
        result = await score_triage(golden, triage, llm_provider=None)
        assert result.case_id == "test-001"
        assert result.severity_correct is True
        assert result.overall_score > 0.70

    @pytest.mark.asyncio
    async def test_wrong_severity_reduces_score(self):
        golden = _make_golden(severity="P1")
        triage = _make_triage(severity="P3")  # Wrong severity
        result = await score_triage(golden, triage, llm_provider=None)
        assert result.severity_correct is False
        assert result.severity_score == 0.0

    @pytest.mark.asyncio
    async def test_result_is_judge_result_instance(self):
        golden = _make_golden()
        triage = _make_triage()
        result = await score_triage(golden, triage, llm_provider=None)
        assert isinstance(result, JudgeResult)
        assert 0.0 <= result.overall_score <= 1.0


# ---------------------------------------------------------------------------
# AC-04: score_adversarial correctness
# ---------------------------------------------------------------------------


class TestScoreAdversarial:
    """AC-04: score_adversarial returns True when blocked matches expected."""

    @pytest.mark.asyncio
    async def test_blocked_when_expected_returns_true(self):
        case = {"id": "adv-001", "expected": {"blocked": True}}
        assert await score_adversarial(case, blocked=True) is True

    @pytest.mark.asyncio
    async def test_not_blocked_when_expected_blocked_returns_false(self):
        case = {"id": "adv-001", "expected": {"blocked": True}}
        assert await score_adversarial(case, blocked=False) is False

    @pytest.mark.asyncio
    async def test_not_blocked_when_not_expected_returns_true(self):
        case = {"id": "adv-safe-01", "expected": {"blocked": False}}
        assert await score_adversarial(case, blocked=False) is True


# ---------------------------------------------------------------------------
# AC-05: Dataset sample count
# ---------------------------------------------------------------------------


class TestDatasetSampleCount:
    """AC-05: Both datasets meet minimum sample requirements."""

    def test_golden_dataset_has_minimum_samples(self):
        assert GOLDEN_PATH.exists(), f"Golden dataset not found at {GOLDEN_PATH}"
        cases = _load_jsonl(GOLDEN_PATH)
        assert len(cases) >= MIN_GOLDEN_SAMPLES, (
            f"Golden dataset has {len(cases)} cases; minimum is {MIN_GOLDEN_SAMPLES}"
        )

    def test_adversarial_dataset_has_minimum_samples(self):
        assert ADVERSARIAL_PATH.exists(), f"Adversarial dataset not found at {ADVERSARIAL_PATH}"
        cases = _load_jsonl(ADVERSARIAL_PATH)
        assert len(cases) >= MIN_ADVERSARIAL_SAMPLES, (
            f"Adversarial dataset has {len(cases)} cases; minimum is {MIN_ADVERSARIAL_SAMPLES}"
        )

    def test_golden_dataset_has_required_fields(self):
        cases = _load_jsonl(GOLDEN_PATH)
        for case in cases:
            assert "id" in case
            assert "input" in case
            assert "expected" in case
            assert "severity" in case["expected"]

    def test_adversarial_dataset_has_required_fields(self):
        cases = _load_jsonl(ADVERSARIAL_PATH)
        for case in cases:
            assert "id" in case
            assert "expected" in case
            assert "blocked" in case["expected"]


# ---------------------------------------------------------------------------
# BR-03: _validate_datasets raises on insufficient samples
# ---------------------------------------------------------------------------


class TestValidateDatasets:
    """BR-03: _validate_datasets raises ValueError for insufficient samples."""

    def test_raises_when_golden_too_small(self):
        with pytest.raises(ValueError, match="Golden dataset"):
            _validate_datasets(golden=[{"id": "x"}], adversarial=[{"id": f"a{i}"} for i in range(5)])

    def test_raises_when_adversarial_too_small(self):
        with pytest.raises(ValueError, match="Adversarial dataset"):
            _validate_datasets(
                golden=[{"id": f"g{i}"} for i in range(5)],
                adversarial=[{"id": "x"}],
            )

    def test_does_not_raise_for_valid_sizes(self):
        # Should not raise
        _validate_datasets(
            golden=[{"id": f"g{i}"} for i in range(5)],
            adversarial=[{"id": f"a{i}"} for i in range(5)],
        )
