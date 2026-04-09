"""PostgresStorageAdapter — production. SQLAlchemy 2.x async + asyncpg.

Schema is documented in ARCHITECTURE.md §11. Migrations live in alembic/.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.entities import Incident, IncidentStatus, Severity
from app.domain.ports import IStorageProvider


# TODO: consolidate to shared Base (H-02)
class Base(DeclarativeBase):
    pass


class IncidentRow(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    reporter_email: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="received")
    severity: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    has_image: Mapped[bool] = mapped_column(Boolean, default=False)
    has_log: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _row_to_entity(row: IncidentRow) -> Incident:
    return Incident(
        id=row.id,
        reporter_email=row.reporter_email,
        title=row.title,
        description=row.description,
        status=IncidentStatus(row.status),
        severity=Severity(row.severity) if row.severity else None,
        blocked=row.blocked,
        blocked_reason=row.blocked_reason,
        has_image=row.has_image,
        has_log=row.has_log,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


_ALLOWED_UPDATE_FIELDS: frozenset[str] = frozenset({
    "status", "severity", "blocked", "blocked_reason",
    "has_image", "has_log", "updated_at",
})


class PostgresStorageAdapter(IStorageProvider):
    name = "postgres"

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_incident(self, incident: Incident) -> None:
        async with self._session_factory() as session:
            row = IncidentRow(
                id=incident.id,
                reporter_email=incident.reporter_email,
                title=incident.title,
                description=incident.description,
                status=incident.status.value,
                severity=incident.severity.value if incident.severity else None,
                blocked=incident.blocked,
                blocked_reason=incident.blocked_reason,
                has_image=incident.has_image,
                has_log=incident.has_log,
                created_at=incident.created_at,
                updated_at=incident.updated_at,
            )
            session.add(row)
            await session.commit()

    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        async with self._session_factory() as session:
            row = await session.get(IncidentRow, incident_id)
            return _row_to_entity(row) if row else None

    async def update_incident(
        self, incident_id: str, patch: dict[str, Any]
    ) -> Incident:
        invalid = set(patch.keys()) - _ALLOWED_UPDATE_FIELDS
        if invalid:
            raise ValueError(f"update_incident: disallowed fields: {invalid}")
        async with self._session_factory() as session:
            patch = {**patch, "updated_at": datetime.now(timezone.utc)}
            await session.execute(
                update(IncidentRow).where(IncidentRow.id == incident_id).values(**patch)
            )
            await session.commit()
            row = await session.get(IncidentRow, incident_id)
            if row is None:
                raise KeyError(incident_id)
            return _row_to_entity(row)

    async def list_incidents(self, limit: int = 50) -> list[Incident]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(IncidentRow).order_by(IncidentRow.created_at.desc()).limit(limit)
            )
            return [_row_to_entity(r) for r in result.scalars().all()]
