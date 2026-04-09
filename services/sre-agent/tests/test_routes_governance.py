"""Tests for Governance Configuration endpoints — HU-12 / DEC-A05.

AC-01: GET /governance/thresholds returns 200 with default seeded values deserialized correctly.
AC-02: PUT /governance/thresholds updates stored values — subsequent GET reflects the change.
AC-03: GET /governance/thresholds returns kill_switch_enabled as a Python bool (not a string).
AC-04: PUT /governance/thresholds with kill_switch_enabled=True stores 'true' string, GET returns True.
AC-05: PUT /governance/thresholds with no fields returns 200 (no-op).
AC-06: PUT /governance/thresholds with confidence_escalation_min > 1.0 returns 422.
AC-07: PUT /governance/thresholds with max_rag_docs_to_expose = 0 returns 422.
BR-01: Anonymous request (no auth) returns 401.
BR-02: OPERATOR role is rejected with 403 on both GET and PUT.
BR-03: VIEWER role is rejected with 403 on both GET and PUT (GET now allows flow_configurator too).
BR-04: PUT /governance/thresholds with severity outside the allowed enum returns 422.
BR-05: DB failure on GET returns 503.
BR-06: DB failure on PUT returns 503.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.auth.jwt_adapter import JWTAdapter
from app.adapters.platform_config.memory_adapter import MemoryPlatformConfigAdapter
from app.api import deps
from app.api.routes_governance import router as governance_router
from app.domain.entities.user import User, UserRole

# ---------------------------------------------------------------------------
# Internal test helpers
# ---------------------------------------------------------------------------

_JWT_SECRET = "test-jwt-secret-for-unit-tests-do-not-use-in-production"
_JWT_ALGORITHM = "HS256"


def _jwt_adapter() -> JWTAdapter:
    return JWTAdapter(secret=_JWT_SECRET, algorithm=_JWT_ALGORITHM, expire_minutes=480)


def _make_user(role: UserRole = UserRole.ADMIN) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value}@test.local",
        full_name=f"Test {role.value.title()}",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_login_at=None,
    )


def _make_container(
    provider: MemoryPlatformConfigAdapter,
    role: UserRole = UserRole.ADMIN,
) -> SimpleNamespace:
    """Build a container double with real JWT adapter and mocked auth_service."""
    _jwt = _jwt_adapter()
    _user = _make_user(role=role)
    _auth_svc = MagicMock()
    _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
    return SimpleNamespace(jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider)


def _make_app(container: SimpleNamespace) -> tuple[FastAPI, str]:
    """Return (app, bearer_token) with dependency overrides applied."""
    app = FastAPI()
    app.include_router(governance_router)

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db
    token = container.jwt_adapter.create_token(container.auth_service.get_user_by_id.return_value)
    return app, token


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# AC-01: GET /config/governance returns 200 with defaults deserialized correctly
# ---------------------------------------------------------------------------


def test_get_governance_returns_200_with_float_and_int_defaults():
    """AC-01 — GET returns seeded defaults as typed Python values."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/governance/thresholds", headers=_bearer(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence_escalation_min"] == pytest.approx(0.7)
    assert body["quality_score_min_for_autoticket"] == pytest.approx(0.6)
    assert body["severity_autoticket_threshold"] == "HIGH"
    assert body["max_rag_docs_to_expose"] == 5


def test_get_governance_empty_section_returns_none_fields():
    """AC-01 — Fresh install with no governance row: all fields are None."""
    provider = MemoryPlatformConfigAdapter(seed={})
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/governance/thresholds", headers=_bearer(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence_escalation_min"] is None
    assert body["kill_switch_enabled"] is None


# ---------------------------------------------------------------------------
# AC-02: PUT updates values — GET reflects the change
# ---------------------------------------------------------------------------


def test_put_then_get_confidence_min_updated():
    """AC-02 — PUT writes to adapter; subsequent GET reads updated value."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)

        put_resp = client.put(
            "/governance/thresholds",
            headers=_bearer(token),
            json={"confidence_escalation_min": 0.85},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["success"] is True

        get_resp = client.get("/governance/thresholds", headers=_bearer(token))

    assert get_resp.status_code == 200
    assert get_resp.json()["confidence_escalation_min"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# AC-03: kill_switch_enabled returned as bool when stored as "false"
# ---------------------------------------------------------------------------


def test_kill_switch_false_returned_as_bool():
    """AC-03 — kill_switch_enabled='false' string in DB is returned as Python False."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/governance/thresholds", headers=_bearer(token))

    assert resp.status_code == 200
    assert resp.json()["kill_switch_enabled"] is False


# ---------------------------------------------------------------------------
# AC-04: PUT kill_switch_enabled=True stored as 'true'; GET returns True
# ---------------------------------------------------------------------------


def test_put_kill_switch_true_stored_and_returned_as_bool():
    """AC-04 — PUT boolean True is persisted as 'true' string; GET deserializes back to True."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        client.put("/governance/thresholds", headers=_bearer(token), json={"kill_switch_enabled": True})
        resp = client.get("/governance/thresholds", headers=_bearer(token))

    assert resp.status_code == 200
    assert resp.json()["kill_switch_enabled"] is True


# ---------------------------------------------------------------------------
# AC-05: PUT with empty body returns 200 (no-op)
# ---------------------------------------------------------------------------


def test_put_empty_body_returns_success_noop():
    """AC-05 — PUT with no fields returns 200 without touching the adapter."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)
    initial_log_len = len(provider.audit_log)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.put("/governance/thresholds", headers=_bearer(token), json={})

    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Audit log must not grow — no update happened.
    assert len(provider.audit_log) == initial_log_len


# ---------------------------------------------------------------------------
# AC-06: confidence_escalation_min outside [0, 1] returns 422
# ---------------------------------------------------------------------------


def test_put_confidence_above_1_returns_422():
    """AC-06 — confidence_escalation_min > 1.0 is rejected."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.put(
            "/governance/thresholds",
            headers=_bearer(token),
            json={"confidence_escalation_min": 1.5},
        )

    assert resp.status_code == 422


def test_put_confidence_below_0_returns_422():
    """AC-06 — confidence_escalation_min < 0.0 is rejected."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.put(
            "/governance/thresholds",
            headers=_bearer(token),
            json={"confidence_escalation_min": -0.1},
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# AC-07: max_rag_docs_to_expose out of range returns 422
# ---------------------------------------------------------------------------


def test_put_rag_docs_zero_returns_422():
    """AC-07 — max_rag_docs_to_expose = 0 is below the minimum of 1."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.put(
            "/governance/thresholds",
            headers=_bearer(token),
            json={"max_rag_docs_to_expose": 0},
        )

    assert resp.status_code == 422


def test_put_rag_docs_above_max_returns_422():
    """AC-07 — max_rag_docs_to_expose = 21 exceeds the maximum of 20."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.put(
            "/governance/thresholds",
            headers=_bearer(token),
            json={"max_rag_docs_to_expose": 21},
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# BR-01: Anonymous request returns 401
# ---------------------------------------------------------------------------


def test_get_without_auth_returns_401():
    """BR-01 — No auth header on GET returns 401."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, _ = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/governance/thresholds")

    assert resp.status_code == 401


def test_put_without_auth_returns_401():
    """BR-01 — No auth header on PUT returns 401."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, _ = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.put("/governance/thresholds", json={"kill_switch_enabled": False})

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# BR-02: OPERATOR role is rejected with 403
# ---------------------------------------------------------------------------


def test_get_as_operator_returns_403():
    """BR-02 — OPERATOR role is below the minimum required (ADMIN)."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider, role=UserRole.OPERATOR)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/governance/thresholds", headers=_bearer(token))

    assert resp.status_code == 403


def test_put_as_operator_returns_403():
    """BR-02 — OPERATOR role is rejected on PUT."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider, role=UserRole.OPERATOR)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.put(
            "/governance/thresholds", headers=_bearer(token), json={"kill_switch_enabled": True}
        )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# BR-03: VIEWER role is rejected with 403
# ---------------------------------------------------------------------------


def test_get_as_viewer_returns_403():
    """BR-03 — VIEWER role is rejected on GET."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider, role=UserRole.VIEWER)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/governance/thresholds", headers=_bearer(token))

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# BR-04: severity outside allowed enum returns 422
# ---------------------------------------------------------------------------


def test_put_invalid_severity_returns_422():
    """BR-04 — severity_autoticket_threshold must be LOW | MEDIUM | HIGH | CRITICAL."""
    provider = MemoryPlatformConfigAdapter()
    container = _make_container(provider)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        app, token = _make_app(container)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.put(
            "/governance/thresholds",
            headers=_bearer(token),
            json={"severity_autoticket_threshold": "UNKNOWN"},
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# BR-05: DB failure on GET returns 503
# ---------------------------------------------------------------------------


def test_get_db_failure_returns_503():
    """BR-05 — If the storage adapter raises, GET returns 503."""
    provider = MagicMock()
    provider.get_config = AsyncMock(side_effect=RuntimeError("db down"))

    _jwt = _jwt_adapter()
    _user = _make_user(role=UserRole.ADMIN)
    _auth_svc = MagicMock()
    _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
    container = SimpleNamespace(jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider)

    app = FastAPI()
    app.include_router(governance_router)

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db
    token = _jwt.create_token(_user)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/governance/thresholds", headers=_bearer(token))

    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# BR-06: DB failure on PUT returns 503
# ---------------------------------------------------------------------------


def test_put_db_failure_returns_503():
    """BR-06 — If the storage adapter raises during update, PUT returns 503."""
    provider = MagicMock()
    provider.update_config = AsyncMock(side_effect=RuntimeError("db down"))

    _jwt = _jwt_adapter()
    _user = _make_user(role=UserRole.ADMIN)
    _auth_svc = MagicMock()
    _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
    container = SimpleNamespace(jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider)

    app = FastAPI()
    app.include_router(governance_router)

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db
    token = _jwt.create_token(_user)

    with patch("app.api.routes_governance.get_container", return_value=container), \
         patch("app.api.deps.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put(
            "/governance/thresholds",
            headers=_bearer(token),
            json={"kill_switch_enabled": True},
        )

    assert resp.status_code == 503
