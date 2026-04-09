"""User domain entities — HU-P017.

Pure domain: no SQLAlchemy, no FastAPI imports (ARC-001).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class UserRole(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    FLOW_CONFIGURATOR = "flow_configurator"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool = True
    created_at: datetime
    last_login_at: Optional[datetime] = None


class TokenPayload(BaseModel):
    sub: str          # user id (UUID as string)
    email: str
    role: str
    exp: int          # unix timestamp
    iat: int
    mock: bool = True  # flag so it's clear this is a mock token
