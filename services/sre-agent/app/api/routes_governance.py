"""Governance configuration endpoints — HU-12 / DEC-A05.

Exposes governance thresholds stored in the platform_config table under the
'governance' section.  This is the API layer consumed by GovernancePage.tsx.

Endpoints:
  GET  /config/governance  — read current thresholds (admin / superadmin)
  PUT  /config/governance  — update one or more thresholds (admin / superadmin)

Auth (HU-P018, ARC-022):
  Both endpoints require Bearer JWT or X-API-Key with ADMIN or SUPERADMIN role.

Persistence (DEC-A05, ARC-020):
  Default values are seeded by migration 0006.  The adapter is
  PostgresPlatformConfigAdapter in production and MemoryPlatformConfigAdapter
  in tests — the route never touches SQL directly.

Kill switch (HU-12):
  kill_switch_enabled is stored as the string "true" / "false" in the DB
  (TEXT column) and converted to/from bool at the API boundary.

Error messages follow ARC-021 (English only).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.api.deps import require_role
from app.domain.entities.user import User, UserRole
from app.infrastructure.container import get_container

log = logging.getLogger(__name__)

router = APIRouter(prefix="/config/governance", tags=["governance"])

# Governance section key used in platform_config (must match migration 0006).
_SECTION = "governance"

# Valid severity values — must match the TS Severity union in types.ts.
_SEVERITY_VALUES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _success_response() -> dict:
    return {"success": True, "updated_at": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GovernanceResponse(BaseModel):
    """Governance thresholds returned by GET /config/governance.

    All fields are Optional to handle a fresh install before the seed runs.
    """

    confidence_escalation_min: Optional[float] = None
    quality_score_min_for_autoticket: Optional[float] = None
    severity_autoticket_threshold: Optional[str] = None
    max_rag_docs_to_expose: Optional[int] = None
    kill_switch_enabled: Optional[bool] = None


class GovernanceUpdateRequest(BaseModel):
    """Body accepted by PUT /config/governance.

    All fields are Optional — a caller may update a single threshold.
    """

    confidence_escalation_min: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    quality_score_min_for_autoticket: Optional[float] = Field(
        default=None, ge=0.0, le=1.0
    )
    severity_autoticket_threshold: Optional[
        Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    ] = None
    max_rag_docs_to_expose: Optional[int] = Field(default=None, ge=1, le=20)
    kill_switch_enabled: Optional[bool] = None

    @field_validator("confidence_escalation_min", "quality_score_min_for_autoticket")
    @classmethod
    def _validate_ratio(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Value must be between 0.00 and 1.00")
        return v

    @field_validator("max_rag_docs_to_expose")
    @classmethod
    def _validate_rag_docs(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 20):
            raise ValueError("max_rag_docs_to_expose must be between 1 and 20")
        return v


# ---------------------------------------------------------------------------
# GET /config/governance
# ---------------------------------------------------------------------------


@router.get("", response_model=GovernanceResponse)
async def get_governance_config(
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> GovernanceResponse:
    """Return current governance thresholds from the platform_config table."""
    container = get_container()
    try:
        raw: dict = await container.platform_config_provider.get_config(_SECTION)
    except Exception as exc:
        log.error(
            "governance_config.get_failed",
            extra={"section": _SECTION, "error": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail="Governance configuration could not be loaded. Database is unreachable.",
        ) from exc

    log.info(
        "governance_config.read",
        extra={"section": _SECTION, "user": current_user.email},
    )

    # Deserialize TEXT storage values to typed Python objects.
    def _to_float(key: str) -> Optional[float]:
        val = raw.get(key)
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _to_int(key: str) -> Optional[int]:
        val = raw.get(key)
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    def _to_bool(key: str) -> Optional[bool]:
        val = raw.get(key)
        if val is None:
            return None
        return str(val).lower() == "true"

    return GovernanceResponse(
        confidence_escalation_min=_to_float("confidence_escalation_min"),
        quality_score_min_for_autoticket=_to_float("quality_score_min_for_autoticket"),
        severity_autoticket_threshold=raw.get("severity_autoticket_threshold"),
        max_rag_docs_to_expose=_to_int("max_rag_docs_to_expose"),
        kill_switch_enabled=_to_bool("kill_switch_enabled"),
    )


# ---------------------------------------------------------------------------
# PUT /config/governance
# ---------------------------------------------------------------------------


@router.put("")
async def update_governance_config(
    request: Request,
    body: GovernanceUpdateRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPERADMIN)),
) -> dict:
    """Update one or more governance thresholds.

    Only fields present (non-None) in the body are written.
    kill_switch_enabled is persisted as the string 'true' / 'false' (TEXT column).
    """
    raw = body.model_dump()
    updates: dict[str, str] = {}
    for key, val in raw.items():
        if val is None:
            continue
        # Booleans must be serialized to lowercase string for TEXT column.
        if isinstance(val, bool):
            updates[key] = "true" if val else "false"
        else:
            updates[key] = str(val)

    if not updates:
        return _success_response()

    container = get_container()
    ip = request.client.host if request.client else None
    try:
        await container.platform_config_provider.update_config(
            _SECTION,
            updates,
            updated_by=current_user.email,
            ip_address=ip,
        )
    except Exception as exc:
        log.error(
            "governance_config.update_failed",
            extra={"section": _SECTION, "error": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail="Governance configuration could not be saved. Database is unreachable.",
        ) from exc

    log.info(
        "governance_config.updated",
        extra={"section": _SECTION, "keys": list(updates.keys()), "user": current_user.email},
    )
    return _success_response()
