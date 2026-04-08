"""LLMCircuitBreaker — wraps two ILLMProvider instances with primary→fallback→degraded.

This is itself an ILLMProvider, so the rest of the system never knows resilience
exists. Add a third provider tomorrow by chaining two breakers.

State machine:
    CLOSED   → primary calls succeed
    OPEN     → too many recent failures → route to fallback
    HALF     → after cooldown, send one probe to primary
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.domain.entities import (
    InjectionVerdict,
    Severity,
    TriagePrompt,
    TriageResult,
)
from app.domain.ports import ILLMProvider

log = logging.getLogger(__name__)


class LLMCircuitBreaker(ILLMProvider):
    name = "circuit_breaker"

    def __init__(
        self,
        primary: ILLMProvider,
        fallback: Optional[ILLMProvider] = None,
        threshold: int = 3,
        cooldown_s: int = 60,
        timeout_s: int = 25,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._threshold = threshold
        self._cooldown_s = cooldown_s
        self._timeout_s = timeout_s
        self._consecutive_failures = 0
        self._opened_at: Optional[float] = None

    # ----- state helpers -----
    def _is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at > self._cooldown_s:
            self._opened_at = None
            self._consecutive_failures = 0
            log.info("circuit_breaker.half_open")
            return False
        return True

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self._opened_at = time.monotonic()
            log.warning("circuit_breaker.opened", extra={"failures": self._consecutive_failures})

    # ----- ILLMProvider implementation -----
    async def triage(self, prompt: TriagePrompt) -> TriageResult:
        if not self._is_open():
            try:
                result = await asyncio.wait_for(
                    self._primary.triage(prompt), timeout=self._timeout_s
                )
                self._record_success()
                return result
            except Exception as e:  # noqa: BLE001
                log.warning("triage.primary_failed", extra={"error": str(e)})
                self._record_failure()

        if self._fallback is not None:
            try:
                result = await asyncio.wait_for(
                    self._fallback.triage(prompt), timeout=self._timeout_s
                )
                result.used_fallback = True
                log.info("triage.fallback_used", extra={"provider": self._fallback.name})
                return result
            except Exception as e:  # noqa: BLE001
                log.error("triage.fallback_failed", extra={"error": str(e)})

        log.error("triage.degraded_mode", extra={"incident_id": prompt.incident_id})
        return TriageResult(
            severity=Severity.P3,
            summary="Automated triage unavailable. Human review required.",
            suspected_root_cause="LLM providers degraded; deterministic fallback in effect.",
            suggested_owners=["sre-oncall"],
            needs_human_review=True,
            confidence=0.0,
            model="degraded",
            used_fallback=True,
            degraded=True,
        )

    async def generate(self, prompt: str) -> str:
        """Generate free-form text with primary→fallback→degraded resilience."""
        if not self._is_open():
            try:
                result = await asyncio.wait_for(
                    self._primary.generate(prompt), timeout=self._timeout_s
                )
                self._record_success()
                return result
            except Exception as e:  # noqa: BLE001
                log.warning("generate.primary_failed", extra={"error": str(e)})
                self._record_failure()

        if self._fallback is not None:
            try:
                result = await asyncio.wait_for(
                    self._fallback.generate(prompt), timeout=self._timeout_s
                )
                log.info("generate.fallback_used", extra={"provider": self._fallback.name})
                return result
            except Exception as e:  # noqa: BLE001
                log.error("generate.fallback_failed", extra={"error": str(e)})

        log.error("generate.degraded_mode")
        return ""

    async def classify_injection(self, text: str) -> InjectionVerdict:
        try:
            return await self._primary.classify_injection(text)
        except Exception:  # noqa: BLE001
            if self._fallback is not None:
                return await self._fallback.classify_injection(text)
            # Fail-closed: if guardrail LLM is down, treat as uncertain
            return InjectionVerdict(verdict="uncertain", score=0.5, reason="guardrail_llm_unavailable")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Embeddings only flow through primary (Gemini). No fallback for embeddings.
        return await self._primary.embed(texts)
