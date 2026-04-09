"""MemoryLLMConfigAdapter — HU-P029.

In-memory implementation of ILLMConfigProvider.
Used in tests and when STORAGE_PROVIDER=memory.
No encryption — API keys stored as plaintext in memory.
"""
from __future__ import annotations

import logging

from app.domain.entities.llm_config import LLMConfig
from app.domain.ports.llm_config_provider import ILLMConfigProvider

log = logging.getLogger(__name__)


class MemoryLLMConfigAdapter(ILLMConfigProvider):
    """Thread-safe in-memory LLM configuration store (single process only)."""

    def __init__(self, default_config: LLMConfig | None = None) -> None:
        self._config: LLMConfig = default_config or LLMConfig()

    async def get_llm_config(self) -> LLMConfig:
        return self._config

    async def update_llm_config(self, config: LLMConfig) -> LLMConfig:
        self._config = config
        log.info(
            "llm_config.updated_in_memory",
            extra={"provider": config.provider, "updated_by": config.updated_by},
        )
        return self._config

    async def get_api_key(self, provider: str) -> str | None:
        if provider == self._config.provider:
            return self._config.api_key
        if provider == self._config.fallback_provider:
            return self._config.fallback_api_key
        return None

    async def test_connection(self) -> bool:
        return True
