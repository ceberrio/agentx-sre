"""Tests for app/orchestration/orchestrator/router.py.

AC-01: route_after_intake returns ROUTE_END when status is INTAKE_BLOCKED.
AC-02: route_after_intake returns ROUTE_TRIAGE when status is INTAKE_OK.
AC-03: route_after_triage returns ROUTE_END when state has an error.
AC-04: route_after_triage returns ROUTE_INTEGRATION on success.
AC-05: route_after_integration always returns ROUTE_END.
BR-01: All routing functions are pure (no I/O).
"""
from __future__ import annotations

import pytest

from app.orchestration.orchestrator.router import (
    ROUTE_END,
    ROUTE_INTEGRATION,
    ROUTE_TRIAGE,
    EscalationDecision,
    route_after_intake,
    route_after_integration,
    route_after_triage,
    should_escalate,
)
from app.orchestration.orchestrator.state import CaseStatus


def _make_state(**kwargs) -> dict:
    """Minimal CaseState for routing tests."""
    return {
        "case_id": "test-id",
        "events": [],
        **kwargs,
    }


class TestRouteAfterIntake:
    """AC-01 / AC-02: Intake routing."""

    def test_blocked_routes_to_end(self):
        state = _make_state(status=CaseStatus.INTAKE_BLOCKED)
        assert route_after_intake(state) == ROUTE_END

    def test_intake_ok_routes_to_triage(self):
        state = _make_state(status=CaseStatus.INTAKE_OK)
        assert route_after_intake(state) == ROUTE_TRIAGE

    def test_new_status_routes_to_triage(self):
        """Edge case: unexpected status falls through to triage."""
        state = _make_state(status=CaseStatus.NEW)
        assert route_after_intake(state) == ROUTE_TRIAGE


class TestRouteAfterTriage:
    """AC-03 / AC-04: Triage routing."""

    def test_error_routes_to_end(self):
        state = _make_state(status=CaseStatus.TRIAGED, error="something went wrong")
        assert route_after_triage(state) == ROUTE_END

    def test_failed_status_routes_to_end(self):
        state = _make_state(status=CaseStatus.FAILED)
        assert route_after_triage(state) == ROUTE_END

    def test_triaged_routes_to_integration(self):
        state = _make_state(status=CaseStatus.TRIAGED)
        assert route_after_triage(state) == ROUTE_INTEGRATION

    def test_no_error_key_routes_to_integration(self):
        state = _make_state(status=CaseStatus.TRIAGED)
        # Ensure no error key present
        assert "error" not in state
        assert route_after_triage(state) == ROUTE_INTEGRATION


class TestRouteAfterIntegration:
    """AC-05: Integration routing always ends."""

    def test_always_routes_to_end(self):
        for status in CaseStatus:
            state = _make_state(status=status)
            assert route_after_integration(state) == ROUTE_END


class TestShouldEscalate:
    """BR-01: Sin governance activo, la política de escalación no escala."""

    def test_should_escalate_returns_escalation_decision(self):
        """El retorno es siempre una instancia de EscalationDecision."""
        state = _make_state(status=CaseStatus.TRIAGED)
        decision = should_escalate(state)
        assert isinstance(decision, EscalationDecision)

    def test_should_not_escalate_without_governance(self):
        """Sin bloque 'governance' en el estado, escalate debe ser False."""
        for status in CaseStatus:
            state = _make_state(status=status)
            decision = should_escalate(state)
            assert isinstance(decision, EscalationDecision)
            assert decision.escalate is False
