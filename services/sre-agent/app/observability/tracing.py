"""Langfuse tracing helpers — typed span factories (v2).

ARCHITECTURE.md §4 defines three layers:
  Layer 1 — infra spans  (per stage)
  Layer 2 — LLM attrs    (per LLM call)
  Layer 3 — agent attrs  (per agent invocation)

All helpers in this module accept only the kwargs listed in the contract table.
No free-form set_attribute calls anywhere else — use these helpers.

Span naming convention: sre.agent.<name>.<phase>
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator, Optional

log = logging.getLogger(__name__)

_langfuse: Optional[Any] = None


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def init_langfuse(
    enabled: bool, public_key: str, secret_key: str, host: str
) -> Optional[Any]:
    """Initialise the Langfuse client. Call once at app startup."""
    global _langfuse
    if not enabled:
        log.info("langfuse.disabled")
        return None
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        log.info("langfuse.connected", extra={"host": host})
        return _langfuse
    except Exception as e:  # noqa: BLE001
        log.warning("langfuse.init_failed", extra={"error": str(e)})
        return None


def get_langfuse() -> Optional[Any]:
    return _langfuse


def verify_langfuse_connection() -> bool:
    """Smoke-test the Langfuse connection by sending a single no-op trace.

    Called once during app startup (after init_langfuse) so the demo operator
    sees a clear SUCCESS / WARNING log instead of a silent first-request failure.

    Returns True when Langfuse is reachable, False otherwise.
    Failure is non-fatal: the app continues with tracing degraded.
    """
    lf = get_langfuse()
    if lf is None:
        log.info("langfuse.verify_skipped", extra={"reason": "langfuse_disabled"})
        return False
    try:
        trace = lf.trace(name="sre.agent.startup.healthcheck", session_id="startup")
        span = trace.span(name="sre.agent.startup.healthcheck", metadata={"ok": True})
        span.end()
        log.info("langfuse.verify_ok")
        return True
    except Exception as e:  # noqa: BLE001
        log.warning(
            "langfuse.verify_failed",
            extra={"error": str(e), "hint": "Check LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY"},
        )
        return False


# ---------------------------------------------------------------------------
# Layer 1 — Infra spans (per stage)
# Span name pattern: sre.agent.<name>.<phase>
# ---------------------------------------------------------------------------

@contextmanager
def span_ingest(
    *,
    incident_id: str,
    has_image: bool,
    has_log: bool,
    text_length: int,
) -> Generator[Any, None, None]:
    """sre.agent.intake_guard.ingest span (Layer 1)."""
    yield from _managed_span(
        name="sre.agent.intake_guard.ingest",
        session_id=incident_id,
        attrs={
            "incident_id": incident_id,
            "has_image": has_image,
            "has_log": has_log,
            "text_length": text_length,
        },
    )


@contextmanager
def span_guardrails(
    *,
    incident_id: str,
    injection_detected: bool,
    score: float,
    blocked_reason: Optional[str] = None,
) -> Generator[Any, None, None]:
    """sre.agent.intake_guard.guardrails span (Layer 1)."""
    attrs: dict[str, Any] = {
        "incident_id": incident_id,
        "injection_detected": injection_detected,
        "score": score,
    }
    if blocked_reason:
        attrs["blocked_reason"] = blocked_reason
    yield from _managed_span(
        name="sre.agent.intake_guard.guardrails",
        session_id=incident_id,
        attrs=attrs,
    )


@contextmanager
def span_triage(
    *,
    incident_id: str,
    context_docs: list[str],
    severity: str,
    # Layer 2 attrs (LLM call)
    llm_cost_usd: float = 0.0,
    llm_prompt_name: str = "",
    llm_prompt_version: str = "",
    llm_tokens_in: int = 0,
    llm_tokens_out: int = 0,
    llm_provider_used: str = "",
    llm_fallback_used: bool = False,
    # Layer 3 attrs (agent)
    agent_iterations: int = 0,
    agent_max_iterations: int = 6,
    agent_rag_queries: int = 0,
    agent_rag_hits: int = 0,
    agent_escalated: bool = False,
    agent_tool_calls: Optional[list[str]] = None,
) -> Generator[Any, None, None]:
    """sre.agent.triage.analysis span (Layers 1 + 2 + 3)."""
    yield from _managed_span(
        name="sre.agent.triage.analysis",
        session_id=incident_id,
        attrs={
            "incident_id": incident_id,
            "context_docs": context_docs,
            "severity": severity,
            # Layer 2
            "llm.cost_usd": llm_cost_usd,
            "llm.prompt_name": llm_prompt_name,
            "llm.prompt_version": llm_prompt_version,
            "llm.tokens_in": llm_tokens_in,
            "llm.tokens_out": llm_tokens_out,
            "llm.provider_used": llm_provider_used,
            "llm.fallback_used": llm_fallback_used,
            # Layer 3
            "agent.name": "triage",
            "agent.iterations": agent_iterations,
            "agent.max_iterations": agent_max_iterations,
            "agent.rag_queries": agent_rag_queries,
            "agent.rag_hits": agent_rag_hits,
            "agent.escalated": agent_escalated,
            "agent.tool_calls": agent_tool_calls or [],
        },
    )


@contextmanager
def span_ticket_create(
    *,
    incident_id: str,
    ticket_id: str,
    ticket_provider: str,
    severity: str,
) -> Generator[Any, None, None]:
    """sre.agent.integration.ticket_create span (Layer 1)."""
    yield from _managed_span(
        name="sre.agent.integration.ticket_create",
        session_id=incident_id,
        attrs={
            "incident_id": incident_id,
            "ticket_id": ticket_id,
            "ticket_provider": ticket_provider,
            "severity": severity,
        },
    )


@contextmanager
def span_notify_team(
    *,
    incident_id: str,
    ticket_id: str,
    notify_provider: str,
    recipients_count: int,
) -> Generator[Any, None, None]:
    """sre.agent.integration.notify_team span (Layer 1)."""
    yield from _managed_span(
        name="sre.agent.integration.notify_team",
        session_id=incident_id,
        attrs={
            "incident_id": incident_id,
            "ticket_id": ticket_id,
            "notify_provider": notify_provider,
            "recipients_count": recipients_count,
        },
    )


@contextmanager
def span_resolve_notify(
    *,
    incident_id: str,
    ticket_id: str,
    reporter_email: str,
) -> Generator[Any, None, None]:
    """sre.agent.resolution.notify_reporter span (Layer 1)."""
    yield from _managed_span(
        name="sre.agent.resolution.notify_reporter",
        session_id=incident_id,
        attrs={
            "incident_id": incident_id,
            "ticket_id": ticket_id,
            "reporter_email": reporter_email,
        },
    )


@contextmanager
def span_resolution_run(
    *,
    incident_id: str,
    ticket_id: str,
) -> Generator[Any, None, None]:
    """sre.agent.resolution.run span — wraps the full resolution subgraph (Layer 1)."""
    yield from _managed_span(
        name="sre.agent.resolution.run",
        session_id=incident_id,
        attrs={
            "incident_id": incident_id,
            "ticket_id": ticket_id,
        },
    )


@contextmanager
def span_resolution_summarize(
    *,
    incident_id: str,
    llm_prompt_name: str = "",
    llm_prompt_version: str = "",
) -> Generator[Any, None, None]:
    """sre.agent.resolution.summarize span — wraps the LLM call (Layer 2).

    Emits llm.prompt_name and llm.prompt_version as required by
    Observability Contract §4.2 for every LLM call.
    """
    yield from _managed_span(
        name="sre.agent.resolution.summarize",
        session_id=incident_id,
        attrs={
            "incident_id": incident_id,
            "llm.prompt_name": llm_prompt_name,
            "llm.prompt_version": llm_prompt_version,
        },
    )


# ---------------------------------------------------------------------------
# Layer 4 — Orchestrator root span (quality signals)
# ---------------------------------------------------------------------------

@contextmanager
def span_orchestrator_root(
    *,
    incident_id: str,
    triage_severity: str = "",
    triage_confidence: str = "",
    triage_quality_score: float = 0.0,
    triage_affected_components: Optional[list[str]] = None,
    case_status_final: str = "",
    case_total_duration_ms: int = 0,
) -> Generator[Any, None, None]:
    """Root span per incident — emits quality signals (§4.4)."""
    yield from _managed_span(
        name="sre.agent.orchestrator.root",
        session_id=incident_id,
        attrs={
            "incident_id": incident_id,
            "triage.severity": triage_severity,
            "triage.confidence": triage_confidence,
            "triage.quality_score": triage_quality_score,
            "triage.affected_components": triage_affected_components or [],
            "case.status_final": case_status_final,
            "case.total_duration_ms": case_total_duration_ms,
        },
    )


# ---------------------------------------------------------------------------
# Internal helper — no-op when Langfuse is disabled
# ---------------------------------------------------------------------------

def _managed_span(
    *, name: str, session_id: str, attrs: dict[str, Any]
) -> Generator[Any, None, None]:
    """Yield a Langfuse span if available, otherwise a no-op context."""
    lf = get_langfuse()
    if lf is None:
        yield None
        return
    span = None
    try:
        trace = lf.trace(name=name, session_id=session_id)
        span = trace.span(name=name, metadata=attrs)
        yield span
    except Exception as e:  # noqa: BLE001
        log.warning("tracing.span_failed", extra={"name": name, "error": str(e)})
        yield None
    finally:
        if span is not None:
            try:
                span.end()
            except Exception:  # noqa: BLE001
                pass
