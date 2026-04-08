"""IntakeGuard Agent — first line of defense.

Responsibilities (5-layer prompt-injection defense, ARCHITECTURE.md §5):
    1. Sanitize input (control chars, zero-width Unicode)
    2. Size cap enforcement
    3. Static heuristic prompt-injection detection
    4. LLM judge (only if 1-3 are inconclusive)
    5. Final allow/block decision

Emits exactly ONE AgentEvent:
    - "intake.passed"  (status -> INTAKE_OK)
    - "intake.blocked" (status -> INTAKE_BLOCKED, payload contains reason)

Observability: emits sre.agent.intake_guard.guardrails span per ARCHITECTURE.md §4.1.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.infrastructure.container import Container
from app.observability import tracing
from app.observability.metrics import incidents_blocked_total
from app.orchestration.agents.intake_guard.state import IntakeGuardState
from app.orchestration.agents.intake_guard.tools import (
    apply_pii_layer,
    detect_injection_markers,
    is_off_topic,
)
from app.security.input_sanitizer import sanitize
from app.orchestration.shared.base_agent import BaseAgent

log = logging.getLogger(__name__)

# Max text size after sanitization (Layer 2)
MAX_TEXT_BYTES = 10_000


class IntakeGuardAgent(BaseAgent):
    name = "intake_guard"

    def __init__(self, container, *, llm_judge_enabled: bool = True) -> None:
        super().__init__(container)
        self._llm_judge_enabled = llm_judge_enabled

    def build(self):
        g = StateGraph(IntakeGuardState)
        g.add_node("deterministic_checks", self._deterministic_checks)
        g.add_node("llm_judge", self._llm_judge)
        g.add_node("decide", self._decide)

        g.set_entry_point("deterministic_checks")
        g.add_conditional_edges(
            "deterministic_checks",
            self._needs_llm_judge,
            {"yes": "llm_judge", "no": "decide"},
        )
        g.add_edge("llm_judge", "decide")
        g.add_edge("decide", END)
        return g.compile()

    # ----- nodes -----

    async def _deterministic_checks(self, state: IntakeGuardState) -> IntakeGuardState:
        """Run layers 1-3: sanitize, size cap, heuristic injection detection."""
        proj = state["projection"]
        incident = proj.incident

        # Layer 1: Sanitize
        clean_title = sanitize(incident.title)
        clean_desc = sanitize(incident.description)
        combined = f"{clean_title} {clean_desc}"

        # Layer 2: Size cap
        if len(combined.encode("utf-8")) > MAX_TEXT_BYTES:
            state["blocked"] = True
            state["blocked_reason"] = "text_too_large"
            log.warning(
                "intake_guard.text_too_large",
                extra={"incident_id": incident.id, "len": len(combined)},
            )
            return state

        # Layer 1b: PII layer — redact emails/phones/SSNs/cards; hard-block credentials.
        # Emails and standard PII are redacted (not blocked) so legitimate SRE incidents
        # that happen to contain an email address are not rejected. Actual credentials
        # (AWS keys, GitHub tokens, Bearer tokens, PEM blocks) are hard-blocked because
        # they must never reach the LLM (SEC-MJ-005).
        redacted_combined, credential_tags = apply_pii_layer(combined)
        if credential_tags:
            state["blocked"] = True
            state["blocked_reason"] = f"credential_detected:{','.join(credential_tags)}"
            log.warning(
                "intake_guard.credential_detected",
                extra={"incident_id": incident.id, "tags": credential_tags},
            )
            incidents_blocked_total.labels(layer="heuristic").inc()
            return state

        # Replace combined with the redacted version so downstream layers
        # (injection detection, LLM judge) never see raw PII.
        combined = redacted_combined

        # Layer 2: Heuristic injection
        if detect_injection_markers(combined):
            state["blocked"] = True
            state["blocked_reason"] = "heuristic_injection_detected"
            log.warning(
                "intake_guard.heuristic_injection",
                extra={"incident_id": incident.id},
            )
            incidents_blocked_total.labels(layer="heuristic").inc()
            return state

        # Layer 3: Off-topic heuristic — borderline cases escalate to LLM judge.
        # Do NOT hard-block here; mark as uncertain so Layer 4 decides.
        if is_off_topic(incident):
            state["blocked"] = False
            state["blocked_reason"] = "potential_off_topic"
            log.info(
                "intake_guard.off_topic_heuristic",
                extra={"incident_id": incident.id},
            )

        return state

    def _needs_llm_judge(self, state: IntakeGuardState) -> str:
        """Route to LLM judge unless a deterministic layer already hard-blocked.

        Hard-blocked means blocked=True with a definitive reason (PII, injection,
        size cap). Uncertain cases (e.g. potential_off_topic) always go to the judge.
        """
        if state.get("blocked"):
            return "no"
        return "yes" if self._llm_judge_enabled else "no"

    async def _llm_judge(self, state: IntakeGuardState) -> IntakeGuardState:
        """Layer 4: LLM-based judge for ambiguous content."""
        proj = state["projection"]
        incident = proj.incident
        # Use redacted text — PII was already stripped in _deterministic_checks.
        from app.security.input_sanitizer import redact_pii
        combined = redact_pii(f"{incident.title}\n{incident.description}")

        try:
            verdict = await self.container.llm.classify_injection(combined)
            state["injection_score"] = verdict.score  # type: ignore[typeddict-unknown-key]

            if verdict.verdict == "yes":
                state["blocked"] = True
                state["blocked_reason"] = f"llm_judge:{verdict.reason or 'injection_detected'}"
                incidents_blocked_total.labels(layer="llm_judge").inc()
                log.info(
                    "intake_guard.llm_judge_blocked",
                    extra={
                        "incident_id": incident.id,
                        "score": verdict.score,
                        "reason": verdict.reason,
                    },
                )
            elif verdict.verdict == "uncertain":
                # Uncertain: allow but flag for human review
                state["blocked"] = False
                state["needs_human_review"] = True  # type: ignore[typeddict-unknown-key]
                log.info(
                    "intake_guard.llm_judge_uncertain",
                    extra={"incident_id": incident.id, "score": verdict.score},
                )
            else:
                state["blocked"] = False
                log.info(
                    "intake_guard.llm_judge_safe",
                    extra={"incident_id": incident.id, "score": verdict.score},
                )
        except Exception as exc:  # noqa: BLE001
            # Fail-closed on LLM judge error: block the incident to prevent
            # an attacker from triggering exceptions to bypass Layer 4 (SEC-CR-003).
            log.warning(
                "intake_guard.llm_judge_failed",
                extra={"incident_id": incident.id, "error": str(exc)},
            )
            state["blocked"] = True
            state["blocked_reason"] = "llm_judge_unavailable"
            incidents_blocked_total.labels(layer="llm_judge").inc()

        return state

    async def _decide(self, state: IntakeGuardState) -> IntakeGuardState:
        """Layer 5: emit final AgentEvent based on accumulated signals."""
        proj = state["projection"]
        incident = proj.incident

        blocked = state.get("blocked", False)
        reason = state.get("blocked_reason", "unknown")

        injection_score = state.get("injection_score", 0.0)  # type: ignore[misc]

        with tracing.span_guardrails(
            incident_id=incident.id,
            injection_detected=blocked,
            score=float(injection_score) if injection_score else 0.0,
            blocked_reason=reason if blocked else None,
        ):
            if blocked:
                state["final_event"] = self.emit(
                    "intake.blocked",
                    payload={"reason": reason, "score": injection_score},
                )
                log.info(
                    "guardrails.blocked",
                    extra={"incident_id": incident.id, "reason": reason},
                )
            else:
                state["final_event"] = self.emit(
                    "intake.passed",
                    payload={"score": injection_score},
                )
                log.info(
                    "guardrails.evaluated",
                    extra={"incident_id": incident.id, "blocked": False},
                )

        return state


def build_intake_guard_agent(container: Container):
    """Public factory used by the orchestrator graph."""
    from app.infrastructure.config import settings
    return IntakeGuardAgent(
        container,
        llm_judge_enabled=settings.guardrails_llm_judge_enabled,
    ).build()
