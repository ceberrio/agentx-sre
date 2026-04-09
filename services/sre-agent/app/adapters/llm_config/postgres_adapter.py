"""PostgresLLMConfigAdapter — HU-P029.

Stores LLM configuration in the llm_config table with Fernet encryption for API keys.
Uses SQLAlchemy 2.x async session factory (same pattern as PostgresStorageAdapter).

Encryption contract:
  - API keys are encrypted with Fernet(CONFIG_ENCRYPTION_KEY) before writing.
  - Fernet keys must be URL-safe base64-encoded 32-byte secrets (use Fernet.generate_key()).
  - Decryption happens on read — the domain entity always holds plaintext.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.entities.llm_config import LLMConfig
from app.domain.ports.llm_config_provider import ILLMConfigProvider

log = logging.getLogger(__name__)

# Singleton row key — we only ever have one active config row.
_CONFIG_ROW_KEY = "active"


# TODO: consolidate to shared Base (H-02)
class _Base(DeclarativeBase):
    pass


class LLMConfigRow(_Base):
    __tablename__ = "llm_config"

    config_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    fallback_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(256), nullable=False)
    fallback_model: Mapped[str] = mapped_column(String(256), nullable=False)
    # Fernet-encrypted, base64 ciphertext — NULL means "no key configured".
    api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fallback_api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    circuit_breaker_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    circuit_breaker_cooldown_s: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class PostgresLLMConfigAdapter(ILLMConfigProvider):
    """Persists LLM configuration in PostgreSQL with encrypted API keys."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        fernet: Fernet,
        bootstrap_config: LLMConfig,
    ) -> None:
        self._session_factory = session_factory
        self._fernet = fernet
        # Fallback defaults when no row exists in DB yet.
        self._bootstrap_config = bootstrap_config

    # ----- ILLMConfigProvider -----

    async def get_llm_config(self) -> LLMConfig:
        """Return config from DB, falling back to bootstrap defaults if no row exists."""
        async with self._session_factory() as session:
            row = await self._fetch_row(session)
            if row is None:
                log.info("llm_config.not_found_in_db — returning bootstrap defaults")
                return self._bootstrap_config
            return self._row_to_entity(row)

    async def update_llm_config(self, config: LLMConfig) -> LLMConfig:
        """Upsert the config row with encrypted API keys."""
        api_key_enc = self._encrypt(config.api_key)
        fallback_api_key_enc = self._encrypt(config.fallback_api_key)

        async with self._session_factory() as session:
            async with session.begin():
                stmt = (
                    pg_insert(LLMConfigRow)
                    .values(
                        config_key=_CONFIG_ROW_KEY,
                        provider=config.provider,
                        fallback_provider=config.fallback_provider,
                        model=config.model,
                        fallback_model=config.fallback_model,
                        api_key_enc=api_key_enc,
                        fallback_api_key_enc=fallback_api_key_enc,
                        circuit_breaker_threshold=config.circuit_breaker_threshold,
                        circuit_breaker_cooldown_s=config.circuit_breaker_cooldown_s,
                        timeout_s=config.timeout_s,
                        updated_at=config.updated_at or datetime.now(timezone.utc),
                        updated_by=config.updated_by,
                    )
                    .on_conflict_do_update(
                        index_elements=["config_key"],
                        set_={
                            "provider": config.provider,
                            "fallback_provider": config.fallback_provider,
                            "model": config.model,
                            "fallback_model": config.fallback_model,
                            "api_key_enc": api_key_enc,
                            "fallback_api_key_enc": fallback_api_key_enc,
                            "circuit_breaker_threshold": config.circuit_breaker_threshold,
                            "circuit_breaker_cooldown_s": config.circuit_breaker_cooldown_s,
                            "timeout_s": config.timeout_s,
                            "updated_at": config.updated_at or datetime.now(timezone.utc),
                            "updated_by": config.updated_by,
                        },
                    )
                )
                await session.execute(stmt)

        log.info(
            "llm_config.updated",
            extra={"provider": config.provider, "updated_by": config.updated_by},
        )
        return config

    async def get_api_key(self, provider: str) -> str | None:
        """Return plaintext API key for the given provider name, or None."""
        config = await self.get_llm_config()
        if provider == config.provider:
            return config.api_key
        if provider == config.fallback_provider:
            return config.fallback_api_key
        return None

    async def test_connection(self) -> bool:
        """Ping the database by executing a lightweight query."""
        try:
            async with self._session_factory() as session:
                await session.execute(select(1))
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("llm_config.test_connection_failed", extra={"error": str(exc)})
            return False

    # ----- Private helpers -----

    async def _fetch_row(self, session: AsyncSession) -> LLMConfigRow | None:
        result = await session.execute(
            select(LLMConfigRow).where(LLMConfigRow.config_key == _CONFIG_ROW_KEY)
        )
        return result.scalar_one_or_none()

    def _encrypt(self, plaintext: str | None) -> str | None:
        # NOTE: This mirrors _encrypt_key() in
        # alembic/versions/0003_add_llm_config_table.py (seed migration).
        # If the encryption scheme changes, update both locations together.
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str | None) -> str | None:
        if ciphertext is None:
            return None
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            log.error("llm_config.decryption_failed — invalid token or wrong key")
            return None

    def _row_to_entity(self, row: LLMConfigRow) -> LLMConfig:
        return LLMConfig(
            provider=row.provider,  # type: ignore[arg-type]
            fallback_provider=row.fallback_provider,  # type: ignore[arg-type]
            model=row.model,
            fallback_model=row.fallback_model,
            api_key=self._decrypt(row.api_key_enc),
            fallback_api_key=self._decrypt(row.fallback_api_key_enc),
            circuit_breaker_threshold=row.circuit_breaker_threshold,
            circuit_breaker_cooldown_s=row.circuit_breaker_cooldown_s,
            timeout_s=row.timeout_s,
            updated_at=row.updated_at,
            updated_by=row.updated_by,
        )
