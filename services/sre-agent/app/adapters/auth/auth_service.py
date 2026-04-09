"""Authentication service — HU-P017.

Handles mock Google OAuth login flow, user lookup, and user management.
All DB operations use SQLAlchemy async sessions.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.auth.jwt_adapter import JWTAdapter
from app.adapters.storage.models import UserRow
from app.domain.entities.user import User, UserRole

log = logging.getLogger(__name__)


def _row_to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        full_name=row.full_name,
        role=UserRole(row.role),
        is_active=row.is_active,
        created_at=row.created_at,
        last_login_at=row.last_login_at,
    )


class AuthService:
    """Coordinates mock Google OAuth and user management operations."""

    def __init__(self, jwt_adapter: JWTAdapter) -> None:
        self._jwt = jwt_adapter

    async def mock_google_login(self, email: str, db: AsyncSession) -> dict:
        """Mock Google OAuth login flow.

        1. Look up user by email in DB.
        2. If not found: auto-create with role='operator' (minimal access).
        3. Update last_login_at.
        4. Return JWT token + user info.
        """
        result = await db.execute(select(UserRow).where(UserRow.email == email))
        row = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if row is None:
            # Auto-create new user with minimal operator role
            row = UserRow(
                id=uuid.uuid4(),
                email=email,
                full_name=None,
                role=UserRole.OPERATOR.value,
                is_active=True,
                created_at=now,
                last_login_at=now,
                google_sub=f"mock-sub-{uuid.uuid4().hex[:8]}",
            )
            db.add(row)
            log.info("auth.user_autocreated", extra={"email": email, "role": UserRole.OPERATOR.value})
        else:
            row.last_login_at = now

        await db.commit()
        await db.refresh(row)

        user = _row_to_user(row)
        log.info("auth.login_success", extra={"user_id": str(user.id), "role": user.role.value})
        return self._jwt.create_mock_google_token(user)

    async def get_user_by_id(self, user_id: str, db: AsyncSession) -> User:
        """Fetch user from DB by UUID. Raises 404 if not found."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="User not found.") from exc

        row = await db.get(UserRow, uid)
        if row is None:
            raise HTTPException(status_code=404, detail="User not found.")
        return _row_to_user(row)

    async def list_users(self, db: AsyncSession) -> list[User]:
        """List all users ordered by created_at descending."""
        result = await db.execute(
            select(UserRow).order_by(UserRow.created_at.desc())
        )
        return [_row_to_user(r) for r in result.scalars().all()]

    async def update_user_role(
        self, user_id: str, new_role: UserRole, db: AsyncSession
    ) -> User:
        """Update a user's role. Raises 404 if user not found."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="User not found.") from exc

        row = await db.get(UserRow, uid)
        if row is None:
            raise HTTPException(status_code=404, detail="User not found.")

        old_role = row.role
        row.role = new_role.value
        await db.commit()
        await db.refresh(row)

        log.info(
            "auth.role_updated",
            extra={"user_id": user_id, "old_role": old_role, "new_role": new_role.value},
        )
        return _row_to_user(row)
