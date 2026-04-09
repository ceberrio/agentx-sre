"""Router — pure functions that decide the next step from CaseState.

CONTRACT (ARC-014):
- These functions MUST be pure: no I/O, no LLM calls, no adapter access.
- They take CaseState (or a slice of it) and return a string label that
  LangGraph maps to the next node.
- Escalation policy lives here. To change routing behavior, edit this file
  and only this file.
"""
from __future__ import annotations

from dataclasses import dataclass as _dataclass

from app.orchestration.orchestrator.state import CaseState, CaseStatus

# Sentinel labels — keep in sync with edges declared in graph.py
ROUTE_INTAKE = "intake_guard"
ROUTE_TRIAGE = "triage_agent"
ROUTE_INTEGRATION = "integration"
ROUTE_ESCALATED = "escalated"
ROUTE_END = "__end__"


def _is_truthy(value: object) -> bool:
    """Normalize a config value to bool.

    Accepts: bool True/False, strings "true"/"1"/"yes"/"on" (case-insensitive).
    Anything else → False (safe default).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return False


_CONFIDENCE_THRESHOLD_DEFAULT = 0.6


def _resolve_confidence_threshold(gov: dict) -> float:
    """Parse and clamp the confidence threshold from governance config.

    Invalid values or values outside [0.0, 1.0] fall back to the default
    to prevent unintentional mass-escalation from a misconfigured DB row.
    """
    raw = gov.get("confidence_escalation_min", _CONFIDENCE_THRESHOLD_DEFAULT)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return _CONFIDENCE_THRESHOLD_DEFAULT
    if not (0.0 <= value <= 1.0):
        return _CONFIDENCE_THRESHOLD_DEFAULT
    return value


@_dataclass(frozen=True)
class EscalationDecision:
    """Result of the escalation policy evaluation."""

    escalate: bool
    trigger: str = ""  # "kill_switch" | "low_confidence" | "needs_human_review" | ""


def route_after_intake(state: CaseState) -> str:
    """After IntakeGuard: continue to triage or terminate the case."""
    status = state.get("status")
    if status == CaseStatus.INTAKE_BLOCKED:
        return ROUTE_END
    return ROUTE_TRIAGE


def route_after_triage(state: CaseState) -> str:
    """After Triage: proceed to Integration unless triage failed or escalated."""
    if state.get("error"):
        return ROUTE_END
    status = state.get("status")
    if status in (CaseStatus.FAILED, CaseStatus.ESCALATED):
        return ROUTE_END
    return ROUTE_INTEGRATION


def route_after_integration(state: CaseState) -> str:
    """After Integration: terminate the synchronous graph."""
    return ROUTE_END


def should_escalate(state: CaseState) -> EscalationDecision:
    """Escalation policy — pure function, reads governance config from CaseState.

    The API layer preloads governance thresholds into state["governance"] before
    graph.ainvoke() so this function never performs I/O (ARC-014).

    Escalation triggers:
    1. kill_switch_enabled truthy — all incidents escalated.
    2. triage.confidence < confidence_escalation_min — LLM not confident enough.
    3. triage.needs_human_review == True — LLM explicitly flagged for review.
    """
    gov = state.get("governance") or {}

    # Trigger 1: kill switch
    if _is_truthy(gov.get("kill_switch_enabled", False)):
        return EscalationDecision(escalate=True, trigger="kill_switch")

    triage = state.get("triage")
    if triage is None:
        return EscalationDecision(escalate=False)

    # Trigger 2: low confidence
    threshold = _resolve_confidence_threshold(gov)
    if triage.confidence < threshold:
        return EscalationDecision(escalate=True, trigger="low_confidence")

    # Trigger 3: LLM flagged for human review
    if triage.needs_human_review:
        return EscalationDecision(escalate=True, trigger="needs_human_review")

    return EscalationDecision(escalate=False)
