"""FastAPI shared dependencies (SEC-CR-001, HU-P017, HU-P018).

Provides:
  - require_api_key: validates X-API-Key header (legacy, kept for reference)
  - get_db: yields an async SQLAlchemy session
  - get_current_user: verifies Bearer JWT and returns the current User
  - get_current_user_or_api_key: dual-auth — accepts Bearer JWT or X-API-Key
  - require_role: dependency factory for role-based access control (ARC-022)
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User, UserRole
from app.infrastructure.config import settings
from app.infrastructure.database import make_session_factory
from app.infrastructure.container import get_container

# ---------------------------------------------------------------------------
# Legacy API-key gate (SEC-CR-001)
# ---------------------------------------------------------------------------


async def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """Dependency that validates the X-API-Key header.

    Raises HTTP 401 when the key is missing or incorrect.
    Using Optional + explicit None check ensures FastAPI never intercepts a
    missing header as a 422 validation error — the function body always runs
    and returns a standards-compliant 401 with WWW-Authenticate.

    This is a lightweight static-secret gate suitable for a demo/hackathon
    environment. For production, replace with OAuth2 / mTLS (see SCALING.md).
    """
    if x_api_key is None or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "ApiKey"},
        )


# ---------------------------------------------------------------------------
# Database session (HU-P017)
# ---------------------------------------------------------------------------

# TODO: consolidate with container session_factory post-hackathon (H-01)
_session_factory = make_session_factory(settings.app_database_url)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional async DB session. Auto-closed after request."""
    async with _session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# JWT Bearer authentication (HU-P017, HU-P018)
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/mock-google-login", auto_error=False)

# Synthetic user returned when X-API-Key auth is used (CI/scripts compat).
# Fixed UUID so callers can detect "system" requests in logs if needed.
_SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _verify_jwt(token: str, db: AsyncSession) -> User:
    """Verify a Bearer JWT token and return the authenticated User from DB.

    Shared by get_current_user and get_current_user_or_api_key (DRY).
    Raises HTTP 401 if token is invalid, expired, or user is inactive.
    """
    container = get_container()
    payload = container.jwt_adapter.verify_token(token)

    user = await container.auth_service.get_user_by_id(payload.sub, db)
    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify Bearer JWT and return the current authenticated User.

    Raises HTTP 401 if token is missing, invalid, or expired.
    The user is re-fetched from DB on every request to ensure is_active is current.
    JWT-only: does NOT accept X-API-Key. Use get_current_user_or_api_key for
    backward-compat endpoints.
    """
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _verify_jwt(token, db)


# ---------------------------------------------------------------------------
# Dual-auth dependency (HU-P018)
# ---------------------------------------------------------------------------


async def get_current_user_or_api_key(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dual-auth dependency: accepts Bearer JWT or X-API-Key.

    Resolution order:
      1. Bearer JWT in Authorization header — validated fully; returns DB user.
      2. X-API-Key header — validated against settings.api_key; returns a
         synthetic SUPERADMIN user (backward compat for CI/scripts).
      3. Neither → HTTP 401.

    JWT takes precedence if both headers are present.
    Error messages follow ARC-021 (English only).
    RBAC is NOT enforced here — callers use require_role for that (ARC-022).
    """
    # --- JWT path ---
    if authorization is not None and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        return await _verify_jwt(token, db)

    # --- API key path (backward compat) ---
    if x_api_key is not None:
        if x_api_key != settings.api_key:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        return User(
            id=_SYSTEM_USER_ID,
            email="system@sre-agent.internal",
            full_name="System (API Key)",
            role=UserRole.SUPERADMIN,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    raise HTTPException(
        status_code=401,
        detail="Not authenticated.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# RBAC dependency factory (HU-P017, HU-P018, ARC-022)
# ---------------------------------------------------------------------------


def require_role(*roles: UserRole):
    """FastAPI dependency factory for role-based access control.

    Usage example:
        Depends(require_role(UserRole.SUPERADMIN, UserRole.ADMIN))

    Raises HTTP 403 if the authenticated user's role is not in the allowed list.
    Accepts Bearer JWT or X-API-Key via get_current_user_or_api_key.
    RBAC is enforced only at the route level — the domain layer has NO knowledge
    of roles (ARC-022).
    """
    async def _check(current_user: User = Depends(get_current_user_or_api_key)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{current_user.role.value}' is not authorized for this action.",
            )
        return current_user

    return _check
