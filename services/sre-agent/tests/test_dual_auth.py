"""Tests for HU-P018: JWT Middleware migration and dual-auth behavior.

AC-01: Protected endpoints return 401 when no auth is provided.
AC-02: Protected endpoints return 401 with an invalid JWT.
AC-03: Protected endpoints return 403 when role is insufficient.
AC-04: X-API-Key is accepted as backward-compat auth (dual-auth).
AC-05: Bearer JWT takes precedence when both JWT and X-API-Key are present.
AC-06: GET /health remains public (no auth required).
AC-07: POST /auth/mock-google-login remains public (no auth required).
AC-08: GET /context/status remains public (no auth required).
AC-09: POST /incidents/{id}/resolve enforces operator-minimum role.
AC-10: POST /context/reindex enforces admin/superadmin role.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps
from app.domain.entities import Incident, IncidentStatus, InjectionVerdict, Severity, Ticket, TicketStatus, TriageResult
from app.domain.entities.user import User, UserRole
from app.domain.ports import IStorageProvider
from tests.conftest import (
    build_jwt_container,
    make_jwt_for_role,
    make_jwt_for_user,
    make_user,
)
from app.infrastructure.config import settings as _app_settings


# ---------------------------------------------------------------------------
# Helpers — minimal isolated apps for each router under test
# ---------------------------------------------------------------------------


def _make_incident(incident_id: str = "inc-auth-001") -> Incident:
    return Incident(
        id=incident_id,
        reporter_email="tester@sre.com",
        title="Auth test incident",
        description="Testing dual-auth middleware",
    )


def _make_storage_with(incident: Incident | None = None):
    _store: dict = {}

    async def _save(inc: Incident) -> None:
        _store[inc.id] = inc

    async def _get(iid: str):
        return _store.get(iid)

    async def _list(limit: int = 50):
        return list(_store.values())

    async def _update(iid: str, patch: dict):
        return _store.get(iid)

    if incident is not None:
        asyncio.run(_save(incident))

    storage = MagicMock(spec=IStorageProvider)
    storage.save_incident = AsyncMock(side_effect=_save)
    storage.get_incident = AsyncMock(side_effect=_get)
    storage.list_incidents = AsyncMock(side_effect=_list)
    storage.update_incident = AsyncMock(side_effect=_update)
    storage.name = "memory"
    return storage


def _make_incidents_app(jwt_container: SimpleNamespace) -> tuple[FastAPI, TestClient]:
    """Build an isolated incidents app with real JWT auth wired."""
    from app.api.routes_incidents import router as incidents_router

    app = FastAPI()
    app.include_router(incidents_router)

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    return app, TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# AC-01: No auth → 401 on protected incident routes
# ---------------------------------------------------------------------------


class TestNoAuthReturns401:
    """AC-01: Every protected endpoint returns 401 with no credentials."""

    def test_get_incidents_no_auth_returns_401(self):
        """AC-01: GET /incidents without auth returns 401."""
        container = build_jwt_container()
        app, client = _make_incidents_app(container)
        storage = _make_storage_with()

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_incidents.get_container", return_value=MagicMock(storage=storage)):
            response = client.get("/incidents")

        assert response.status_code == 401

    def test_post_incidents_no_auth_returns_401(self):
        """AC-01: POST /incidents without auth returns 401."""
        container = build_jwt_container()
        app, client = _make_incidents_app(container)

        with patch("app.api.deps.get_container", return_value=container):
            response = client.post(
                "/incidents",
                data={
                    "reporter_email": "sre@company.com",
                    "title": "Test",
                    "description": "Test description",
                },
            )

        assert response.status_code == 401

    def test_get_incident_by_id_no_auth_returns_401(self):
        """AC-01: GET /incidents/{id} without auth returns 401."""
        container = build_jwt_container()
        app, client = _make_incidents_app(container)

        with patch("app.api.deps.get_container", return_value=container):
            response = client.get("/incidents/some-id")

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# AC-02: Invalid JWT → 401 on protected routes
# ---------------------------------------------------------------------------


class TestInvalidJwtReturns401:
    """AC-02: Invalid JWT token yields 401 on protected routes."""

    def test_get_incidents_invalid_jwt_returns_401(self, invalid_jwt_headers):
        """AC-02: GET /incidents with tampered token returns 401."""
        container = build_jwt_container()
        app, client = _make_incidents_app(container)

        with patch("app.api.deps.get_container", return_value=container):
            response = client.get("/incidents", headers=invalid_jwt_headers)

        assert response.status_code == 401

    def test_post_incidents_invalid_jwt_returns_401(self, invalid_jwt_headers):
        """AC-02: POST /incidents with tampered token returns 401."""
        container = build_jwt_container()
        app, client = _make_incidents_app(container)

        with patch("app.api.deps.get_container", return_value=container):
            response = client.post(
                "/incidents",
                data={
                    "reporter_email": "sre@company.com",
                    "title": "Test",
                    "description": "Test",
                },
                headers=invalid_jwt_headers,
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# AC-03: Insufficient role → 403
# ---------------------------------------------------------------------------


class TestInsufficientRoleReturns403:
    """AC-03: A valid JWT with insufficient role returns 403."""

    def test_resolve_incident_as_viewer_returns_403(self):
        """AC-03: POST /incidents/{id}/resolve as viewer returns 403."""
        viewer = make_user(role=UserRole.VIEWER)
        container = build_jwt_container(current_user=viewer)
        token = make_jwt_for_user(viewer)

        from app.api.routes_incidents import router as incidents_router

        incident = _make_incident("inc-resolve-viewer")
        storage = _make_storage_with(incident)
        app_container = MagicMock()
        app_container.storage = storage

        app = FastAPI()
        app.include_router(incidents_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_incidents.get_container", return_value=app_container):
            response = client.post(
                "/incidents/inc-resolve-viewer/resolve",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 403
        assert "not authorized" in response.json()["detail"].lower()

    def test_reindex_as_operator_returns_403(self):
        """AC-03: POST /context/reindex as operator returns 403."""
        operator = make_user(role=UserRole.OPERATOR)
        container = build_jwt_container(current_user=operator)
        token = make_jwt_for_user(operator)

        from app.api.routes_context import router as context_router

        app = FastAPI()
        app.include_router(context_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.deps.get_container", return_value=container):
            response = client.post(
                "/context/reindex",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC-04: X-API-Key backward compat
# ---------------------------------------------------------------------------


class TestApiKeyBackwardCompat:
    """AC-04: X-API-Key is still accepted on dual-auth endpoints."""

    def test_get_incidents_with_api_key_returns_200(self, api_key_headers):
        """AC-04: GET /incidents with valid X-API-Key returns 200."""
        storage = _make_storage_with()
        app_container = MagicMock()
        app_container.storage = storage

        from app.api.routes_incidents import router as incidents_router

        app = FastAPI()
        app.include_router(incidents_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.routes_incidents.get_container", return_value=app_container):
            response = client.get("/incidents", headers=api_key_headers)

        assert response.status_code == 200

    def test_invalid_api_key_returns_401(self):
        """AC-04: X-API-Key with wrong value returns 401."""
        from app.api.routes_incidents import router as incidents_router

        app = FastAPI()
        app.include_router(incidents_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/incidents", headers={"X-API-Key": "WRONG-KEY-NEVER-VALID"})
        assert response.status_code == 401

    def test_api_key_grants_superadmin_synthetic_user(self):
        """AC-04: X-API-Key produces a synthetic SUPERADMIN user (can resolve incidents)."""
        incident = _make_incident("inc-apikey-resolve")
        # The resolve endpoint guards against resolving un-ticketed incidents (409).
        # Set a ticket_id so the guard passes and we test only the auth path.
        incident.ticket_id = "t-001"
        storage = _make_storage_with(incident)

        app_container = MagicMock()
        app_container.storage = storage
        app_container.ticket = MagicMock()
        app_container.ticket.resolve_ticket = AsyncMock(
            return_value=Ticket(
                id="t-001",
                incident_id="inc-apikey-resolve",
                provider="mock",
                status=TicketStatus.RESOLVED,
            )
        )

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={"status": "resolved", "events": []})

        from app.api.routes_incidents import router as incidents_router

        app = FastAPI()
        app.include_router(incidents_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.routes_incidents.get_container", return_value=app_container), \
             patch("app.api.routes_incidents.build_resolution_graph", return_value=mock_graph):
            response = client.post(
                "/incidents/inc-apikey-resolve/resolve",
                headers={"X-API-Key": _app_settings.api_key},
            )

        # SUPERADMIN synthetic user passes operator-minimum role check
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# AC-05: JWT takes precedence when both headers are present
# ---------------------------------------------------------------------------


class TestJwtPrecedenceOverApiKey:
    """AC-05: Bearer JWT is used (not API key) when both headers are present."""

    def test_jwt_used_when_both_headers_present(self):
        """AC-05: When both Authorization and X-API-Key are sent, JWT is processed."""
        operator = make_user(role=UserRole.OPERATOR)
        container = build_jwt_container(current_user=operator)
        token = make_jwt_for_user(operator)

        storage = _make_storage_with()
        app_container = MagicMock()
        app_container.storage = storage

        from app.api.routes_incidents import router as incidents_router

        app = FastAPI()
        app.include_router(incidents_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        # Send both headers — JWT should be used (operator is valid for GET /incidents)
        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_incidents.get_container", return_value=app_container):
            response = client.get(
                "/incidents",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-API-Key": _app_settings.api_key,
                },
            )

        # Operator can list incidents — 200 confirms JWT resolved correctly
        assert response.status_code == 200

    def test_jwt_takes_precedence_invalid_jwt_still_fails(self):
        """AC-05: When both headers are present but JWT is invalid, returns 401 (not API key fallback)."""
        container = build_jwt_container()

        from app.api.routes_incidents import router as incidents_router

        app = FastAPI()
        app.include_router(incidents_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        # Invalid JWT + valid API key — JWT takes precedence and fails
        with patch("app.api.deps.get_container", return_value=container):
            response = client.get(
                "/incidents",
                headers={
                    "Authorization": "Bearer this.is.invalid.jwt",
                    "X-API-Key": _app_settings.api_key,
                },
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# AC-06: GET /health remains public
# ---------------------------------------------------------------------------


class TestPublicEndpoints:
    """AC-06/07/08: Public endpoints require no auth."""

    def test_health_is_public(self):
        """AC-06: GET /health returns 200 with no auth headers."""
        from app.api.routes_health import router as health_router

        app = FastAPI()
        app.include_router(health_router)
        client = TestClient(app)

        container = MagicMock()
        container.adapter_summary = lambda: {
            "llm": "mock", "ticket": "mock", "notify": "mock",
            "storage": "mock", "context": "mock",
        }

        with patch("app.api.routes_health.get_container", return_value=container), \
             patch("app.api.routes_health.get_langfuse", return_value=None):
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_context_status_is_public(self):
        """AC-08: GET /context/status returns 200 with no auth headers."""
        from app.api.routes_context import router as context_router

        app = FastAPI()
        app.include_router(context_router)
        client = TestClient(app)

        mock_context = MagicMock()
        mock_context.get_index_status = MagicMock(
            return_value={
                "provider": "github",
                "status": "ready",
                "indexed_files": 10,
                "total_chunks": 200,
                "index_path": "/data/faiss",
                "last_indexed_at": None,
                "repo_url": "https://github.com/test/repo",
            }
        )
        container = MagicMock()
        container.context = mock_context

        with patch("app.api.routes_context.get_container", return_value=container):
            response = client.get("/context/status")

        assert response.status_code == 200

    def test_auth_login_is_public(self):
        """AC-07: POST /auth/mock-google-login returns 200 with no auth headers."""
        from app.api.routes_auth import router as auth_router

        jwt_container = build_jwt_container()
        jwt_container.auth_service.mock_google_login = AsyncMock(
            return_value={
                "access_token": "fake-token",
                "token_type": "bearer",
                "user": {
                    "id": "abc",
                    "email": "sre@test.com",
                    "full_name": "SRE User",
                    "role": "operator",
                    "is_active": True,
                    "last_login_at": None,
                },
            }
        )

        app = FastAPI()
        app.include_router(auth_router, prefix="/auth")

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app)

        with patch("app.api.routes_auth.get_container", return_value=jwt_container):
            response = client.post(
                "/auth/mock-google-login",
                json={"email": "sre@test.com"},
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# AC-09: POST /incidents/{id}/resolve role matrix
# ---------------------------------------------------------------------------


class TestResolveIncidentRoleMatrix:
    """AC-09: Verify operator-minimum enforcement on resolve endpoint."""

    def _resolve_with_role(self, role: UserRole) -> int:
        # For OPERATOR the IDOR guard requires reporter_email == user.email.
        # Use a fixed email so both sides align.
        _email = "tester@sre.com" if role == UserRole.OPERATOR else f"{role.value}@sre.com"
        user = make_user(role=role, email=_email)
        container = build_jwt_container(current_user=user)
        token = make_jwt_for_user(user)

        incident = _make_incident("inc-role-test")
        # resolve endpoint guards un-ticketed incidents with 409 — set ticket_id so
        # we test the role-check path, not the business-state guard.
        incident.ticket_id = "t-001"
        storage = _make_storage_with(incident)
        app_container = MagicMock()
        app_container.storage = storage
        app_container.ticket = MagicMock()
        app_container.ticket.resolve_ticket = AsyncMock(
            return_value=Ticket(
                id="t-001",
                incident_id="inc-role-test",
                provider="mock",
                status=TicketStatus.RESOLVED,
            )
        )
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value={"status": "resolved", "events": []})

        from app.api.routes_incidents import router as incidents_router

        app = FastAPI()
        app.include_router(incidents_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_incidents.get_container", return_value=app_container), \
             patch("app.api.routes_incidents.build_resolution_graph", return_value=mock_graph):
            response = client.post(
                "/incidents/inc-role-test/resolve",
                headers={"Authorization": f"Bearer {token}"},
            )
        return response.status_code

    def test_viewer_cannot_resolve(self):
        """AC-09: VIEWER role returns 403 on resolve."""
        assert self._resolve_with_role(UserRole.VIEWER) == 403

    def test_operator_can_resolve(self):
        """AC-09: OPERATOR role returns 200 on resolve."""
        assert self._resolve_with_role(UserRole.OPERATOR) == 200

    def test_admin_can_resolve(self):
        """AC-09: ADMIN role returns 200 on resolve."""
        assert self._resolve_with_role(UserRole.ADMIN) == 200

    def test_superadmin_can_resolve(self):
        """AC-09: SUPERADMIN role returns 200 on resolve."""
        assert self._resolve_with_role(UserRole.SUPERADMIN) == 200


# ---------------------------------------------------------------------------
# AC-10: POST /context/reindex admin/superadmin only
# ---------------------------------------------------------------------------


class TestReindexRoleMatrix:
    """AC-10: /context/reindex requires admin or superadmin."""

    def _reindex_with_role(self, role: UserRole) -> int:
        user = make_user(role=role)
        container = build_jwt_container(current_user=user)
        token = make_jwt_for_user(user)

        mock_context = MagicMock()
        mock_context.reindex = AsyncMock(return_value=None)
        app_container = MagicMock()
        app_container.context = mock_context

        from app.api.routes_context import router as context_router

        app = FastAPI()
        app.include_router(context_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.deps.get_container", return_value=container), \
             patch("app.api.routes_context.get_container", return_value=app_container):
            response = client.post(
                "/context/reindex",
                headers={"Authorization": f"Bearer {token}"},
            )
        return response.status_code

    def test_operator_cannot_reindex(self):
        """AC-10: OPERATOR returns 403 on reindex."""
        assert self._reindex_with_role(UserRole.OPERATOR) == 403

    def test_flow_configurator_cannot_reindex(self):
        """AC-10: FLOW_CONFIGURATOR returns 403 on reindex."""
        assert self._reindex_with_role(UserRole.FLOW_CONFIGURATOR) == 403

    def test_admin_can_reindex(self):
        """AC-10: ADMIN returns 200 on reindex."""
        assert self._reindex_with_role(UserRole.ADMIN) == 200

    def test_superadmin_can_reindex(self):
        """AC-10: SUPERADMIN returns 200 on reindex."""
        assert self._reindex_with_role(UserRole.SUPERADMIN) == 200
