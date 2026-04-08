"""FastAPI shared dependencies (SEC-CR-001).

Provides the require_api_key dependency, which validates the X-API-Key header
against the SRE_API_KEY environment variable. Applied to all incident,
webhook, and feedback routers. Health, metrics, and UI routes are exempt.
"""
from __future__ import annotations

from fastapi import Header, HTTPException
from app.infrastructure.config import settings


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """Dependency that validates the X-API-Key header.

    Raises HTTP 401 when the key is missing or incorrect.
    This is a lightweight static-secret gate suitable for a demo/hackathon
    environment. For production, replace with OAuth2 / mTLS (see SCALING.md).
    """
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
