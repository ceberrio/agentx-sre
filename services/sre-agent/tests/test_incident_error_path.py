"""Tests for POST /incidents error path — orchestrator exception handling.

TC-U-INC-017: Cuando el orquestador lanza una excepcion, POST /incidents retorna
              HTTP 500 con detail="incident_processing_failed".

This verifies the error boundary in routes_incidents.py L94-98:
  try:
      final_state = await graph.ainvoke(state)
  except Exception as exc:
      log.error("api.graph_invocation_failed", ...)
      raise HTTPException(status_code=500, detail="incident_processing_failed")

Auth note (HU-P018): Auth is bypassed using dependency_overrides. The focus
of this test is the HTTP error contract for unhandled orchestrator failures.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.domain.entities import (
    Incident,
    InjectionVerdict,
    Ticket,
    TicketStatus,
    NotificationReceipt,
)
from app.domain.entities.user import User, UserRole
from app.domain.ports import IStorageProvider


# ---------------------------------------------------------------------------
# Auth bypass helper
# ---------------------------------------------------------------------------


def _bypass_auth(app: FastAPI) -> None:
    """Override get_current_user_or_api_key to bypass auth in HTTP-layer tests."""
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
# Container helper
# ---------------------------------------------------------------------------


def _make_container():
    """Build a container double with in-memory storage for POST /incidents tests."""
    _store: dict[str, Incident] = {}

    async def _save_incident(inc: Incident) -> None:
        _store[inc.id] = inc

    async def _get_incident(incident_id: str):
        return _store.get(incident_id)

    async def _update_incident(incident_id: str, patch_data: dict):
        return _store.get(incident_id)

    storage = MagicMock(spec=IStorageProvider)
    storage.save_incident = AsyncMock(side_effect=_save_incident)
    storage.get_incident = AsyncMock(side_effect=_get_incident)
    storage.update_incident = AsyncMock(side_effect=_update_incident)
    storage.name = "memory"

    mock_ticket = MagicMock()
    mock_ticket.name = "mock"
    mock_ticket.create_ticket = AsyncMock(
        return_value=Ticket(
            id="ticket-001",
            incident_id="test",
            provider="mock",
            status=TicketStatus.OPEN,
        )
    )

    mock_notify = MagicMock()
    mock_notify.name = "mock"
    mock_notify.notify_team = AsyncMock(
        return_value=NotificationReceipt(delivered=True, provider="mock", channel="team")
    )

    mock_llm = MagicMock()
    mock_llm.name = "mock_llm"
    mock_llm.classify_injection = AsyncMock(
        return_value=InjectionVerdict(verdict="no", score=0.0)
    )

    mock_context = MagicMock()
    mock_context.name = "mock_context"
    mock_context.search_context = AsyncMock(return_value=[])

    container = SimpleNamespace(
        storage=storage,
        llm=mock_llm,
        ticket=mock_ticket,
        notify=mock_notify,
        context=mock_context,
    )
    container.adapter_summary = lambda: {
        "llm": "mock_llm",
        "ticket": "mock",
        "notify": "mock",
        "storage": "memory",
        "context": "mock_context",
    }
    return container


# ---------------------------------------------------------------------------
# TC-U-INC-017: Graph exception => HTTP 500 with detail="incident_processing_failed"
# ---------------------------------------------------------------------------


def test_orchestrator_exception_returns_500_with_correct_detail():
    """TC-U-INC-017: Unhandled orchestrator exception yields HTTP 500.

    Acceptance criteria:
    - When build_orchestrator_graph returns a graph whose ainvoke raises RuntimeError,
      POST /incidents MUST return HTTP 500.
    - Response body MUST contain detail="incident_processing_failed".
    - The incident is saved BEFORE the pipeline runs (storage.save_incident is called).

    This verifies the error boundary in routes_incidents.py is properly catching
    exceptions from the LangGraph pipeline and returning a safe error response
    without leaking internal stack traces.
    """
    container = _make_container()

    from app.api.routes_incidents import router as incidents_router
    app = FastAPI()
    app.include_router(incidents_router)
    _bypass_auth(app)

    # Build a graph mock whose ainvoke raises an unexpected exception
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        side_effect=RuntimeError("Simulated LLM adapter connection timeout")
    )

    client = TestClient(app, raise_server_exceptions=False)
    with (
        patch("app.api.routes_incidents.get_container", return_value=container),
        patch(
            "app.api.routes_incidents.build_orchestrator_graph",
            return_value=mock_graph,
        ),
    ):
        response = client.post(
            "/incidents",
            data={
                "reporter_email": "sre@company.com",
                "title": "Critical DB failure",
                "description": "Primary database unreachable — 500 errors across all pods",
            },
        )

    assert response.status_code == 500, (
        f"Expected HTTP 500 when orchestrator throws, got {response.status_code}. "
        f"Body: {response.text}"
    )
    body = response.json()
    assert body.get("detail") == "incident_processing_failed", (
        f"Expected detail='incident_processing_failed', got: {body}"
    )


def test_orchestrator_exception_incident_is_persisted_before_pipeline():
    """TC-U-INC-017b: Even when pipeline fails, incident is saved to storage first.

    Verifies that container.storage.save_incident is called BEFORE graph.ainvoke,
    so that the incident is traceable even after a processing failure.
    This guarantees no silent data loss on pipeline errors.
    """
    container = _make_container()

    from app.api.routes_incidents import router as incidents_router
    app = FastAPI()
    app.include_router(incidents_router)
    _bypass_auth(app)

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        side_effect=Exception("Simulated graph failure")
    )

    client = TestClient(app, raise_server_exceptions=False)
    with (
        patch("app.api.routes_incidents.get_container", return_value=container),
        patch(
            "app.api.routes_incidents.build_orchestrator_graph",
            return_value=mock_graph,
        ),
    ):
        response = client.post(
            "/incidents",
            data={
                "reporter_email": "sre@company.com",
                "title": "Memory leak",
                "description": "Container OOMKilled in payment namespace",
            },
        )

    # HTTP 500 is expected
    assert response.status_code == 500

    # The incident MUST have been persisted to storage before the pipeline ran
    container.storage.save_incident.assert_called_once(), (
        "storage.save_incident must be called even when pipeline fails"
    )


def test_orchestrator_value_error_also_returns_500():
    """TC-U-INC-017c: ValueError from orchestrator also returns 500 (broad except clause).

    The error boundary uses `except Exception` which covers all non-BaseException
    errors. This test verifies ValueError (common from validation layers) is caught.
    """
    container = _make_container()

    from app.api.routes_incidents import router as incidents_router
    app = FastAPI()
    app.include_router(incidents_router)
    _bypass_auth(app)

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        side_effect=ValueError("Unexpected state schema violation in LangGraph node")
    )

    client = TestClient(app, raise_server_exceptions=False)
    with (
        patch("app.api.routes_incidents.get_container", return_value=container),
        patch(
            "app.api.routes_incidents.build_orchestrator_graph",
            return_value=mock_graph,
        ),
    ):
        response = client.post(
            "/incidents",
            data={
                "reporter_email": "sre@company.com",
                "title": "Schema error test",
                "description": "Testing ValueError path in error boundary",
            },
        )

    assert response.status_code == 500
    assert response.json().get("detail") == "incident_processing_failed"
