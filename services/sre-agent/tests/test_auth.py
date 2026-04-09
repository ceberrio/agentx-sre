"""Tests for auth routes and RBAC — HU-P017.

AC-01: POST /auth/mock-google-login with existing email → JWT
AC-02: POST /auth/mock-google-login with new email → auto-creates operator
AC-03: GET /auth/me with valid JWT → user info
AC-04: GET /auth/me with expired/invalid/missing JWT → 401
AC-05: GET /auth/users requires superadmin or admin
AC-06: PUT /auth/users/{id}/role requires superadmin
BR-05: require_role dependency enforces role restrictions
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
from app.domain.entities.user import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECRET = "test-jwt-secret-for-unit-tests"
_ALGORITHM = "HS256"


def _jwt_adapter() -> JWTAdapter:
    return JWTAdapter(secret=_SECRET, algorithm=_ALGORITHM, expire_minutes=480)


def _make_user(
    role: UserRole = UserRole.OPERATOR,
    email: str = "test@softserve.com",
) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        full_name="Test User",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        last_login_at=None,
    )


def _make_app_with_mocks(
    auth_service: MagicMock | None = None,
    jwt: JWTAdapter | None = None,
    db_user: User | None = None,
) -> FastAPI:
    """Build an isolated FastAPI app with stubbed container and DB."""
    from app.api.routes_auth import router as auth_router

    _jwt = jwt or _jwt_adapter()
    _auth_svc = auth_service or MagicMock()

    container = SimpleNamespace(
        jwt_adapter=_jwt,
        auth_service=_auth_svc,
    )

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    # Override get_container to return our test container
    with patch("app.api.routes_auth.get_container", return_value=container):
        # Override get_db to return a dummy async session
        async def _fake_db():
            yield MagicMock()

        # Override get_current_user to bypass JWT for non-auth tests
        # (Each test that needs real JWT will use a real token)
        app.dependency_overrides = {}

    return app, container, _jwt


def _build_app_with_real_jwt_auth(
    current_user: User,
    auth_service: MagicMock | None = None,
) -> tuple[FastAPI, JWTAdapter]:
    """Build app where JWT is verified for real but DB lookup is mocked."""
    from app.api import deps
    from app.api.routes_auth import router as auth_router

    _jwt = _jwt_adapter()
    _auth_svc = auth_service or MagicMock()
    _auth_svc.get_user_by_id = AsyncMock(return_value=current_user)

    container = SimpleNamespace(
        jwt_adapter=_jwt,
        auth_service=_auth_svc,
    )

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    return app, _jwt, container


# ---------------------------------------------------------------------------
# AC-01: POST /auth/mock-google-login with existing email → JWT
# ---------------------------------------------------------------------------


def test_mock_login_existing_user_returns_jwt():
    """AC-01: POST /auth/mock-google-login with existing email returns a JWT and user info."""
    user = _make_user(role=UserRole.OPERATOR, email="operator@softserve.com")
    jwt_adapter = _jwt_adapter()

    auth_svc = MagicMock()
    auth_svc.mock_google_login = AsyncMock(
        return_value=jwt_adapter.create_mock_google_token(user)
    )

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.routes_auth.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            "/auth/mock-google-login",
            json={"email": "operator@softserve.com"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "operator@softserve.com"
    assert body["user"]["role"] == UserRole.OPERATOR.value


# ---------------------------------------------------------------------------
# AC-02: POST /auth/mock-google-login with new email → auto-creates operator
# ---------------------------------------------------------------------------


def test_mock_login_new_email_creates_operator_user():
    """AC-02: POST /auth/mock-google-login with new email auto-creates user with operator role."""
    new_user = _make_user(role=UserRole.OPERATOR, email="newuser@example.com")
    jwt_adapter = _jwt_adapter()

    auth_svc = MagicMock()
    auth_svc.mock_google_login = AsyncMock(
        return_value=jwt_adapter.create_mock_google_token(new_user)
    )

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.routes_auth.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            "/auth/mock-google-login",
            json={"email": "newuser@example.com"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == UserRole.OPERATOR.value
    # Verify auth_service was called with the new email
    auth_svc.mock_google_login.assert_called_once()
    call_kwargs = auth_svc.mock_google_login.call_args
    assert call_kwargs.kwargs["email"] == "newuser@example.com"


# ---------------------------------------------------------------------------
# AC-03: GET /auth/me with valid JWT → returns user info
# ---------------------------------------------------------------------------


def test_get_me_with_valid_jwt_returns_user_info():
    """AC-03: GET /auth/me with a valid Bearer JWT returns current user info."""
    user = _make_user(role=UserRole.ADMIN, email="sre-lead@softserve.com")
    jwt_adapter = _jwt_adapter()
    token = jwt_adapter.create_token(user)

    auth_svc = MagicMock()
    auth_svc.get_user_by_id = AsyncMock(return_value=user)

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "sre-lead@softserve.com"
    assert body["role"] == UserRole.ADMIN.value


# ---------------------------------------------------------------------------
# AC-04: GET /auth/me with invalid / expired / missing JWT → 401
# ---------------------------------------------------------------------------


def test_get_me_with_invalid_jwt_returns_401():
    """AC-04: GET /auth/me with a tampered token returns 401."""
    user = _make_user()
    jwt_adapter = _jwt_adapter()

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    auth_svc = MagicMock()
    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer this.is.not.a.valid.token"},
        )

    assert response.status_code == 401


def test_get_me_with_expired_jwt_returns_401():
    """AC-04: GET /auth/me with an expired JWT returns 401."""
    user = _make_user()
    # Create adapter with -1 minute expiry = already expired
    jwt_adapter_expired = JWTAdapter(secret=_SECRET, algorithm=_ALGORITHM, expire_minutes=-1)
    expired_token = jwt_adapter_expired.create_token(user)

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    # Verifier uses normal adapter — same secret but checks exp
    jwt_adapter = _jwt_adapter()
    auth_svc = MagicMock()
    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

    assert response.status_code == 401


def test_get_me_with_no_token_returns_401():
    """AC-04: GET /auth/me without Authorization header returns 401."""
    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    jwt_adapter = _jwt_adapter()
    auth_svc = MagicMock()
    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/auth/me")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# BR-05 / ARC-022: require_role dependency
# ---------------------------------------------------------------------------


def test_require_role_passes_for_matching_role():
    """BR-05: require_role allows access when user has an accepted role."""
    superadmin = _make_user(role=UserRole.SUPERADMIN, email="admin@softserve.com")
    jwt_adapter = _jwt_adapter()
    token = jwt_adapter.create_token(superadmin)

    auth_svc = MagicMock()
    auth_svc.get_user_by_id = AsyncMock(return_value=superadmin)
    auth_svc.list_users = AsyncMock(return_value=[superadmin])

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container), \
         patch("app.api.routes_auth.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


def test_require_role_blocks_insufficient_role():
    """BR-05: require_role returns 403 when user's role is not in the allowed list."""
    operator = _make_user(role=UserRole.OPERATOR, email="operator@softserve.com")
    jwt_adapter = _jwt_adapter()
    token = jwt_adapter.create_token(operator)

    auth_svc = MagicMock()
    auth_svc.get_user_by_id = AsyncMock(return_value=operator)

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container), \
         patch("app.api.routes_auth.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# AC-05: GET /auth/users
# ---------------------------------------------------------------------------


def test_list_users_as_superadmin_returns_list():
    """AC-05: GET /auth/users as superadmin returns all users."""
    superadmin = _make_user(role=UserRole.SUPERADMIN, email="admin@softserve.com")
    operator = _make_user(role=UserRole.OPERATOR, email="op@softserve.com")
    jwt_adapter = _jwt_adapter()
    token = jwt_adapter.create_token(superadmin)

    auth_svc = MagicMock()
    auth_svc.get_user_by_id = AsyncMock(return_value=superadmin)
    auth_svc.list_users = AsyncMock(return_value=[superadmin, operator])

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container), \
         patch("app.api.routes_auth.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2


def test_list_users_as_operator_returns_403():
    """AC-05: GET /auth/users as operator returns 403."""
    operator = _make_user(role=UserRole.OPERATOR, email="operator@softserve.com")
    jwt_adapter = _jwt_adapter()
    token = jwt_adapter.create_token(operator)

    auth_svc = MagicMock()
    auth_svc.get_user_by_id = AsyncMock(return_value=operator)

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container), \
         patch("app.api.routes_auth.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC-06: PUT /auth/users/{id}/role
# ---------------------------------------------------------------------------


def test_update_role_as_superadmin_succeeds():
    """AC-06: PUT /auth/users/{id}/role as superadmin updates the user's role."""
    superadmin = _make_user(role=UserRole.SUPERADMIN, email="admin@softserve.com")
    target_user = _make_user(role=UserRole.OPERATOR, email="op@softserve.com")
    updated_user = target_user.model_copy(update={"role": UserRole.ADMIN})
    jwt_adapter = _jwt_adapter()
    token = jwt_adapter.create_token(superadmin)

    auth_svc = MagicMock()
    auth_svc.get_user_by_id = AsyncMock(return_value=superadmin)
    auth_svc.update_user_role = AsyncMock(return_value=updated_user)

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container), \
         patch("app.api.routes_auth.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.put(
            f"/auth/users/{target_user.id}/role",
            json={"role": UserRole.ADMIN.value},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == UserRole.ADMIN.value


def test_update_role_as_admin_returns_403():
    """AC-06: PUT /auth/users/{id}/role as admin (not superadmin) returns 403."""
    admin = _make_user(role=UserRole.ADMIN, email="sre-lead@softserve.com")
    target_id = str(uuid.uuid4())
    jwt_adapter = _jwt_adapter()
    token = jwt_adapter.create_token(admin)

    auth_svc = MagicMock()
    auth_svc.get_user_by_id = AsyncMock(return_value=admin)

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container), \
         patch("app.api.routes_auth.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.put(
            f"/auth/users/{target_id}/role",
            json={"role": UserRole.OPERATOR.value},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Additional: POST /auth/logout
# ---------------------------------------------------------------------------


def test_logout_with_valid_jwt_returns_success():
    """POST /auth/logout with valid JWT returns success message."""
    user = _make_user(role=UserRole.OPERATOR)
    jwt_adapter = _jwt_adapter()
    token = jwt_adapter.create_token(user)

    auth_svc = MagicMock()
    auth_svc.get_user_by_id = AsyncMock(return_value=user)

    from app.api import deps
    from app.api.routes_auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[deps.get_db] = _fake_db

    container = SimpleNamespace(jwt_adapter=jwt_adapter, auth_service=auth_svc)

    with patch("app.api.deps.get_container", return_value=container):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert "message" in response.json()
