"""Typed env-var settings. Single source of truth for all configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ----- LLM -----
    llm_provider: Literal["gemini", "openrouter", "anthropic", "openai", "stub"] = "gemini"
    llm_fallback_provider: Literal["gemini", "openrouter", "anthropic", "openai", "stub", "none"] = "openrouter"
    llm_circuit_breaker_threshold: int = 3
    llm_circuit_breaker_cooldown_s: int = 60
    llm_timeout_s: int = 25

    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "google/gemini-2.0-flash-exp:free"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # ----- Ticket -----
    ticket_provider: Literal["mock", "gitlab", "jira"] = "mock"
    gitlab_base_url: Optional[str] = None
    gitlab_token: Optional[str] = None
    gitlab_project_id: Optional[str] = None
    jira_base_url: Optional[str] = None
    jira_token: Optional[str] = None
    jira_project_key: Optional[str] = None

    # ----- Notify -----
    notify_provider: Literal["mock", "slack", "email", "teams"] = "mock"
    slack_webhook_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None

    # ----- Storage -----
    storage_provider: Literal["memory", "postgres"] = "postgres"
    app_database_url: str = "postgresql+asyncpg://sre:sre@app-db:5432/sre_agent"

    # ----- Context / RAG -----
    context_provider: Literal["static", "faiss"] = "faiss"
    eshop_context_dir: Path = Path("/app/eshop-context")
    faiss_index_path: Path = Path("/data/faiss/eshop.index")

    # ----- Mock services -----
    mock_services_url: str = "http://mock-services:9000"

    # ----- Observability -----
    langfuse_enabled: bool = True
    langfuse_public_key: str = "pk-lf-demo"
    langfuse_secret_key: str = "sk-lf-demo"
    langfuse_host: str = "http://langfuse-web:3000"
    log_level: str = "INFO"

    # ----- App -----
    app_env: str = "development"
    max_upload_size_mb: int = 5
    guardrails_llm_judge_enabled: bool = True

    # ----- API authentication (SEC-CR-001) -----
    # Set SRE_API_KEY in the environment for any non-local deployment.
    api_key: str = "sre-demo-key"

    @model_validator(mode="after")
    def _reject_stub_in_production(self) -> "Settings":
        """Prevent accidental stub usage in production — CR-005."""
        if self.app_env == "production":
            if self.llm_provider == "stub":
                raise ValueError(
                    "LLM_PROVIDER=stub is forbidden in production. Set a real provider."
                )
            if self.llm_fallback_provider == "stub":
                raise ValueError(
                    "LLM_FALLBACK_PROVIDER=stub is forbidden in production."
                )
        return self


settings = Settings()
