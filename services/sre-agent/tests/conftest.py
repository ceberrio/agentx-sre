"""Shared test fixtures for the sre-agent test suite (HU-P018).

Provides:
  - make_jwt_for_role: generate a real signed JWT for any role
  - jwt_settings: test-only JWT config (separate secret to avoid polluting real settings)
  - superadmin_headers / operator_headers / admin_headers / viewer_headers: ready-to-use
    Authorization header dicts for use in TestClient calls
  - api_key_headers: X-API-Key header dict (backward compat path)
  - build_jwt_container: build a SimpleNamespace container double with real JWT adapter
    and a mocked auth_service — the standard boilerplate for JWT-auth tests
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.auth.jwt_adapter import JWTAdapter
from app.domain.entities.user import User, UserRole
from app.infrastructure.config import settings as _app_settings

# ---------------------------------------------------------------------------
# Test JWT configuration
# ---------------------------------------------------------------------------

_TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-do-not-use-in-production"
_TEST_JWT_ALGORITHM = "HS256"
_TEST_JWT_EXPIRE_MINUTES = 480


def make_jwt_adapter() -> JWTAdapter:
    """Return a JWTAdapter configured with the test secret."""
    return JWTAdapter(
        secret=_TEST_JWT_SECRET,
        algorithm=_TEST_JWT_ALGORITHM,
        expire_minutes=_TEST_JWT_EXPIRE_MINUTES,
    )


def make_user(
    role: UserRole = UserRole.OPERATOR,
    email: str | None = None,
    is_active: bool = True,
) -> User:
    """Create a User domain entity for tests."""
    _email = email or f"{role.value}@softserve-test.com"
    return User(
        id=uuid.uuid4(),
        email=_email,
        full_name=f"Test {role.value.title()}",
        role=role,
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
        last_login_at=None,
    )


def make_jwt_for_role(role: UserRole) -> str:
    """Generate a real signed JWT for the given role.

    The token is signed with _TEST_JWT_SECRET — do NOT use in non-test code.
    """
    adapter = make_jwt_adapter()
    user = make_user(role=role)
    return adapter.create_token(user)


def make_jwt_for_user(user: User) -> str:
    """Generate a real signed JWT for a specific User instance."""
    return make_jwt_adapter().create_token(user)


# ---------------------------------------------------------------------------
# Header fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def superadmin_headers() -> dict:
    """Authorization header with a valid SUPERADMIN JWT."""
    return {"Authorization": f"Bearer {make_jwt_for_role(UserRole.SUPERADMIN)}"}


@pytest.fixture
def admin_headers() -> dict:
    """Authorization header with a valid ADMIN JWT."""
    return {"Authorization": f"Bearer {make_jwt_for_role(UserRole.ADMIN)}"}


@pytest.fixture
def operator_headers() -> dict:
    """Authorization header with a valid OPERATOR JWT."""
    return {"Authorization": f"Bearer {make_jwt_for_role(UserRole.OPERATOR)}"}


@pytest.fixture
def flow_configurator_headers() -> dict:
    """Authorization header with a valid FLOW_CONFIGURATOR JWT."""
    return {"Authorization": f"Bearer {make_jwt_for_role(UserRole.FLOW_CONFIGURATOR)}"}


@pytest.fixture
def viewer_headers() -> dict:
    """Authorization header with a valid VIEWER JWT."""
    return {"Authorization": f"Bearer {make_jwt_for_role(UserRole.VIEWER)}"}


@pytest.fixture
def api_key_headers() -> dict:
    """X-API-Key header using the current app settings key (backward compat path)."""
    return {"X-API-Key": _app_settings.api_key}


@pytest.fixture
def invalid_jwt_headers() -> dict:
    """Authorization header with a tampered (invalid) JWT."""
    return {"Authorization": "Bearer this.is.not.a.valid.jwt.token"}


# ---------------------------------------------------------------------------
# Container builder helper
# ---------------------------------------------------------------------------


def build_jwt_container(
    current_user: User | None = None,
    role: UserRole = UserRole.SUPERADMIN,
) -> SimpleNamespace:
    """Build a minimal container double where JWT auth is real but DB is mocked.

    The returned container has:
      - jwt_adapter: real JWTAdapter with the test secret
      - auth_service: MagicMock with get_user_by_id stubbed to return current_user

    Use patch("app.api.deps.get_container", return_value=container) in your test.
    """
    _user = current_user or make_user(role=role)
    _jwt = make_jwt_adapter()
    _auth_svc = MagicMock()
    _auth_svc.get_user_by_id = AsyncMock(return_value=_user)
    return SimpleNamespace(jwt_adapter=_jwt, auth_service=_auth_svc)
