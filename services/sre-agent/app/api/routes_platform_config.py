"""Platform Configuration endpoints — HU-P032-A.

5 configuration sections, each with GET + PUT:
  GET  /config/ticket-system
  PUT  /config/ticket-system
  GET  /config/notifications
  PUT  /config/notifications
  GET  /config/ecommerce-repo
  PUT  /config/ecommerce-repo
  GET  /config/observability
  PUT  /config/observability
  GET  /config/security
  PUT  /config/security

Auth (HU-P018, ARC-022):
  All endpoints require Bearer JWT or X-API-Key with ADMIN or SUPERADMIN role.

Credential masking (ARC-024):
  GET responses NEVER return credential plaintext — credential fields are set to None.

Audit log (ARC-026):
  PUT writes one audit_log row per changed field in the same DB transaction.

Forbidden fields (ARC-025):
  PUT /config/observability rejects langfuse_public_key, langfuse_secret_key,
  langfuse_host, storage_provider with HTTP 400.

Error messages follow ARC-021 (English only).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from app.api.deps import require_role
from app.domain.entities.user import User, UserRole
from app.infrastructure.container import get_container

log = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

# ---------------------------------------------------------------------------
# Credential field keys — NEVER returned in HTTP GET responses (ARC-024).
# ---------------------------------------------------------------------------

_CREDENTIAL_KEYS: frozenset[str] = frozenset(
    {"gitlab_token", "jira_api_token", "slack_bot_token", "smtp_password"}
)

# Fields rejected in PUT /config/observability (ARC-025).
_OBSERVABILITY_FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {"langfuse_public_key", "langfuse_secret_key", "langfuse_host", "storage_provider"}
)


def _mask_credentials(config: dict) -> dict:
    """Return a copy of config with credential field values replaced by None."""
    return {
        k: (None if k in _CREDENTIAL_KEYS else v)
        for k, v in config.items()
    }


def _success_response() -> dict:
    return {"success": True, "updated_at": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Ticket System — section: ticket_system
# ---------------------------------------------------------------------------


class TicketSystemResponse(BaseModel):
    ticket_provider: Optional[str] = None
    gitlab_url: Optional[str] = None
    gitlab_project_id: Optional[str] = None
    gitlab_token: None = None  # always masked
    jira_url: Optional[str] = None
    jira_project_key: Optional[str] = None
    jira_api_token: None = None  # always masked


class TicketSystemUpdateRequest(BaseModel):
    ticket_provider: Optional[Literal["mock", "gitlab", "jira"]] = None
    gitlab_url: Optional[str] = None
    gitlab_project_id: Optional[str] = None
    gitlab_token: Optional[str] = None
    jira_url: Optional[str] = None
    jira_project_key: Optional[str] = None
    jira_api_token: Optional[str] = None


@router.get("/ticket-system", response_model=TicketSystemResponse)
async def get_ticket_system_config(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> TicketSystemResponse:
    container = get_container()
    try:
        raw = await container.platform_config_provider.get_config("ticket_system")
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.get_failed", extra={"section": "ticket_system", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be loaded. Database is unreachable.",
        ) from exc
    masked = _mask_credentials(raw)
    log.info("platform_config.read", extra={"section": "ticket_system", "user": current_user.email})
    return TicketSystemResponse(**{k: masked.get(k) for k in TicketSystemResponse.model_fields})


@router.put("/ticket-system")
async def update_ticket_system_config(
    request: Request,
    body: TicketSystemUpdateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return _success_response()
    container = get_container()
    ip = request.client.host if request.client else None
    try:
        await container.platform_config_provider.update_config(
            "ticket_system", updates, updated_by=current_user.email, ip_address=ip
        )
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.update_failed", extra={"section": "ticket_system", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be saved. Database is unreachable.",
        ) from exc
    log.info("platform_config.updated", extra={"section": "ticket_system", "user": current_user.email})
    return _success_response()


# ---------------------------------------------------------------------------
# Notifications — section: notifications
# ---------------------------------------------------------------------------


class NotificationsResponse(BaseModel):
    notify_provider: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_bot_token: None = None  # always masked
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: None = None  # always masked


class NotificationsUpdateRequest(BaseModel):
    notify_provider: Optional[Literal["mock", "slack", "email", "teams"]] = None
    slack_channel: Optional[str] = None
    slack_bot_token: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None

    @field_validator("smtp_port")
    @classmethod
    def _validate_smtp_port(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 65535):
            raise ValueError("smtp_port must be between 1 and 65535")
        return v


@router.get("/notifications", response_model=NotificationsResponse)
async def get_notifications_config(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> NotificationsResponse:
    container = get_container()
    try:
        raw = await container.platform_config_provider.get_config("notifications")
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.get_failed", extra={"section": "notifications", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be loaded. Database is unreachable.",
        ) from exc
    masked = _mask_credentials(raw)
    log.info("platform_config.read", extra={"section": "notifications", "user": current_user.email})
    return NotificationsResponse(**{k: masked.get(k) for k in NotificationsResponse.model_fields})


@router.put("/notifications")
async def update_notifications_config(
    request: Request,
    body: NotificationsUpdateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    raw = body.model_dump()
    updates: dict[str, str] = {}
    for k, v in raw.items():
        if v is not None:
            updates[k] = str(v)
    if not updates:
        return _success_response()
    container = get_container()
    ip = request.client.host if request.client else None
    try:
        await container.platform_config_provider.update_config(
            "notifications", updates, updated_by=current_user.email, ip_address=ip
        )
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.update_failed", extra={"section": "notifications", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be saved. Database is unreachable.",
        ) from exc
    log.info("platform_config.updated", extra={"section": "notifications", "user": current_user.email})
    return _success_response()


# ---------------------------------------------------------------------------
# Ecommerce Repo — section: ecommerce_repo
# ---------------------------------------------------------------------------


class EcommerceRepoResponse(BaseModel):
    context_provider: Optional[str] = None
    eshop_context_dir: Optional[str] = None
    faiss_index_path: Optional[str] = None


class EcommerceRepoUpdateRequest(BaseModel):
    context_provider: Optional[Literal["static", "faiss", "github"]] = None
    eshop_context_dir: Optional[str] = None
    faiss_index_path: Optional[str] = None


@router.get("/ecommerce-repo", response_model=EcommerceRepoResponse)
async def get_ecommerce_repo_config(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> EcommerceRepoResponse:
    container = get_container()
    try:
        raw = await container.platform_config_provider.get_config("ecommerce_repo")
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.get_failed", extra={"section": "ecommerce_repo", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be loaded. Database is unreachable.",
        ) from exc
    log.info("platform_config.read", extra={"section": "ecommerce_repo", "user": current_user.email})
    return EcommerceRepoResponse(**{k: raw.get(k) for k in EcommerceRepoResponse.model_fields})


@router.put("/ecommerce-repo")
async def update_ecommerce_repo_config(
    request: Request,
    body: EcommerceRepoUpdateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return _success_response()
    container = get_container()
    ip = request.client.host if request.client else None
    try:
        await container.platform_config_provider.update_config(
            "ecommerce_repo", updates, updated_by=current_user.email, ip_address=ip
        )
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.update_failed", extra={"section": "ecommerce_repo", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be saved. Database is unreachable.",
        ) from exc
    log.info("platform_config.updated", extra={"section": "ecommerce_repo", "user": current_user.email})
    return _success_response()


# ---------------------------------------------------------------------------
# Observability — section: observability
# ---------------------------------------------------------------------------


class ObservabilityResponse(BaseModel):
    log_level: Optional[str] = None
    governance_cache_ttl_s: Optional[str] = None
    explainability_provider: Optional[str] = None
    langfuse_enabled: Optional[str] = None


class ObservabilityUpdateRequest(BaseModel):
    log_level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR"]] = None
    governance_cache_ttl_s: Optional[int] = None
    explainability_provider: Optional[Literal["langfuse", "local", "none"]] = None
    langfuse_enabled: Optional[bool] = None

    @field_validator("governance_cache_ttl_s")
    @classmethod
    def _validate_cache_ttl(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 300):
            raise ValueError("governance_cache_ttl_s must be between 0 and 300")
        return v


@router.get("/observability", response_model=ObservabilityResponse)
async def get_observability_config(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> ObservabilityResponse:
    container = get_container()
    try:
        raw = await container.platform_config_provider.get_config("observability")
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.get_failed", extra={"section": "observability", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be loaded. Database is unreachable.",
        ) from exc
    log.info("platform_config.read", extra={"section": "observability", "user": current_user.email})
    return ObservabilityResponse(**{k: raw.get(k) for k in ObservabilityResponse.model_fields})


@router.put("/observability")
async def update_observability_config(
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    # ARC-025: read raw JSON first so Pydantic cannot silently strip forbidden fields.
    # If we let Pydantic parse the body first (via `body: ObservabilityUpdateRequest`),
    # extra fields are ignored (not rejected), which would bypass ARC-025 silently.
    try:
        raw: dict = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    found_forbidden = _OBSERVABILITY_FORBIDDEN_FIELDS & set(raw.keys())
    if found_forbidden:
        raise HTTPException(
            status_code=400,
            detail=f"Fields not configurable via API: {sorted(found_forbidden)}",
        )

    body = ObservabilityUpdateRequest(**raw)
    updates: dict[str, str] = {}
    for k, v in body.model_dump().items():
        if v is not None:
            updates[k] = str(v).lower() if isinstance(v, bool) else str(v)
    if not updates:
        return _success_response()
    container = get_container()
    ip = request.client.host if request.client else None
    try:
        await container.platform_config_provider.update_config(
            "observability", updates, updated_by=current_user.email, ip_address=ip
        )
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.update_failed", extra={"section": "observability", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be saved. Database is unreachable.",
        ) from exc
    log.info("platform_config.updated", extra={"section": "observability", "user": current_user.email})
    return _success_response()


# ---------------------------------------------------------------------------
# Security — section: security
# ---------------------------------------------------------------------------


class SecurityResponse(BaseModel):
    guardrails_llm_judge_enabled: Optional[str] = None
    max_upload_size_mb: Optional[str] = None


class SecurityUpdateRequest(BaseModel):
    guardrails_llm_judge_enabled: Optional[bool] = None
    max_upload_size_mb: Optional[int] = None

    @field_validator("max_upload_size_mb")
    @classmethod
    def _validate_upload_size(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 50):
            raise ValueError("max_upload_size_mb must be between 1 and 50")
        return v


@router.get("/security", response_model=SecurityResponse)
async def get_security_config(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> SecurityResponse:
    container = get_container()
    try:
        raw = await container.platform_config_provider.get_config("security")
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.get_failed", extra={"section": "security", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be loaded. Database is unreachable.",
        ) from exc
    log.info("platform_config.read", extra={"section": "security", "user": current_user.email})
    return SecurityResponse(**{k: raw.get(k) for k in SecurityResponse.model_fields})


@router.put("/security")
async def update_security_config(
    request: Request,
    body: SecurityUpdateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    raw = body.model_dump()
    updates: dict[str, str] = {}
    for k, v in raw.items():
        if v is not None:
            updates[k] = str(v).lower() if isinstance(v, bool) else str(v)
    if not updates:
        return _success_response()
    container = get_container()
    ip = request.client.host if request.client else None
    try:
        await container.platform_config_provider.update_config(
            "security", updates, updated_by=current_user.email, ip_address=ip
        )
    except Exception as exc:  # noqa: BLE001
        log.error("platform_config.update_failed", extra={"section": "security", "error": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="Configuration could not be saved. Database is unreachable.",
        ) from exc
    log.info("platform_config.updated", extra={"section": "security", "user": current_user.email})
    return _success_response()
