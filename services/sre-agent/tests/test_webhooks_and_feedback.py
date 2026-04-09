"""Tests for FASE 4: routes_webhooks.py and routes_feedback.py.

AC-01: POST /webhooks/resolution returns 202 Accepted for valid payload.
AC-02: POST /webhooks/resolution rejects payloads missing required fields (422).
AC-03: POST /incidents/{id}/feedback persists rating for a known incident.
AC-04: POST /incidents/{id}/feedback returns 404 for unknown incident_id.
AC-05: POST /incidents/{id}/feedback accepts positive and negative ratings.
BR-01: Resolution webhook triggers background task without blocking HTTP response.
BR-02: Feedback endpoint never logs the comment content (PII boundary).
BR-03: Empty incident_id or ticket_id in webhook payload returns 422.

Note (HU-P018): Routes now enforce auth per-route. Tests focused on business logic
override get_current_user_or_api_key to bypass auth. Auth behavior is tested
separately in test_dual_auth.py.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.domain.entities import (
    Incident,
    IncidentStatus,
    InjectionVerdict,
    Severity,
    Ticket,
    TicketStatus,
    TriageResult,
    NotificationReceipt,
    TeamNotification,
    ReporterNotification,
)
from app.domain.entities.user import User, UserRole
from app.domain.ports import IStorageProvider


# ---------------------------------------------------------------------------
# Auth bypass helper (HU-P018)
# ---------------------------------------------------------------------------


def _bypass_auth(app: FastAPI) -> None:
    """Override get_current_user_or_api_key to bypass auth in business-logic tests."""
    import uuid
    from datetime import datetime, timezone

    _user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email="system@sre-agent.internal",
        full_name="System (Test Override)",
        role=UserRole.SUPERADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    async def _no_auth() -> User:
        return _user

    app.dependency_overrides[deps.get_current_user_or_api_key] = _no_auth


# ---------------------------------------------------------------------------
# Helpers — build a minimal test app
# ---------------------------------------------------------------------------


def _make_incident(incident_id: str = "incident-123") -> Incident:
    return Incident(
        id=incident_id,
        reporter_email="reporter@shop.com",
        title="DB down",
        description="PostgreSQL pod crash-looping",
    )


def _make_container(incident: Incident | None = None):
    """Build a container double with a MagicMock storage backed by an in-memory dict.

    Uses MagicMock(spec=IStorageProvider) to respect the hexagonal boundary —
    no concrete adapter is imported (MJ-004). Uses asyncio.run() instead of
    the deprecated asyncio.get_event_loop().run_until_complete() (MJ-002).
    Uses SimpleNamespace instead of a class-with-mutation pattern (MN-006).
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

    if incident is not None:
        asyncio.run(_save_incident(incident))

    mock_ticket = MagicMock()
    mock_ticket.name = "mock"
    mock_ticket.resolve_ticket = AsyncMock(return_value=Ticket(
        id="ticket-001",
        incident_id=incident.id if incident else "incident-123",
        provider="mock",
        status=TicketStatus.RESOLVED,
    ))

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
# AC-01: POST /webhooks/resolution returns 202 Accepted for valid payload
# ---------------------------------------------------------------------------


def test_resolution_webhook_returns_202():
    """AC-01: Valid resolution webhook payload returns 202 Accepted."""
    incident = _make_incident("incident-001")
    container = _make_container(incident)

    from app.api.routes_webhooks import router as webhooks_router
    app = FastAPI()
    app.include_router(webhooks_router)
    _bypass_auth(app)

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value={"status": "resolved", "events": []})

    client = TestClient(app, raise_server_exceptions=False)
    with patch("app.api.routes_webhooks.get_container", return_value=container), \
         patch("app.api.routes_webhooks._get_resolution_graph", return_value=mock_graph):
        response = client.post(
            "/webhooks/resolution",
            json={
                "incident_id": "incident-001",
                "ticket_id": "ticket-abc",
                "ticket_url": "http://mock/tickets/ticket-abc",
            },
        )

    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] is True
    assert body["incident_id"] == "incident-001"
    assert body["ticket_id"] == "ticket-abc"


# ---------------------------------------------------------------------------
# AC-02: Missing required fields returns 422
# ---------------------------------------------------------------------------


def test_resolution_webhook_missing_ticket_id_returns_422():
    """AC-02: Missing ticket_id in webhook payload yields 422 Unprocessable Entity."""
    from app.api.routes_webhooks import router as webhooks_router
    app = FastAPI()
    app.include_router(webhooks_router)
    _bypass_auth(app)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/webhooks/resolution",
        json={"incident_id": "incident-123"},  # ticket_id missing
    )
    assert response.status_code == 422


def test_resolution_webhook_missing_incident_id_returns_422():
    """AC-02: Missing incident_id in webhook payload yields 422."""
    from app.api.routes_webhooks import router as webhooks_router
    app = FastAPI()
    app.include_router(webhooks_router)
    _bypass_auth(app)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/webhooks/resolution",
        json={"ticket_id": "ticket-001"},  # incident_id missing
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC-03: POST /incidents/{id}/feedback persists rating for a known incident
# ---------------------------------------------------------------------------


def test_feedback_positive_rating_for_known_incident():
    """AC-03: Positive rating is accepted and persisted for an existing incident."""
    incident = _make_incident("incident-feedback-01")
    container = _make_container(incident)

    from app.api.routes_feedback import router as feedback_router
    app = FastAPI()
    app.include_router(feedback_router)
    _bypass_auth(app)

    client = TestClient(app)
    with patch("app.api.routes_feedback.get_container", return_value=container):
        response = client.post(
            "/incidents/incident-feedback-01/feedback",
            json={"rating": "positive", "comment": "Great triage!"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == "incident-feedback-01"
    assert body["rating"] == "positive"
    assert body["persisted"] is True


# ---------------------------------------------------------------------------
# AC-04: POST /incidents/{id}/feedback returns 404 for unknown incident
# ---------------------------------------------------------------------------


def test_feedback_unknown_incident_returns_404():
    """AC-04: Feedback for a non-existent incident returns 404."""
    container = _make_container(incident=None)

    from app.api.routes_feedback import router as feedback_router
    app = FastAPI()
    app.include_router(feedback_router)
    _bypass_auth(app)

    client = TestClient(app)
    with patch("app.api.routes_feedback.get_container", return_value=container):
        response = client.post(
            "/incidents/does-not-exist/feedback",
            json={"rating": "negative"},
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "incident_not_found"


# ---------------------------------------------------------------------------
# AC-05: Feedback accepts both positive and negative ratings
# ---------------------------------------------------------------------------


def test_feedback_negative_rating_accepted():
    """AC-05: Negative rating is accepted for a known incident."""
    incident = _make_incident("incident-neg-01")
    container = _make_container(incident)

    from app.api.routes_feedback import router as feedback_router
    app = FastAPI()
    app.include_router(feedback_router)
    _bypass_auth(app)

    client = TestClient(app)
    with patch("app.api.routes_feedback.get_container", return_value=container):
        response = client.post(
            "/incidents/incident-neg-01/feedback",
            json={"rating": "negative"},
        )
    assert response.status_code == 200
    assert response.json()["rating"] == "negative"


def test_feedback_invalid_rating_rejected():
    """AC-05: An invalid rating value (not positive/negative) yields 422."""
    from app.api.routes_feedback import router as feedback_router
    app = FastAPI()
    app.include_router(feedback_router)
    _bypass_auth(app)

    client = TestClient(app)
    response = client.post(
        "/incidents/incident-inv-01/feedback",
        json={"rating": "meh"},  # Invalid literal
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# BR-01: Resolution webhook triggers background task (non-blocking response)
# ---------------------------------------------------------------------------


def test_resolution_webhook_is_non_blocking():
    """BR-01: The resolution webhook returns immediately without awaiting the graph."""
    incident = _make_incident("incident-nb-01")
    container = _make_container(incident)

    from app.api.routes_webhooks import router as webhooks_router
    app = FastAPI()
    app.include_router(webhooks_router)
    _bypass_auth(app)

    async def _slow_graph(*args, **kwargs):
        await asyncio.sleep(0)  # yield once — TestClient should still return quickly
        return {"status": "resolved", "events": []}

    slow_graph = MagicMock()
    slow_graph.ainvoke = _slow_graph

    client = TestClient(app, raise_server_exceptions=False)
    with patch("app.api.routes_webhooks.get_container", return_value=container), \
         patch("app.api.routes_webhooks._get_resolution_graph", return_value=slow_graph):
        response = client.post(
            "/webhooks/resolution",
            json={"incident_id": "incident-nb-01", "ticket_id": "tkt-slow"},
        )

    # Response must be 202 regardless of graph speed.
    assert response.status_code == 202


# ---------------------------------------------------------------------------
# BR-02: Feedback endpoint never logs the comment content (PII boundary)
# ---------------------------------------------------------------------------


def test_feedback_comment_content_is_not_logged(caplog):
    """BR-02: The comment field MUST NOT appear in log records."""
    import logging

    incident = _make_incident("incident-pii-01")
    container = _make_container(incident)

    from app.api.routes_feedback import router as feedback_router
    app = FastAPI()
    app.include_router(feedback_router)
    _bypass_auth(app)

    pii_comment = "My SSN is 123-45-6789 and this triage was wrong"
    client = TestClient(app)
    with patch("app.api.routes_feedback.get_container", return_value=container), \
         caplog.at_level(logging.INFO):
        client.post(
            "/incidents/incident-pii-01/feedback",
            json={"rating": "negative", "comment": pii_comment},
        )

    for record in caplog.records:
        assert pii_comment not in str(record.message)
        assert pii_comment not in str(getattr(record, "comment", ""))


# ---------------------------------------------------------------------------
# BR-03: Empty string incident_id or ticket_id returns 422
# ---------------------------------------------------------------------------


def test_resolution_webhook_empty_strings_rejected():
    """BR-03: Empty string values for required fields are rejected with 422."""
    incident = _make_incident()
    container = _make_container(incident)

    from app.api.routes_webhooks import router as webhooks_router
    app = FastAPI()
    app.include_router(webhooks_router)
    _bypass_auth(app)

    client = TestClient(app, raise_server_exceptions=False)
    with patch("app.api.routes_webhooks.get_container", return_value=container):
        response = client.post(
            "/webhooks/resolution",
            json={"incident_id": "   ", "ticket_id": ""},
        )
    # Pydantic will pass strings through; the handler raises 422 via HTTPException.
    assert response.status_code == 422
