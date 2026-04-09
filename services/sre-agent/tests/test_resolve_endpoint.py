"""Tests for POST /incidents/{id}/resolve endpoint.

TC-U-INC-015: POST /incidents/{id}/resolve retorna 200 y status "resolved"
TC-U-INC-016: POST /incidents/{id}/resolve con incidente inexistente retorna 404

Auth note (HU-P018): These tests override get_current_user_or_api_key AND the
require_role closure to bypass auth cleanly — business logic is the focus here.
Role-based access control for resolve is tested separately in test_dual_auth.py.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.domain.entities import (
    Incident,
    IncidentStatus,
    InjectionVerdict,
    Ticket,
    TicketStatus,
    NotificationReceipt,
    ReporterNotification,
)
from app.domain.entities.user import User, UserRole
from app.domain.ports import IStorageProvider


# ---------------------------------------------------------------------------
# Auth bypass — OPERATOR role (minimum required for resolve)
# ---------------------------------------------------------------------------


def _bypass_auth_as_operator(app: FastAPI) -> None:
    """Override both auth and require_role to inject an operator user."""
    import uuid
    from datetime import datetime, timezone

    _user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        email="operator@sre-agent.internal",
        full_name="Test Operator",
        role=UserRole.OPERATOR,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    async def _no_auth() -> User:
        return _user

    # Override dual-auth dependency
    app.dependency_overrides[deps.get_current_user_or_api_key] = _no_auth

    # Override require_role factory: the resolve route uses
    # require_role(OPERATOR, FLOW_CONFIGURATOR, ADMIN, SUPERADMIN).
    # We patch require_role at module level so the closure returns _user directly.
    original_require_role = deps.require_role

    def _mock_require_role(*roles):
        async def _check() -> User:
            return _user
        return _check

    deps.require_role = _mock_require_role
    # Store restore function on app so tests can clean up if needed
    app._restore_require_role = lambda: setattr(deps, "require_role", original_require_role)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_incident(incident_id: str = "incident-resolve-001") -> Incident:
    return Incident(
        id=incident_id,
        reporter_email="reporter@company.com",
        title="DB crash-loop",
        description="PostgreSQL pod in CrashLoopBackOff",
    )


def _make_container(incident: Incident | None = None):
    """Build a minimal container double for resolve endpoint tests.

    Pattern mirrors test_webhooks_and_feedback.py — MagicMock(spec=IStorageProvider)
    backed by an in-memory dict to enforce the hexagonal boundary.
    """
    _store: dict[str, Incident] = {}

    async def _save_incident(inc: Incident) -> None:
        _store[inc.id] = inc

    async def _get_incident(incident_id: str):
        return _store.get(incident_id)

    async def _update_incident(incident_id: str, patch: dict):
        if incident_id in _store:
            return _store[incident_id]
        return None

    storage = MagicMock(spec=IStorageProvider)
    storage.save_incident = AsyncMock(side_effect=_save_incident)
    storage.get_incident = AsyncMock(side_effect=_get_incident)
    storage.update_incident = AsyncMock(side_effect=_update_incident)

    # Pre-load incident if provided
    if incident is not None:
        asyncio.run(_save_incident(incident))

    mock_ticket = MagicMock()
    mock_ticket.name = "mock"
    mock_ticket.resolve_ticket = AsyncMock(
        return_value=Ticket(
            id="ticket-resolve-001",
            incident_id=incident.id if incident else "unknown",
            provider="mock",
            status=TicketStatus.RESOLVED,
        )
    )

    mock_notify = MagicMock()
    mock_notify.name = "mock"
    mock_notify.notify_reporter = AsyncMock(
        return_value=NotificationReceipt(delivered=True, provider="mock", channel="reporter")
    )

    mock_llm = MagicMock()
    mock_llm.name = "mock_llm"
    mock_llm.classify_injection = AsyncMock(
        return_value=InjectionVerdict(verdict="no", score=0.0)
    )
    mock_llm.generate = AsyncMock(return_value="Resolution summary generated.")

    mock_context = MagicMock()
    mock_context.name = "mock_context"
    mock_context.search_context = AsyncMock(return_value=[])

    return SimpleNamespace(
        storage=storage,
        llm=mock_llm,
        ticket=mock_ticket,
        notify=mock_notify,
        context=mock_context,
    )


# ---------------------------------------------------------------------------
# TC-U-INC-015: POST /incidents/{id}/resolve — successful resolution
# ---------------------------------------------------------------------------


def test_resolve_existing_incident_returns_200():
    """TC-U-INC-015: POST /incidents/{id}/resolve with valid incident returns 200.

    Acceptance criteria:
    - HTTP 200
    - Response body contains incident_id
    - Response body contains status="resolved"
    """
    incident = _make_incident("incident-resolve-ok")
    container = _make_container(incident)

    from app.api.routes_incidents import router as incidents_router
    from app.orchestration.orchestrator.graph import build_resolution_graph

    app = FastAPI()
    app.include_router(incidents_router)
    _bypass_auth_as_operator(app)

    # Mock the resolution graph — we test the HTTP layer, not the graph
    mock_graph = MagicMock()
    from app.orchestration.orchestrator.state import CaseStatus
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "status": CaseStatus.RESOLVED,
            "events": [],
        }
    )

    client = TestClient(app, raise_server_exceptions=False)
    with (
        __import__("unittest.mock", fromlist=["patch"]).patch(
            "app.api.routes_incidents.get_container", return_value=container
        ),
        __import__("unittest.mock", fromlist=["patch"]).patch(
            "app.api.routes_incidents.build_resolution_graph", return_value=mock_graph
        ),
    ):
        response = client.post("/incidents/incident-resolve-ok/resolve")

    try:
        app._restore_require_role()
    except AttributeError:
        pass

    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. Body: {response.text}"
    )
    body = response.json()
    assert body["incident_id"] == "incident-resolve-ok", (
        f"incident_id mismatch: {body}"
    )
    assert body["status"] == "resolved", (
        f"status mismatch — expected 'resolved', got: {body.get('status')}"
    )


# ---------------------------------------------------------------------------
# TC-U-INC-016: POST /incidents/{id}/resolve — non-existent incident returns 404
# ---------------------------------------------------------------------------


def test_resolve_nonexistent_incident_returns_404():
    """TC-U-INC-016: POST /incidents/{id}/resolve with unknown ID returns 404.

    Acceptance criteria:
    - HTTP 404
    - Response body detail = "incident_not_found"
    """
    # Container with no pre-loaded incidents (empty store)
    container = _make_container(incident=None)

    from app.api.routes_incidents import router as incidents_router

    app = FastAPI()
    app.include_router(incidents_router)
    _bypass_auth_as_operator(app)

    client = TestClient(app, raise_server_exceptions=False)
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.api.routes_incidents.get_container", return_value=container
    ):
        response = client.post("/incidents/does-not-exist-99999/resolve")

    try:
        app._restore_require_role()
    except AttributeError:
        pass

    assert response.status_code == 404, (
        f"Expected 404, got {response.status_code}. Body: {response.text}"
    )
    assert response.json()["detail"] == "incident_not_found", (
        f"detail mismatch: {response.json()}"
    )
