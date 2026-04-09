"""LLMConfig domain entity — HU-P029.

Pure domain: no SQLAlchemy, no FastAPI imports (ARC-001).
This entity holds LLM provider configuration and supports masking
of sensitive API keys before any HTTP response (ARC-021).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

LLMProviderName = Literal["gemini", "openrouter", "anthropic", "openai", "stub"]
LLMFallbackProviderName = Literal["gemini", "openrouter", "anthropic", "openai", "stub", "none"]

# Mask token shown instead of the real API key in HTTP responses.
_API_KEY_MASK = "sk-***"


class LLMConfig(BaseModel):
    """Mutable LLM provider configuration stored in the database.

    API keys are stored encrypted at rest and masked in HTTP responses.
    Call masked() before serializing to any HTTP response body.
    """

    # Defaults are "stub"/"none" so that a LLMConfig() with no arguments never
    # attempts to build a real provider adapter (which would fail with api_key=None).
    # Concrete provider values must always be supplied explicitly (ARC-023).
    provider: LLMProviderName = "stub"
    fallback_provider: LLMFallbackProviderName = "none"
    model: str = ""
    fallback_model: str = ""

    # Encrypted API keys (Fernet-encrypted, base64 strings stored in DB).
    # In-memory they are the PLAINTEXT keys after decryption.
    api_key: Optional[str] = None
    fallback_api_key: Optional[str] = None

    circuit_breaker_threshold: int = 3
    circuit_breaker_cooldown_s: int = 60
    timeout_s: int = 25

    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

    @field_validator("circuit_breaker_threshold")
    @classmethod
    def _validate_threshold(cls, v: int) -> int:
        if v < 1:
            raise ValueError("circuit_breaker_threshold must be >= 1")
        return v

    @field_validator("circuit_breaker_cooldown_s")
    @classmethod
    def _validate_cooldown(cls, v: int) -> int:
        if v < 1:
            raise ValueError("circuit_breaker_cooldown_s must be >= 1")
        return v

    @field_validator("timeout_s")
    @classmethod
    def _validate_timeout(cls, v: int) -> int:
        if v < 1:
            raise ValueError("timeout_s must be >= 1")
        return v

    def masked(self) -> "LLMConfig":
        """Return a copy of this config with API keys replaced by the mask token.

        ALWAYS use this method before including the config in any HTTP response.
        Never expose plaintext API keys to HTTP clients.
        """
        return self.model_copy(
            update={
                "api_key": _API_KEY_MASK if self.api_key else None,
                "fallback_api_key": _API_KEY_MASK if self.fallback_api_key else None,
            }
        )
