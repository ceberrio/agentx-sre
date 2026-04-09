"""Tests for app/adapters/llm/circuit_breaker.py.

TC-U-016: CLOSED state — primary succeeds, result returned directly.
TC-U-017: OPEN state — primary fails, fallback is used.
TC-U-018: OPEN state — both primary and fallback fail, degraded response returned.
TC-U-019: HALF-OPEN transition — after cooldown expires, circuit resets to CLOSED.
TC-U-020: classify_injection() fail-closed — when primary raises, returns 'uncertain'.
TC-U-021: Degraded triage response has correct sentinel values.
"""
from __future__ import annotations

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.adapters.llm.circuit_breaker import LLMCircuitBreaker
from app.domain.entities import (
    InjectionVerdict,
    Severity,
    TriagePrompt,
    TriageResult,
)
from app.domain.ports import ILLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prompt() -> TriagePrompt:
    return TriagePrompt(
        incident_id="test-cb-001",
        title="DB down",
        description="PostgreSQL pod crash-looping",
    )


def _successful_triage_result(model: str = "primary") -> TriageResult:
    return TriageResult(
        severity=Severity.P2,
        summary="Test summary",
        suspected_root_cause="Test root cause",
        suggested_owners=["sre-team"],
        confidence=0.9,
        model=model,
    )


class _FailingProvider(ILLMProvider):
    """Always raises RuntimeError to simulate a failing LLM provider."""
    name = "failing"

    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        raise RuntimeError("provider_unavailable")

    async def classify_injection(self, text: str) -> InjectionVerdict:
        raise RuntimeError("provider_unavailable")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("provider_unavailable")

    async def generate(self, prompt: str) -> str:
        raise RuntimeError("provider_unavailable")


class _SucceedingProvider(ILLMProvider):
    """Always succeeds — used as a healthy primary or fallback."""
    name = "succeeding"

    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        return _successful_triage_result(model=self.name)

    async def classify_injection(self, text: str) -> InjectionVerdict:
        return InjectionVerdict(verdict="no", score=0.0)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 4 for _ in texts]

    async def generate(self, prompt: str) -> str:
        return "generated text"


# ---------------------------------------------------------------------------
# TC-U-016: CLOSED state — primary succeeds
# ---------------------------------------------------------------------------

def test_closed_state_primary_succeeds():
    """TC-U-016: In CLOSED state the result comes from the primary provider."""
    primary = _SucceedingProvider()
    breaker = LLMCircuitBreaker(primary=primary, threshold=3)
    prompt = _make_prompt()
    result = asyncio.run(breaker.triage(prompt))
    assert result.model == "succeeding"
    assert result.used_fallback is False


# ---------------------------------------------------------------------------
# TC-U-017: Primary fails, fallback is used
# ---------------------------------------------------------------------------

def test_primary_failure_routes_to_fallback():
    """TC-U-017: When primary raises, the circuit breaker uses the fallback."""
    primary = _FailingProvider()

    class FallbackProvider(_SucceedingProvider):
        name = "fallback"

    fallback = FallbackProvider()
    breaker = LLMCircuitBreaker(primary=primary, fallback=fallback, threshold=1)
    prompt = _make_prompt()
    result = asyncio.run(breaker.triage(prompt))
    # Must have used fallback
    assert result.used_fallback is True


# ---------------------------------------------------------------------------
# TC-U-018: Both primary and fallback fail — degraded response
# ---------------------------------------------------------------------------

def test_both_fail_returns_degraded_response():
    """TC-U-018: When both primary and fallback fail, a degraded result is returned."""
    breaker = LLMCircuitBreaker(
        primary=_FailingProvider(),
        fallback=_FailingProvider(),
        threshold=1,
    )
    prompt = _make_prompt()
    result = asyncio.run(breaker.triage(prompt))
    assert result.degraded is True
    assert result.model == "degraded"
    assert result.needs_human_review is True
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# TC-U-019: HALF-OPEN — after cooldown expires, circuit resets
# ---------------------------------------------------------------------------

def test_half_open_resets_after_cooldown():
    """TC-U-019: After cooldown expires, _is_open() returns False (half-open transition)."""
    breaker = LLMCircuitBreaker(
        primary=_FailingProvider(),
        threshold=1,
        cooldown_s=0,  # Expire immediately
    )
    prompt = _make_prompt()
    # Trigger the circuit to open
    asyncio.run(breaker.triage(prompt))
    # Verify it opened
    assert breaker._opened_at is not None

    # Force time past cooldown — set _opened_at to far in the past
    breaker._opened_at = time.monotonic() - 999
    # Now _is_open should return False and reset state
    assert breaker._is_open() is False
    assert breaker._opened_at is None
    assert breaker._consecutive_failures == 0


# ---------------------------------------------------------------------------
# TC-U-020: classify_injection() fail-closed — uncertain when primary fails
# ---------------------------------------------------------------------------

def test_classify_injection_fail_closed_no_fallback():
    """TC-U-020: classify_injection() returns 'uncertain' when primary raises and no fallback."""
    breaker = LLMCircuitBreaker(primary=_FailingProvider(), fallback=None, threshold=3)
    verdict = asyncio.run(breaker.classify_injection("some text"))
    assert verdict.verdict == "uncertain"
    assert verdict.score == 0.5
    assert verdict.reason == "guardrail_llm_unavailable"


def test_classify_injection_fail_closed_with_failing_fallback():
    """TC-U-020b: BUG-CB-001 — classify_injection() propagates exception when both providers fail.

    BUG FOUND: The fallback call in classify_injection() is NOT wrapped in a try/except.
    When the fallback also raises, the exception propagates unhandled instead of returning
    the fail-closed InjectionVerdict(verdict='uncertain'). This leaves the guardrail broken.
    Expected: returns InjectionVerdict(verdict='uncertain', score=0.5).
    Actual:   raises RuntimeError('provider_unavailable').

    This test documents the current (incorrect) behavior. Do NOT fix in this test file.
    Severity: High — guardrail fails open when both LLM providers are down.
    """
    breaker = LLMCircuitBreaker(
        primary=_FailingProvider(),
        fallback=_FailingProvider(),
        threshold=3,
    )
    # Bug fixed: fallback is now wrapped in try/except; both providers failing returns uncertain
    verdict = asyncio.run(breaker.classify_injection("some text"))
    assert verdict.verdict == "uncertain"
    assert verdict.score == 0.5
    assert verdict.reason == "guardrail_llm_unavailable"


# ---------------------------------------------------------------------------
# TC-U-021: Degraded triage response sentinel values
# ---------------------------------------------------------------------------

def test_degraded_response_has_correct_sentinel_values():
    """TC-U-021: Degraded TriageResult carries correct hardcoded sentinel values."""
    breaker = LLMCircuitBreaker(
        primary=_FailingProvider(),
        fallback=None,
        threshold=1,
    )
    prompt = _make_prompt()
    result = asyncio.run(breaker.triage(prompt))
    assert result.degraded is True
    assert result.used_fallback is True
    assert result.model == "degraded"
    assert result.confidence == 0.0
    assert result.needs_human_review is True
    assert result.severity == Severity.P3
    assert "sre-oncall" in result.suggested_owners


# ---------------------------------------------------------------------------
# Additional edge cases — failure counter and threshold logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_consecutive_failures_increment():
    """Failure counter increments correctly on each failure."""
    breaker = LLMCircuitBreaker(primary=_FailingProvider(), threshold=5)
    await breaker._record_failure()
    await breaker._record_failure()
    assert breaker._consecutive_failures == 2


@pytest.mark.asyncio
async def test_circuit_opens_at_threshold():
    """Circuit opens precisely when consecutive_failures reaches threshold."""
    breaker = LLMCircuitBreaker(primary=_FailingProvider(), threshold=3)
    for _ in range(3):
        await breaker._record_failure()
    assert breaker._opened_at is not None


@pytest.mark.asyncio
async def test_success_resets_failure_counter():
    """_record_success() clears failure counter and opened_at."""
    breaker = LLMCircuitBreaker(primary=_FailingProvider(), threshold=3)
    await breaker._record_failure()
    await breaker._record_failure()
    await breaker._record_success()
    assert breaker._consecutive_failures == 0
    assert breaker._opened_at is None
