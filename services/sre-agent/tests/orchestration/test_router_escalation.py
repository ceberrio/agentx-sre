"""Tests de escalacion por governance — router.py y routes_incidents.py.

Cubre las funciones puras de decision de escalacion y el mapeo
de estado de LangGraph a patch de base de datos.

Modulos bajo prueba:
  - app.orchestration.orchestrator.router._is_truthy
  - app.orchestration.orchestrator.router._resolve_confidence_threshold
  - app.orchestration.orchestrator.router.should_escalate
  - app.orchestration.orchestrator.router.route_after_triage
  - app.api.routes_incidents._build_post_graph_patch
"""
from __future__ import annotations

import pytest

from app.orchestration.orchestrator.router import (
    ROUTE_END,
    ROUTE_INTEGRATION,
    EscalationDecision,
    _is_truthy,
    _resolve_confidence_threshold,
    route_after_triage,
    should_escalate,
)
from app.orchestration.orchestrator.state import CaseStatus
from app.api.routes_incidents import _build_post_graph_patch
from app.domain.entities import Severity, TriageResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_triage(
    confidence: float = 0.9,
    needs_human_review: bool = False,
) -> TriageResult:
    """Construye un TriageResult minimo valido para las pruebas."""
    return TriageResult(
        severity=Severity.P2,
        summary="Resumen de prueba",
        suspected_root_cause="Causa raiz de prueba",
        confidence=confidence,
        needs_human_review=needs_human_review,
    )


def _make_state(**kwargs) -> dict:
    """CaseState minimo para pruebas de routing."""
    return {"case_id": "test-case-001", "events": [], **kwargs}


# ---------------------------------------------------------------------------
# _is_truthy()
# ---------------------------------------------------------------------------

class TestIsTruthy:
    """Normalizacion de valores de configuracion a bool."""

    def test_bool_true(self):
        assert _is_truthy(True) is True

    def test_bool_false(self):
        assert _is_truthy(False) is False

    def test_string_true_lowercase(self):
        assert _is_truthy("true") is True

    def test_string_true_titlecase(self):
        assert _is_truthy("True") is True

    def test_string_true_uppercase(self):
        assert _is_truthy("TRUE") is True

    def test_string_one(self):
        assert _is_truthy("1") is True

    def test_string_yes(self):
        assert _is_truthy("yes") is True

    def test_string_on(self):
        assert _is_truthy("on") is True

    def test_string_false(self):
        assert _is_truthy("false") is False

    def test_string_zero(self):
        assert _is_truthy("0") is False

    def test_string_empty(self):
        assert _is_truthy("") is False

    def test_int_one(self):
        # Enteros que no sean bool devuelven False (safe default)
        assert _is_truthy(1) is False

    def test_none(self):
        assert _is_truthy(None) is False

    def test_list(self):
        assert _is_truthy([True]) is False


# ---------------------------------------------------------------------------
# _resolve_confidence_threshold()
# ---------------------------------------------------------------------------

class TestResolveConfidenceThreshold:
    """Parseo y clamping del umbral de confianza desde governance config."""

    def test_empty_dict_returns_default(self):
        assert _resolve_confidence_threshold({}) == pytest.approx(0.6)

    def test_valid_float_0_8(self):
        assert _resolve_confidence_threshold({"confidence_escalation_min": 0.8}) == pytest.approx(0.8)

    def test_boundary_zero(self):
        assert _resolve_confidence_threshold({"confidence_escalation_min": 0.0}) == pytest.approx(0.0)

    def test_boundary_one(self):
        assert _resolve_confidence_threshold({"confidence_escalation_min": 1.0}) == pytest.approx(1.0)

    def test_above_range_returns_default(self):
        assert _resolve_confidence_threshold({"confidence_escalation_min": 1.01}) == pytest.approx(0.6)

    def test_below_range_returns_default(self):
        assert _resolve_confidence_threshold({"confidence_escalation_min": -0.01}) == pytest.approx(0.6)

    def test_non_numeric_string_returns_default(self):
        assert _resolve_confidence_threshold({"confidence_escalation_min": "alto"}) == pytest.approx(0.6)

    def test_none_explicit_returns_default(self):
        assert _resolve_confidence_threshold({"confidence_escalation_min": None}) == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# should_escalate()
# ---------------------------------------------------------------------------

class TestShouldEscalate:
    """Politica de escalacion — funcion pura."""

    # --- Kill switch ---

    def test_kill_switch_bool_true_escalates(self):
        state = _make_state(governance={"kill_switch_enabled": True})
        result = should_escalate(state)
        assert result.escalate is True
        assert result.trigger == "kill_switch"

    def test_kill_switch_string_true_escalates(self):
        state = _make_state(governance={"kill_switch_enabled": "true"})
        result = should_escalate(state)
        assert result.escalate is True
        assert result.trigger == "kill_switch"

    def test_kill_switch_false_high_confidence_no_review_no_escalation(self):
        state = _make_state(
            governance={"kill_switch_enabled": False},
            triage=_make_triage(confidence=0.95, needs_human_review=False),
        )
        result = should_escalate(state)
        assert result.escalate is False
        assert result.trigger == ""

    def test_kill_switch_false_low_confidence_triggers_low_confidence(self):
        """Confianza 0.59 < 0.6 (default) debe escalar con trigger low_confidence."""
        state = _make_state(
            governance={"kill_switch_enabled": False},
            triage=_make_triage(confidence=0.59),
        )
        result = should_escalate(state)
        assert result.escalate is True
        assert result.trigger == "low_confidence"

    def test_kill_switch_false_confidence_exactly_threshold_no_escalation(self):
        """Confianza exactamente igual al umbral (0.6) NO debe escalar — borde inferior incluido."""
        state = _make_state(
            governance={"kill_switch_enabled": False},
            triage=_make_triage(confidence=0.6),
        )
        result = should_escalate(state)
        assert result.escalate is False

    def test_kill_switch_false_high_confidence_needs_human_review(self):
        """LLM flag needs_human_review=True debe escalar aunque la confianza sea alta."""
        state = _make_state(
            governance={"kill_switch_enabled": False},
            triage=_make_triage(confidence=0.9, needs_human_review=True),
        )
        result = should_escalate(state)
        assert result.escalate is True
        assert result.trigger == "needs_human_review"

    def test_kill_switch_true_ignores_triage_none(self):
        """Kill switch activo no requiere triage; funciona con triage=None."""
        state = _make_state(governance={"kill_switch_enabled": True}, triage=None)
        result = should_escalate(state)
        assert result.escalate is True
        assert result.trigger == "kill_switch"

    def test_governance_none_returns_no_escalation(self):
        """governance=None debe caer a {} y no escalar (kill switch off por defecto)."""
        state = _make_state(governance=None, triage=_make_triage(confidence=0.9))
        result = should_escalate(state)
        assert result.escalate is False

    def test_trigger_precedence_kill_switch_over_low_confidence(self):
        """kill_switch debe preceder a low_confidence."""
        state = _make_state(
            governance={"kill_switch_enabled": True, "confidence_escalation_min": 0.99},
            triage=_make_triage(confidence=0.1),  # tambien dispara low_confidence
        )
        result = should_escalate(state)
        assert result.trigger == "kill_switch"

    def test_trigger_precedence_low_confidence_over_needs_human_review(self):
        """low_confidence debe preceder a needs_human_review."""
        state = _make_state(
            governance={"kill_switch_enabled": False},
            triage=_make_triage(confidence=0.1, needs_human_review=True),
        )
        result = should_escalate(state)
        assert result.trigger == "low_confidence"


# ---------------------------------------------------------------------------
# route_after_triage()
# ---------------------------------------------------------------------------

class TestRouteAfterTriage:
    """Routing post-triage basado en status y presencia de error."""

    def test_escalated_routes_to_end(self):
        state = _make_state(status=CaseStatus.ESCALATED)
        assert route_after_triage(state) == ROUTE_END

    def test_failed_routes_to_end(self):
        state = _make_state(status=CaseStatus.FAILED)
        assert route_after_triage(state) == ROUTE_END

    def test_triaged_no_error_routes_to_integration(self):
        state = _make_state(status=CaseStatus.TRIAGED)
        assert route_after_triage(state) == ROUTE_INTEGRATION

    def test_error_present_routes_to_end(self):
        state = _make_state(status=CaseStatus.TRIAGED, error="fallo inesperado")
        assert route_after_triage(state) == ROUTE_END


# ---------------------------------------------------------------------------
# _build_post_graph_patch()  — incluyendo GAP-005
# ---------------------------------------------------------------------------

class TestBuildPostGraphPatch:
    """Mapeo de estado final de LangGraph a patch de base de datos (ARC-023)."""

    def test_escalated_enum_sets_blocked_true_and_blocked_reason(self):
        """Estado ESCALATED con enum debe establecer blocked=True y blocked_reason."""
        final_state = {
            "status": CaseStatus.ESCALATED,
            "triage": None,
            "ticket": None,
        }
        patch = _build_post_graph_patch(final_state)
        assert patch["status"] == "blocked"
        assert patch.get("blocked") is True
        assert "blocked_reason" in patch
        assert patch["blocked_reason"]  # no debe ser vacio/None

    def test_escalated_enum_custom_blocked_reason(self):
        """blocked_reason del estado debe propagarse al patch."""
        final_state = {
            "status": CaseStatus.ESCALATED,
            "blocked_reason": "kill_switch_activo",
            "triage": None,
            "ticket": None,
        }
        patch = _build_post_graph_patch(final_state)
        assert patch["blocked_reason"] == "kill_switch_activo"

    def test_escalated_string_gap005(self):
        """GAP-005: LangGraph puede devolver status como string raw 'escalated'.

        Se verifica si _build_post_graph_patch aplica blocked=True en ese caso.
        Si NO aplica, se documenta como bug confirmado.
        """
        final_state = {
            "status": "escalated",  # string, no enum
            "triage": None,
            "ticket": None,
        }
        patch = _build_post_graph_patch(final_state)

        # El status mapeado DEBE ser "blocked" (lookup en _CASE_TO_INCIDENT_STATUS)
        assert patch["status"] == "blocked", (
            "GAP-005: El status mapeado es incorrecto para string 'escalated'"
        )

        # GAP-005: la comparacion `final_status_enum == CaseStatus.ESCALATED`
        # falla cuando status es un string crudo porque str != CaseStatus enum.
        # Si el patch NO tiene blocked=True aqui, el bug esta confirmado.
        gap005_bug_present = patch.get("blocked") is not True
        if gap005_bug_present:
            pytest.fail(
                "BUG GAP-005 CONFIRMADO: Cuando LangGraph retorna status como string "
                "'escalated' (no enum), _build_post_graph_patch NO establece "
                "blocked=True en el patch. La comparacion `final_status_enum == "
                "CaseStatus.ESCALATED` falla silenciosamente con un string raw. "
                "El incidente queda en DB sin blocked=True aunque fue escalado."
            )

    def test_intake_blocked_sets_blocked_true(self):
        """Estado INTAKE_BLOCKED debe establecer blocked=True."""
        final_state = {
            "status": CaseStatus.INTAKE_BLOCKED,
            "blocked_reason": "contenido_sospechoso",
            "triage": None,
            "ticket": None,
        }
        patch = _build_post_graph_patch(final_state)
        assert patch.get("blocked") is True
        assert patch["blocked_reason"] == "contenido_sospechoso"

    def test_triaged_does_not_set_blocked(self):
        """Estado TRIAGED NO debe incluir blocked en el patch."""
        final_state = {
            "status": CaseStatus.TRIAGED,
            "triage": _make_triage(confidence=0.85),
            "ticket": None,
        }
        patch = _build_post_graph_patch(final_state)
        assert "blocked" not in patch
        assert patch["status"] == "triaging"

    def test_triaged_includes_triage_fields(self):
        """Estado TRIAGED con triage presente debe incluir campos de triage en el patch."""
        triage = _make_triage(confidence=0.85, needs_human_review=False)
        final_state = {
            "status": CaseStatus.TRIAGED,
            "triage": triage,
            "ticket": None,
        }
        patch = _build_post_graph_patch(final_state)
        assert patch["triage_confidence"] == pytest.approx(0.85)
        assert patch["severity"] == Severity.P2.value
        assert "triage_summary" in patch
        assert "triage_root_cause" in patch
