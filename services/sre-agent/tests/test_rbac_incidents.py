"""Tests for RBAC filtering in GET /incidents.

TC-RBAC-004: operator solo ve sus propios incidentes (filtrado por reporter_email)
TC-RBAC-005: flow_configurator ve todos los incidentes
TC-RBAC-006: admin ve todos los incidentes

HALLAZGO DE QA (GAP-002):
  El endpoint GET /incidents NO implementa filtro RBAC por reporter_email para
  operadores. La implementacion actual en routes_incidents.py llama directamente
  a container.storage.list_incidents() sin ningun filtro de rol, retornando
  TODOS los incidentes a cualquier usuario autenticado.

  TC-RBAC-004 documenta el comportamiento ACTUAL (incorrecto) vs el ESPERADO.
  El test esta marcado con xfail para que la suite siga pasando hasta que el
  desarrollador implemente el filtro. La correccion requiere:
    1. Pasar current_user.email al storage adapter
    2. Implementar filtracion por reporter_email en IStorageProvider.list_incidents()

  Severidad del bug: Medium — un operador puede ver incidentes de otros operadores,
  lo que viola el principio de minimo privilegio (ARC-022).

  Ref: routes_incidents.py L117-123, ARCHITECTURE.md ARC-022.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.domain.entities import (
    Incident,
    InjectionVerdict,
    Ticket,
    TicketStatus,
    NotificationReceipt,
    ReporterNotification,
)
from app.domain.entities.user import User, UserRole
from app.domain.ports import IStorageProvider


# ---------------------------------------------------------------------------
# Auth helpers — build users with specific roles
# ---------------------------------------------------------------------------


def _make_user(email: str, role: UserRole) -> User:
    import uuid
    from datetime import datetime, timezone

    return User(
        id=uuid.uuid4(),
        email=email,
        full_name=f"Test {role.value}",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def _bypass_auth_as(app: FastAPI, user: User) -> None:
    """Override get_current_user_or_api_key to inject a specific user."""
    async def _no_auth() -> User:
        return user
    app.dependency_overrides[deps.get_current_user_or_api_key] = _no_auth


# ---------------------------------------------------------------------------
# Container helper — two incidents from different operators
# ---------------------------------------------------------------------------


def _make_container_with_incidents() -> tuple[SimpleNamespace, list[Incident]]:
    """Build a container with two incidents from different reporters."""
    _store: dict[str, Incident] = {}

    incident_a = Incident(
        id="incident-operator-a-001",
        reporter_email="operator.a@company.com",
        title="Service A down",
        description="Microservice A is returning 500",
    )
    incident_b = Incident(
        id="incident-operator-b-001",
        reporter_email="operator.b@company.com",
        title="Service B down",
        description="Microservice B is OOMKilled",
    )

    async def _save_incident(inc: Incident) -> None:
        _store[inc.id] = inc

    async def _list_incidents(limit: int = 50):
        return list(_store.values())[:limit]

    async def _get_incident(incident_id: str):
        return _store.get(incident_id)

    async def _update_incident(incident_id: str, patch: dict):
        return _store.get(incident_id)

    # Pre-load both incidents
    asyncio.run(_save_incident(incident_a))
    asyncio.run(_save_incident(incident_b))

    storage = MagicMock(spec=IStorageProvider)
    storage.save_incident = AsyncMock(side_effect=_save_incident)
    storage.get_incident = AsyncMock(side_effect=_get_incident)
    storage.update_incident = AsyncMock(side_effect=_update_incident)
    storage.list_incidents = AsyncMock(side_effect=_list_incidents)
    storage.name = "memory"

    mock_ticket = MagicMock()
    mock_ticket.name = "mock"

    mock_notify = MagicMock()
    mock_notify.name = "mock"

    mock_llm = MagicMock()
    mock_llm.name = "mock_llm"

    mock_context = MagicMock()
    mock_context.name = "mock_context"

    container = SimpleNamespace(
        storage=storage,
        llm=mock_llm,
        ticket=mock_ticket,
        notify=mock_notify,
        context=mock_context,
    )
    return container, [incident_a, incident_b]


# ---------------------------------------------------------------------------
# TC-RBAC-004: operator solo ve sus propios incidentes
#
# ESTADO: PASS — filtro RBAC implementado en routes_incidents.py (BUG-002 fix).
# El backend ahora filtra por reporter_email cuando current_user.role == OPERATOR.
# ---------------------------------------------------------------------------


def test_operator_only_sees_own_incidents():
    """TC-RBAC-004: Un operador solo debe ver incidentes donde reporter_email == su email.

    COMPORTAMIENTO ESPERADO (implementado, BUG-002 fix):
      - operator.a@company.com realiza GET /incidents
      - Respuesta contiene solo incident-operator-a-001 (su incidente)
      - incident-operator-b-001 NO aparece en la respuesta
    """
    container, incidents = _make_container_with_incidents()
    operator_a = _make_user("operator.a@company.com", UserRole.OPERATOR)

    from app.api.routes_incidents import router as incidents_router
    app = FastAPI()
    app.include_router(incidents_router)
    _bypass_auth_as(app, operator_a)

    client = TestClient(app, raise_server_exceptions=False)
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.api.routes_incidents.get_container", return_value=container
    ):
        response = client.get("/incidents")

    assert response.status_code == 200
    body = response.json()
    incident_ids = [i["id"] for i in body]

    # RBAC: operator only sees their own incident
    assert "incident-operator-a-001" in incident_ids, (
        "Operator A's own incident must be visible"
    )
    assert "incident-operator-b-001" not in incident_ids, (
        "BUG: Operator A can see Operator B's incident — RBAC filter missing"
    )


# ---------------------------------------------------------------------------
# TC-RBAC-005: flow_configurator ve todos los incidentes
# ---------------------------------------------------------------------------


def test_flow_configurator_sees_all_incidents():
    """TC-RBAC-005: Un flow_configurator debe ver TODOS los incidentes del sistema.

    COMPORTAMIENTO ESPERADO:
      - flow_configurator realiza GET /incidents
      - Respuesta contiene todos los incidentes (de todos los reporters)

    ESTADO: Este test refleja el comportamiento actual del backend (retorna todo)
    y verifica que el rol flow_configurator NO este restringido cuando se implemente
    el filtro RBAC. PASS hoy, debe seguir PASS despues del fix.
    """
    container, incidents = _make_container_with_incidents()
    configurator = _make_user("configurator@company.com", UserRole.FLOW_CONFIGURATOR)

    from app.api.routes_incidents import router as incidents_router
    app = FastAPI()
    app.include_router(incidents_router)
    _bypass_auth_as(app, configurator)

    client = TestClient(app, raise_server_exceptions=False)
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.api.routes_incidents.get_container", return_value=container
    ):
        response = client.get("/incidents")

    assert response.status_code == 200
    body = response.json()
    incident_ids = [i["id"] for i in body]

    # flow_configurator should see ALL incidents
    assert "incident-operator-a-001" in incident_ids, (
        "flow_configurator must see incident from operator A"
    )
    assert "incident-operator-b-001" in incident_ids, (
        "flow_configurator must see incident from operator B"
    )


# ---------------------------------------------------------------------------
# TC-RBAC-006: admin ve todos los incidentes
# ---------------------------------------------------------------------------


def test_admin_sees_all_incidents():
    """TC-RBAC-006: Un admin debe ver TODOS los incidentes del sistema.

    COMPORTAMIENTO ESPERADO:
      - admin realiza GET /incidents
      - Respuesta contiene todos los incidentes (de todos los reporters)

    ESTADO: PASS hoy. Debe seguir PASS despues de cualquier fix de RBAC.
    """
    container, incidents = _make_container_with_incidents()
    admin = _make_user("admin@company.com", UserRole.ADMIN)

    from app.api.routes_incidents import router as incidents_router
    app = FastAPI()
    app.include_router(incidents_router)
    _bypass_auth_as(app, admin)

    client = TestClient(app, raise_server_exceptions=False)
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.api.routes_incidents.get_container", return_value=container
    ):
        response = client.get("/incidents")

    assert response.status_code == 200
    body = response.json()
    incident_ids = [i["id"] for i in body]

    # admin should see ALL incidents
    assert "incident-operator-a-001" in incident_ids, (
        "admin must see incident from operator A"
    )
    assert "incident-operator-b-001" in incident_ids, (
        "admin must see incident from operator B"
    )
