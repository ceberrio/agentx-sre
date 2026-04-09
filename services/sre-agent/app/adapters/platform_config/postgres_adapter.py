"""PostgresPlatformConfigAdapter — HU-P032-A.

Stores platform configuration in the platform_config table with Fernet encryption
for credential fields, and writes audit_log rows in the same DB transaction (ARC-026).

Encryption contract:
  - Credential fields (is_credential=True) are encrypted with Fernet before writing.
  - Decryption happens on read — the port always returns plaintext.
  - Audit log stores '[REDACTED]' for old/new credential values (ARC-024).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Boolean, DateTime, Integer, String, Text, select, distinct
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.ports.platform_config_provider import IPlatformConfigProvider

log = logging.getLogger(__name__)

# Credential field keys — always redacted in audit log, always Fernet-encrypted in DB.
_CREDENTIAL_KEYS: frozenset[str] = frozenset(
    {"gitlab_token", "jira_api_token", "slack_bot_token", "smtp_password"}
)
_AUDIT_REDACTED = "[REDACTED]"


# TODO: consolidate to shared Base (H-02)
class _Base(DeclarativeBase):
    pass


class PlatformConfigRow(_Base):
    __tablename__ = "platform_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_credential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditLogRow(_Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    field_key: Mapped[str] = mapped_column(String(128), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PostgresPlatformConfigAdapter(IPlatformConfigProvider):
    """Persists platform configuration in PostgreSQL with encrypted credentials."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        fernet: Fernet,
    ) -> None:
        self._session_factory = session_factory
        self._fernet = fernet

    # ----- IPlatformConfigProvider -----

    async def get_config(self, section: str) -> dict[str, Any]:
        async with self._session_factory() as session:
            rows = await self._fetch_section(session, section)
            return {row.key: self._read_value(row) for row in rows}

    async def get_value(self, section: str, key: str) -> Any | None:
        async with self._session_factory() as session:
            row = await self._fetch_row(session, section, key)
            if row is None:
                return None
            return self._read_value(row)

    async def update_config(
        self,
        section: str,
        updates: dict[str, Any],
        updated_by: str = "",
        ip_address: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            async with session.begin():
                for key, new_plaintext in updates.items():
                    old_row = await self._fetch_row(session, section, key)
                    old_plain = self._read_value(old_row) if old_row else None
                    is_cred = self._is_credential(key, old_row)

                    stored_value = self._write_value(str(new_plaintext), is_cred)
                    stmt = (
                        pg_insert(PlatformConfigRow)
                        .values(
                            section=section,
                            key=key,
                            value=stored_value,
                            is_credential=is_cred,
                            created_at=now,
                            updated_at=now,
                        )
                        .on_conflict_do_update(
                            index_elements=["section", "key"],
                            set_={
                                "value": stored_value,
                                "updated_at": now,
                            },
                        )
                    )
                    await session.execute(stmt)

                    audit = AuditLogRow(
                        user_email=updated_by,
                        action="config_update",
                        section=section,
                        field_key=key,
                        old_value=_AUDIT_REDACTED if is_cred else str(old_plain) if old_plain is not None else None,
                        new_value=_AUDIT_REDACTED if is_cred else str(new_plaintext),
                        ip_address=ip_address,
                        created_at=now,
                    )
                    session.add(audit)

        log.info(
            "platform_config.updated",
            extra={
                "section": section,
                "keys": list(updates.keys()),
                "updated_by": updated_by,
            },
        )

    async def get_credential(self, section: str, key: str) -> str | None:
        value = await self.get_value(section, key)
        if not value:
            return None
        return value

    async def list_sections(self) -> list[str]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(distinct(PlatformConfigRow.section))
            )
            return list(result.scalars().all())

    # ----- Private helpers -----

    async def _fetch_section(
        self, session: AsyncSession, section: str
    ) -> list[PlatformConfigRow]:
        result = await session.execute(
            select(PlatformConfigRow).where(PlatformConfigRow.section == section)
        )
        return list(result.scalars().all())

    async def _fetch_row(
        self, session: AsyncSession, section: str, key: str
    ) -> PlatformConfigRow | None:
        result = await session.execute(
            select(PlatformConfigRow).where(
                PlatformConfigRow.section == section,
                PlatformConfigRow.key == key,
            )
        )
        return result.scalar_one_or_none()

    def _is_credential(self, key: str, row: PlatformConfigRow | None) -> bool:
        if row is not None:
            return bool(row.is_credential)
        return key in _CREDENTIAL_KEYS

    def _read_value(self, row: PlatformConfigRow) -> str | None:
        if row.value is None:
            return None
        if row.is_credential:
            return self._decrypt(row.value)
        return row.value

    def _write_value(self, plaintext: str, is_credential: bool) -> str | None:
        if not plaintext:
            return plaintext
        if is_credential:
            return self._encrypt(plaintext)
        return plaintext

    def _encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str | None) -> str | None:
        if ciphertext is None:
            return None
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            log.error("platform_config.decryption_failed — invalid token or wrong key")
            return None
