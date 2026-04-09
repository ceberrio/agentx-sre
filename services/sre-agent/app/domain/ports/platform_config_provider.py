"""IPlatformConfigProvider port — HU-P032-A.

Pure domain: no SQLAlchemy, no FastAPI imports (ARC-001).
Adapters must implement this interface to provide platform configuration
persistence with encrypted credential storage and atomic audit logging.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IPlatformConfigProvider(ABC):
    """Port for reading and writing platform configuration sections.

    Implementations live in app/adapters/platform_config/.
    The domain layer never calls concrete adapters directly (DIP).
    """

    @abstractmethod
    async def get_config(self, section: str) -> dict[str, Any]:
        """Return all key/value pairs for the given section.

        Credential fields are returned as plaintext after decryption.
        NEVER expose these values directly in HTTP responses — callers
        must mask credential fields before returning to clients (ARC-024).
        """

    @abstractmethod
    async def get_value(self, section: str, key: str) -> Any | None:
        """Return a single value for a section/key pair.

        Returns None if the section or key does not exist.
        """

    @abstractmethod
    async def update_config(
        self,
        section: str,
        updates: dict[str, Any],
        updated_by: str = "",
        ip_address: str | None = None,
    ) -> None:
        """Upsert one or more key/value pairs in a section.

        Credential fields are encrypted before persisting.
        One audit_log row per changed field is written in the same
        DB transaction (ARC-026 — no fire-and-forget).

        Args:
            section: configuration section name.
            updates: mapping of key -> new plaintext value.
            updated_by: email of the user performing the update.
            ip_address: source IP from the HTTP request, for audit log.
        """

    @abstractmethod
    async def get_credential(self, section: str, key: str) -> str | None:
        """Return the plaintext credential value for a section/key pair.

        Returns None if the key does not exist or its value is empty.
        Intended for internal adapter use only — never expose via HTTP.
        """

    @abstractmethod
    async def list_sections(self) -> list[str]:
        """Return the distinct section names present in the config store."""
