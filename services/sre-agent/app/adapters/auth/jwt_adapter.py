"""JWT creation and verification adapter — HU-P017.

Uses python-jose with HS256 algorithm.
Secret comes from settings.jwt_secret — never hardcoded (ARC-008).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from jose import JWTError, jwt

from app.domain.entities.user import TokenPayload, User

log = logging.getLogger(__name__)

_ALGORITHM = "HS256"


class JWTAdapter:
    """Creates and verifies signed JWTs for mock Google OAuth flow."""

    def __init__(self, secret: str, algorithm: str = _ALGORITHM, expire_minutes: int = 480) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    def create_token(self, user: User, expires_delta_minutes: int | None = None) -> str:
        """Create a signed JWT for the given user. Default 8h expiry."""
        exp_minutes = expires_delta_minutes if expires_delta_minutes is not None else self._expire_minutes
        now = int(datetime.now(timezone.utc).timestamp())
        exp = now + (exp_minutes * 60)

        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "exp": exp,
            "iat": now,
            "mock": True,
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        log.info(
            "jwt.created",
            extra={"user_id": str(user.id), "role": user.role.value, "exp": exp},
        )
        return token

    def verify_token(self, token: str) -> TokenPayload:
        """Verify and decode a JWT. Raises HTTPException(401) if invalid."""
        try:
            raw = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except JWTError as exc:
            log.warning("jwt.invalid", extra={"reason": str(exc)})
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        return TokenPayload(
            sub=raw["sub"],
            email=raw["email"],
            role=raw["role"],
            exp=raw["exp"],
            iat=raw["iat"],
            mock=raw.get("mock", True),
        )

    def create_mock_google_token(self, user: User) -> dict:
        """Simulate what Google OAuth would return.

        Returns a dict with access_token, token_type, and user info.
        """
        access_token = self.create_token(user)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            },
        }
