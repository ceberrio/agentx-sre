"""Auth routes — HU-P017.

Endpoints:
  POST /auth/mock-google-login  — mock Google OAuth (no real Google call)
  GET  /auth/me                 — current user info
  GET  /auth/users              — list all users (superadmin, admin)
  PUT  /auth/users/{id}/role    — update user role (superadmin only)
  POST /auth/logout             — client-side token discard signal (stateless)

All responses are in English (ARC-021).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.domain.entities.user import User, UserRole
from app.infrastructure.container import get_container

log = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class MockLoginRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address.")
        return v


class RoleUpdateRequest(BaseModel):
    role: UserRole


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    last_login_at: str | None

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            is_active=user.is_active,
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/mock-google-login", summary="Mock Google OAuth login")
async def mock_google_login(
    body: MockLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Simulate Google OAuth login without calling Google's servers.

    Accepts any valid email. If the user does not exist, auto-creates with
    role='operator'. Updates last_login_at on every call.

    Returns a signed JWT (HS256) that must be included as a Bearer token
    in subsequent requests.
    """
    container = get_container()
    result = await container.auth_service.mock_google_login(email=body.email, db=db)
    log.info("auth.mock_login", extra={"email": body.email})
    return result


@router.get("/me", summary="Get current user info")
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's profile.

    Requires a valid Bearer JWT in the Authorization header.
    Returns 401 if the token is missing, invalid, or expired.
    """
    return UserResponse.from_user(current_user)


@router.get("/users", summary="List all users (superadmin, admin)")
async def list_users(
    current_user: User = Depends(require_role(UserRole.SUPERADMIN, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """Return a list of all registered users.

    Requires role: superadmin or admin. Returns 403 for all other roles.
    """
    container = get_container()
    users = await container.auth_service.list_users(db=db)
    return [UserResponse.from_user(u) for u in users]


@router.put("/users/{user_id}/role", summary="Update user role (superadmin only)")
async def update_user_role(
    user_id: str,
    body: RoleUpdateRequest,
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update the role of a user by ID.

    Requires role: superadmin. Returns 403 for all other roles.
    Returns 404 if the user does not exist.
    """
    container = get_container()
    updated = await container.auth_service.update_user_role(
        user_id=user_id, new_role=body.role, db=db
    )
    log.info(
        "auth.role_updated_via_api",
        extra={
            "target_user_id": user_id,
            "new_role": body.role.value,
            "updated_by": str(current_user.id),
        },
    )
    return UserResponse.from_user(updated)


@router.post("/logout", summary="Logout (stateless — client discards token)")
async def logout(current_user: User = Depends(get_current_user)) -> dict:
    """Signal a logout intent.

    JWTs are stateless — this endpoint does not invalidate the token server-side.
    The client must discard the token. Included for SPA UX completeness.
    """
    log.info("auth.logout", extra={"user_id": str(current_user.id)})
    return {"message": "Logged out successfully."}
