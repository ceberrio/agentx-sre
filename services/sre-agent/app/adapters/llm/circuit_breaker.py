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
from app.observability.metrics import llm_fallback_activations_total

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
        self._lock = asyncio.Lock()

    # ----- reconfiguration (HU-P029) -----

    def reconfigure(self, threshold: int, cooldown_s: int) -> None:
        """Update circuit-breaker parameters without replacing the adapter.

        Called atomically by container.reconfigure_circuit_breaker() under the
        hot-reload lock. Resets failure state so the next call uses the new
        parameters from a clean slate.
        """
        self._threshold = threshold
        self._cooldown_s = cooldown_s
        self._consecutive_failures = 0
        self._opened_at = None
        log.info(
            "circuit_breaker.reconfigured",
            extra={"threshold": threshold, "cooldown_s": cooldown_s},
        )

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

    async def _record_success(self) -> None:
        async with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    async def _record_failure(self) -> None:
        async with self._lock:
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
                await self._record_success()
                return result
            except Exception as e:  # noqa: BLE001
                log.warning("triage.primary_failed", extra={"error": str(e)})
                await self._record_failure()

        if self._fallback is not None:
            try:
                result = await asyncio.wait_for(
                    self._fallback.triage(prompt), timeout=self._timeout_s
                )
                result.used_fallback = True
                llm_fallback_activations_total.labels(
                    from_provider=self._primary.name,
                    to_provider=self._fallback.name,
                ).inc()
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
                await self._record_success()
                return result
            except Exception as e:  # noqa: BLE001
                log.warning("generate.primary_failed", extra={"error": str(e)})
                await self._record_failure()

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
        except Exception as e:  # noqa: BLE001
            log.warning("classify_injection.primary_failed", extra={"error": str(e)})

        if self._fallback is not None:
            try:
                return await self._fallback.classify_injection(text)
            except Exception as e:  # noqa: BLE001
                log.error("classify_injection.fallback_failed", extra={"error": str(e)})

        # Fail-closed: if guardrail LLM is down, treat as uncertain
        log.error("classify_injection.degraded_mode")
        return InjectionVerdict(verdict="uncertain", score=0.5, reason="guardrail_llm_unavailable")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Embeddings only flow through primary (Gemini). No fallback for embeddings.
        return await self._primary.embed(texts)
