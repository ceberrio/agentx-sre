"""ILLMConfigProvider port — HU-P029.

Pure domain: no SQLAlchemy, no FastAPI imports (ARC-001).
Adapters must implement this interface to provide LLM configuration
persistence with encrypted API key storage.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.llm_config import LLMConfig


class ILLMConfigProvider(ABC):
    """Port for reading and writing LLM provider configuration.

    Implementations live in app/adapters/llm_config/.
    The domain layer never calls concrete adapters directly (DIP).
    """

    @abstractmethod
    async def get_llm_config(self) -> LLMConfig:
        """Return the current LLM configuration.

        Returns the persisted config if one exists, or bootstrap defaults
        derived from environment variables when no config has been saved yet.
        """

    @abstractmethod
    async def update_llm_config(self, config: LLMConfig) -> LLMConfig:
        """Persist a new LLM configuration.

        API keys in config are plaintext — the adapter is responsible for
        encrypting them before writing to storage.
        Returns the updated config (plaintext, for hot reload).
        """

    @abstractmethod
    async def get_api_key(self, provider: str) -> str | None:
        """Return the plaintext API key for the given provider name.

        Returns None if the provider has no configured key.
        Used by hot-reload logic to build new LLM adapters.
        """

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify that the backing store is reachable.

        Used by the health check endpoint and the GET /config/llm status field.
        Returns True if the storage backend responded successfully.
        """
