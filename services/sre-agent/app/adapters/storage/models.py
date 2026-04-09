"""Shared SQLAlchemy ORM models for storage adapters — HU-P017.

UserRow lives here so it stays decoupled from domain entities (ARC-001).
The Base declared here is used by UserRow only; IncidentRow keeps its own
Base in postgres_adapter.py to avoid a circular-import refactor during hackathon.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# TODO: consolidate to shared Base (H-02)
class UserBase(DeclarativeBase):
    pass


class UserRow(UserBase):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="operator")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    google_sub: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True
    )
