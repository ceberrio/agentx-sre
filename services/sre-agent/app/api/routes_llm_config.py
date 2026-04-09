"""LLM Provider Configuration endpoints — HU-P029.

GET  /config/llm  — return current config (masked). ADMIN or SUPERADMIN.
PUT  /config/llm  — update config + hot-reload LLM adapter. SUPERADMIN only.

Auth (HU-P018, ARC-022):
  Both endpoints require Bearer JWT or X-API-Key with the corresponding role.
  API keys are NEVER returned in plaintext — LLMConfig.masked() is always applied.

Hot reload flow (DEC-A06, < 5s network excluded):
  validate → DB UPSERT encrypted → get_llm_config() →
  container.reload_llm_adapter() → asyncio.Lock → atomic swap → release →
  return {"config": masked, "reload_status": "ok", "elapsed_ms": N}

Error messages follow ARC-021 (English only).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.api.deps import require_role
from app.domain.entities.llm_config import LLMConfig, LLMProviderName, LLMFallbackProviderName
from app.domain.entities.user import User, UserRole
from app.infrastructure.container import get_container

log = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class LLMConfigUpdateRequest(BaseModel):
    """Body for PUT /config/llm. All fields are optional — only provided ones are updated."""

    provider: Optional[LLMProviderName] = None
    fallback_provider: Optional[LLMFallbackProviderName] = None
    model: Optional[str] = None
    fallback_model: Optional[str] = None
    # Plaintext API keys — stored encrypted in DB, never returned.
    api_key: Optional[str] = None
    fallback_api_key: Optional[str] = None
    circuit_breaker_threshold: Optional[int] = None
    circuit_breaker_cooldown_s: Optional[int] = None
    timeout_s: Optional[int] = None

    @field_validator("circuit_breaker_threshold")
    @classmethod
    def _validate_threshold(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("circuit_breaker_threshold must be >= 1")
        return v

    @field_validator("circuit_breaker_cooldown_s")
    @classmethod
    def _validate_cooldown(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("circuit_breaker_cooldown_s must be >= 1")
        return v

    @field_validator("timeout_s")
    @classmethod
    def _validate_timeout(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("timeout_s must be >= 1")
        return v


class LLMConfigResponse(BaseModel):
    """GET /config/llm response body. API keys are always masked."""

    config: LLMConfig
    storage_backend: str
    connection_ok: bool


class LLMConfigUpdateResponse(BaseModel):
    """PUT /config/llm response body."""

    config: LLMConfig
    reload_status: Literal["ok", "failed"]
    elapsed_ms: float
    message: str


# ---------------------------------------------------------------------------
# GET /config/llm
# ---------------------------------------------------------------------------


@router.get("/llm", response_model=LLMConfigResponse)
async def get_llm_config(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> LLMConfigResponse:
    """Return the current LLM provider configuration (API keys masked).

    Accessible by ADMIN and SUPERADMIN roles.
    """
    container = get_container()
    config = await container.llm_config_provider.get_llm_config()
    connection_ok = await container.llm_config_provider.test_connection()

    log.info(
        "llm_config.read",
        extra={"user": current_user.email, "provider": config.provider},
    )
    return LLMConfigResponse(
        config=config.masked(),
        storage_backend=type(container.llm_config_provider).__name__,
        connection_ok=connection_ok,
    )


# ---------------------------------------------------------------------------
# PUT /config/llm
# ---------------------------------------------------------------------------


@router.put("/llm", response_model=LLMConfigUpdateResponse)
async def update_llm_config(
    body: LLMConfigUpdateRequest,
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
) -> LLMConfigUpdateResponse:
    """Update LLM provider configuration and hot-reload the adapter.

    Accessible by SUPERADMIN role only.
    API keys in the request body are stored encrypted — never returned in plaintext.

    Hot reload completes in < 5s (network latency excluded, per DEC-A06).
    """
    container = get_container()

    # Load current config, merge with request fields.
    current = await container.llm_config_provider.get_llm_config()
    merged = _merge_config(current, body, updated_by=current_user.email)

    # Persist encrypted to DB.
    try:
        saved = await container.llm_config_provider.update_llm_config(merged)
    except Exception as exc:  # noqa: BLE001
        log.error("llm_config.persist_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail="Failed to persist LLM configuration. Check server logs.",
        ) from exc

    # Hot-reload the adapter atomically.
    try:
        elapsed_ms = await container.reload_llm_adapter(saved)
    except Exception as exc:  # noqa: BLE001
        log.error("llm_config.reload_failed", extra={"error": str(exc)})
        # Config was saved — reload failure is non-fatal, inform caller.
        return LLMConfigUpdateResponse(
            config=saved.masked(),
            reload_status="failed",
            elapsed_ms=0.0,
            message=(
                "Configuration saved but adapter reload failed. "
                "The previous adapter is still active. Check server logs."
            ),
        )

    log.info(
        "llm_config.reload_ok",
        extra={
            "user": current_user.email,
            "provider": saved.provider,
            "elapsed_ms": round(elapsed_ms, 1),
        },
    )
    return LLMConfigUpdateResponse(
        config=saved.masked(),
        reload_status="ok",
        elapsed_ms=round(elapsed_ms, 1),
        message=f"LLM adapter reloaded successfully. Provider: {saved.provider}.",
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _merge_config(
    current: LLMConfig,
    req: LLMConfigUpdateRequest,
    updated_by: str,
) -> LLMConfig:
    """Merge request fields into current config, keeping unchanged fields as-is.

    API key fields use a sentinel check: None in the request means "keep current",
    not "clear the key". This avoids accidental key erasure on partial updates.
    """
    return LLMConfig(
        provider=req.provider if req.provider is not None else current.provider,
        fallback_provider=(
            req.fallback_provider
            if req.fallback_provider is not None
            else current.fallback_provider
        ),
        model=req.model if req.model is not None else current.model,
        fallback_model=(
            req.fallback_model if req.fallback_model is not None else current.fallback_model
        ),
        # Keep existing key if request sends None — never erase accidentally.
        api_key=req.api_key if req.api_key is not None else current.api_key,
        fallback_api_key=(
            req.fallback_api_key
            if req.fallback_api_key is not None
            else current.fallback_api_key
        ),
        circuit_breaker_threshold=(
            req.circuit_breaker_threshold
            if req.circuit_breaker_threshold is not None
            else current.circuit_breaker_threshold
        ),
        circuit_breaker_cooldown_s=(
            req.circuit_breaker_cooldown_s
            if req.circuit_breaker_cooldown_s is not None
            else current.circuit_breaker_cooldown_s
        ),
        timeout_s=req.timeout_s if req.timeout_s is not None else current.timeout_s,
        updated_at=datetime.now(timezone.utc),
        updated_by=updated_by,
    )
