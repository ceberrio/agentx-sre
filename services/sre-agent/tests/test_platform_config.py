"""Tests for Platform Configuration endpoints — HU-P032-A.

AC-01: GET /config/ticket-system returns 200 with credentials masked as None
AC-02: PUT /config/ticket-system stores update, credentials never returned
AC-03: GET /config/observability returns 200
AC-04: PUT /config/observability with forbidden langfuse_secret_key returns 400
AC-05: GET /config/security returns 200
AC-06: PUT /config/security with max_upload_size_mb=100 returns 422
BR-01: Anonymous (no auth) requests return 401/403
BR-02: Audit log has expected rows after PUT (MemoryAdapter)
BR-03: GET returns None for all known credential fields (ARC-024)
BR-04: PUT /config/notifications with invalid smtp_port returns 422
"""
from __future__ import annotations

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
from app.api.routes_platform_config import router as platform_config_router
from app.domain.entities.user import User, UserRole

# ---------------------------------------------------------------------------
# Test helpers
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


def _build_test_app(
    platform_provider: MemoryPlatformConfigAdapter | None = None,
    current_user: User | None = None,
) -> tuple[FastAPI, TestClient, MemoryPlatformConfigAdapter]:
    """Build an isolated FastAPI test app with the platform config router.

    Uses MemoryPlatformConfigAdapter and real JWT verification.
    Container is injected via get_container patch.
    """
    _jwt = _jwt_adapter()
    _user = current_user or _make_user(role=UserRole.ADMIN)
    _auth_svc = MagicMock()
    _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
    _provider = platform_provider or MemoryPlatformConfigAdapter()

    container = SimpleNamespace(
        jwt_adapter=_jwt,
        auth_service=_auth_svc,
        platform_config_provider=_provider,
    )

    app = FastAPI()
    app.include_router(platform_config_router)

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    with patch("app.api.routes_platform_config.get_container", return_value=container):
        with patch("app.api.deps.get_container", return_value=container):
            client = TestClient(app, raise_server_exceptions=True)
            return app, client, _provider


def _auth_header(role: UserRole = UserRole.ADMIN) -> dict:
    _jwt = _jwt_adapter()
    user = _make_user(role=role)
    token = _jwt.create_token(user)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# AC-01: GET /config/ticket-system returns 200, credentials masked as None
# ---------------------------------------------------------------------------


def test_get_ticket_system_returns_200_with_credentials_masked():
    """AC-01 / BR-03: GET /config/ticket-system — credentials returned as None."""
    provider = MemoryPlatformConfigAdapter()
    _, client, _ = _build_test_app(platform_provider=provider)

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt,
            auth_service=_auth_svc,
            platform_config_provider=provider,
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.get("/config/ticket-system", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    # Credential fields must be None (ARC-024)
    assert data.get("gitlab_token") is None
    assert data.get("jira_api_token") is None
    # Non-credential field present
    assert "ticket_provider" in data


# ---------------------------------------------------------------------------
# AC-02: PUT /config/ticket-system stores update, credentials not returned
# ---------------------------------------------------------------------------


def test_put_ticket_system_returns_200_and_stores_update():
    """AC-02: PUT /config/ticket-system with valid body returns 200."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.put(
            "/config/ticket-system",
            json={"ticket_provider": "jira", "jira_url": "https://jira.example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "updated_at" in body

    # Verify stored value (does not leak credential)
    import asyncio
    stored = asyncio.run(provider.get_value("ticket_system", "ticket_provider"))
    assert stored == "jira"


# ---------------------------------------------------------------------------
# AC-03: GET /config/observability returns 200
# ---------------------------------------------------------------------------


def test_get_observability_returns_200():
    """AC-03: GET /config/observability returns 200 with known fields."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.get("/config/observability", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("log_level") == "INFO"
    assert data.get("langfuse_enabled") == "true"


# ---------------------------------------------------------------------------
# AC-04: PUT /config/observability with langfuse_secret_key returns 400
# ---------------------------------------------------------------------------


def test_put_observability_with_forbidden_field_returns_400():
    """AC-04 / ARC-025: langfuse_secret_key in body returns HTTP 400."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.put(
            "/config/observability",
            json={"langfuse_secret_key": "sk-lf-secret"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 400
    assert "not configurable via API" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# AC-05: GET /config/security returns 200
# ---------------------------------------------------------------------------


def test_get_security_returns_200():
    """AC-05: GET /config/security returns 200 with known fields."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.get("/config/security", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    data = resp.json()
    assert "max_upload_size_mb" in data
    assert "guardrails_llm_judge_enabled" in data


# ---------------------------------------------------------------------------
# AC-06: PUT /config/security with max_upload_size_mb=100 returns 422
# ---------------------------------------------------------------------------


def test_put_security_with_invalid_upload_size_returns_422():
    """AC-06: max_upload_size_mb=100 exceeds max=50 — Pydantic returns 422."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.put(
            "/config/security",
            json={"max_upload_size_mb": 100},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# BR-01: Anonymous request to any config endpoint returns 401/403
# ---------------------------------------------------------------------------


def test_anonymous_request_returns_401():
    """BR-01: No auth header → 401 on GET /config/ticket-system."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _auth_svc = MagicMock()
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)

        resp = c.get("/config/ticket-system")

    assert resp.status_code in (401, 403)


def test_operator_role_cannot_access_config():
    """BR-01: OPERATOR role → 403 on GET /config/security (RBAC enforcement)."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.OPERATOR)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.get("/config/security", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# BR-02: Audit log has expected rows after PUT (MemoryAdapter)
# ---------------------------------------------------------------------------


def test_put_creates_audit_log_entry():
    """BR-02 / ARC-026: After PUT, MemoryAdapter audit_log has one row per changed field."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        # Two fields updated → two audit rows expected
        resp = c.put(
            "/config/ticket-system",
            json={"ticket_provider": "jira", "jira_url": "https://jira.local"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert len(provider.audit_log) == 2
    sections = {entry["section"] for entry in provider.audit_log}
    assert sections == {"ticket_system"}
    keys = {entry["field_key"] for entry in provider.audit_log}
    assert "ticket_provider" in keys
    assert "jira_url" in keys


def test_put_credential_field_audit_log_is_redacted():
    """BR-02 / ARC-026: Credential fields stored as [REDACTED] in audit log."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.put(
            "/config/ticket-system",
            json={"gitlab_token": "glpat-supersecret"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    # Credential value must be [REDACTED] in audit — never the plaintext
    audit_entry = next(
        e for e in provider.audit_log if e["field_key"] == "gitlab_token"
    )
    assert audit_entry["new_value"] == "[REDACTED]"
    assert "glpat-supersecret" not in str(provider.audit_log)


# ---------------------------------------------------------------------------
# BR-04: PUT /config/notifications with invalid smtp_port returns 422
# ---------------------------------------------------------------------------


def test_put_notifications_invalid_smtp_port_returns_422():
    """BR-04: smtp_port=99999 fails Pydantic validation → 422."""
    provider = MemoryPlatformConfigAdapter()

    with patch("app.api.routes_platform_config.get_container") as mock_gc, \
         patch("app.api.deps.get_container") as mock_deps_gc:
        _jwt = _jwt_adapter()
        _user = _make_user(UserRole.ADMIN)
        _auth_svc = MagicMock()
        _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
        container = SimpleNamespace(
            jwt_adapter=_jwt, auth_service=_auth_svc, platform_config_provider=provider
        )
        mock_gc.return_value = container
        mock_deps_gc.return_value = container

        app = FastAPI()
        app.include_router(platform_config_router)

        async def _fake_db():
            yield MagicMock()

        app.dependency_overrides[deps.get_db] = _fake_db
        c = TestClient(app, raise_server_exceptions=True)
        token = _jwt.create_token(_user)

        resp = c.put(
            "/config/notifications",
            json={"smtp_port": 99999},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Memory adapter unit tests
# ---------------------------------------------------------------------------


class TestMemoryPlatformConfigAdapter:
    """Unit tests for MemoryPlatformConfigAdapter — no HTTP layer."""

    def _adapter(self) -> MemoryPlatformConfigAdapter:
        return MemoryPlatformConfigAdapter()

    @pytest.mark.asyncio
    async def test_get_config_returns_section_data(self):
        adapter = self._adapter()
        result = await adapter.get_config("ticket_system")
        assert "ticket_provider" in result
        assert result["ticket_provider"] == "gitlab"

    @pytest.mark.asyncio
    async def test_get_value_returns_single_key(self):
        adapter = self._adapter()
        result = await adapter.get_value("observability", "log_level")
        assert result == "INFO"

    @pytest.mark.asyncio
    async def test_get_value_missing_key_returns_none(self):
        adapter = self._adapter()
        result = await adapter.get_value("ticket_system", "nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_config_writes_and_audit_log(self):
        adapter = self._adapter()
        await adapter.update_config(
            "security",
            {"max_upload_size_mb": "20"},
            updated_by="admin@test.com",
            ip_address="127.0.0.1",
        )
        value = await adapter.get_value("security", "max_upload_size_mb")
        assert value == "20"
        assert len(adapter.audit_log) == 1
        assert adapter.audit_log[0]["field_key"] == "max_upload_size_mb"
        assert adapter.audit_log[0]["user_email"] == "admin@test.com"

    @pytest.mark.asyncio
    async def test_credential_audit_is_redacted(self):
        adapter = self._adapter()
        await adapter.update_config(
            "ticket_system",
            {"gitlab_token": "supersecret"},
            updated_by="admin@test.com",
        )
        entry = adapter.audit_log[0]
        assert entry["new_value"] == "[REDACTED]"
        assert "supersecret" not in str(adapter.audit_log)

    @pytest.mark.asyncio
    async def test_get_credential_returns_value(self):
        adapter = self._adapter()
        await adapter.update_config("notifications", {"slack_bot_token": "xoxb-abc"})
        result = await adapter.get_credential("notifications", "slack_bot_token")
        assert result == "xoxb-abc"

    @pytest.mark.asyncio
    async def test_get_credential_empty_returns_none(self):
        adapter = self._adapter()
        result = await adapter.get_credential("ticket_system", "gitlab_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_sections(self):
        adapter = self._adapter()
        sections = await adapter.list_sections()
        assert "ticket_system" in sections
        assert "notifications" in sections
        assert "observability" in sections
        assert "security" in sections
