"""Typed env-var settings. Single source of truth for all configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ----- LLM -----
    # LLM provider, model, API keys, and circuit-breaker parameters are managed
    # in the database via the llm_config table (ARC-023).
    # Configure via the UI at http://localhost:5173 → LLM Config.
    # Do NOT add LLM variables here.

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

    # ----- LLM Config Provider (HU-P029) -----
    # When "postgres", config is persisted in llm_config table with encrypted keys.
    # When "memory", config lives in-process (testing/single-node only).
    llm_config_provider: Literal["memory", "postgres"] = "postgres"
    # Fernet key for encrypting API keys at rest. REQUIRED when llm_config_provider=postgres.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Must be a URL-safe base64-encoded 32-byte secret. Set CONFIG_ENCRYPTION_KEY env var.
    config_encryption_key: Optional[str] = None

    # ----- Context / RAG -----
    context_provider: Literal["static", "faiss", "github"] = "github"
    eshop_context_dir: Path = Path("/app/eshop-context")
    faiss_index_path: Path = Path("/data/faiss/eshop.index")
    # GitHub-indexed context (HU-P030)
    faiss_github_index_path: Path = Path("/data/faiss/eshop_github.index")
    eshop_repo_url: str = "https://github.com/dotnet-architecture/eShopOnWeb"

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

    # ----- JWT / Auth (HU-P017) -----
    # JWT_SECRET must be overridden in production — see _reject_stub_in_production.
    jwt_secret: str = "sre-dev-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours

    # ----- CORS (HU-P031) -----
    # Origins allowed to make cross-site requests to the API.
    # sre-web (Nginx Docker) + Vite dev server.
    # Never use "*" in production — explicit list required.
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://sre-web:80",
        "http://sre-web",
        "http://localhost:80",
    ]

    @model_validator(mode="after")
    def _reject_weak_jwt_in_production(self) -> "Settings":
        """Prevent insecure JWT secret in production — CR-005."""
        if self.app_env == "production":
            if self.jwt_secret == "sre-dev-jwt-secret-change-in-production":
                raise ValueError(
                    "JWT_SECRET must be changed in production. "
                    "Set JWT_SECRET to a secure random value (min 32 chars)."
                )
        return self


settings = Settings()
