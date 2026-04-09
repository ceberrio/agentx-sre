"""Dependency Injection Container.

This is the ONLY file in the codebase that knows about concrete adapters.
Everything else (orchestration, api, domain) sees only port interfaces.

To add a new provider:
  1. Write the adapter class in app/adapters/<port>/.
  2. Add a branch to the corresponding _build_* function below.
  3. Document the env var in ARCHITECTURE.md §13.
  4. Done. No other file needs to change.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from app.adapters.auth.auth_service import AuthService
from app.adapters.auth.jwt_adapter import JWTAdapter
from app.domain.entities.llm_config import LLMConfig
from app.domain.ports import (
    IContextProvider,
    ILLMProvider,
    INotifyProvider,
    IStorageProvider,
    ITicketProvider,
)
from app.domain.ports.llm_config_provider import ILLMConfigProvider
from app.domain.ports.platform_config_provider import IPlatformConfigProvider
from app.infrastructure.config import Settings, settings
from app.infrastructure.database import make_session_factory

log = logging.getLogger(__name__)


@dataclass
class Container:
    """Holds the resolved adapter instances. Built once at app startup."""

    llm: ILLMProvider
    ticket: ITicketProvider
    notify: INotifyProvider
    storage: IStorageProvider
    context: IContextProvider
    jwt_adapter: JWTAdapter
    auth_service: AuthService
    llm_config_provider: ILLMConfigProvider
    platform_config_provider: IPlatformConfigProvider

    def __post_init__(self) -> None:
        # Hot-reload lock initialized here (not as a field default) so it is
        # always created within the running event loop — asyncio.Lock() called
        # at class definition time would bind to a different loop on Python 3.10+.
        self._reload_lock: asyncio.Lock = asyncio.Lock()

    def adapter_summary(self) -> dict[str, str]:
        return {
            "llm": self.llm.name,
            "ticket": self.ticket.name,
            "notify": self.notify.name,
            "storage": self.storage.name,
            "context": self.context.name,
        }

    def is_stub_mode(self) -> bool:
        """Return True when the active primary LLM adapter is the stub.

        The LLM field may be a circuit-breaker wrapper; unwrap one level to
        reach the primary adapter and inspect its name.
        """
        primary = getattr(self.llm, "_primary", self.llm)
        return getattr(primary, "name", "") == "stub"

    async def reload_llm_adapter(self, config: LLMConfig) -> float:
        """Hot-reload the LLM adapter from a new LLMConfig atomically.

        Acquires the reload lock, builds new adapters, then atomically swaps
        self.llm. Also reconfigures the circuit breaker parameters.
        Returns elapsed milliseconds (must be < 5000 per DEC-A06, network excluded).

        Raises RuntimeError if adapter build fails — caller must handle.
        """
        async with self._reload_lock:
            t0 = time.monotonic()
            new_llm = _build_llm_from_config(config)
            self.llm = new_llm
            elapsed_ms = (time.monotonic() - t0) * 1000
            log.info(
                "container.llm_reloaded",
                extra={"provider": config.provider, "elapsed_ms": round(elapsed_ms, 1)},
            )
            return elapsed_ms

    def reconfigure_circuit_breaker(self, threshold: int, cooldown_s: int) -> None:
        """Update circuit-breaker parameters on the active LLM adapter.

        Only effective when self.llm is an LLMCircuitBreaker instance.
        Called inside reload_llm_adapter — always under the reload lock.
        NOTE: called internally by reload_llm_adapter only.
        """
        from app.adapters.llm.circuit_breaker import LLMCircuitBreaker

        if isinstance(self.llm, LLMCircuitBreaker):
            self.llm.reconfigure(threshold=threshold, cooldown_s=cooldown_s)


# ----- builders -----


def _build_single_llm_from_key(name: str, api_key: str | None, model: str) -> ILLMProvider:
    """Build a single LLM adapter from explicit key + model (used in hot reload)."""
    if name == "stub":
        from app.adapters.llm.stub_adapter import StubLLMAdapter
        return StubLLMAdapter()
    if name == "gemini":
        if not api_key:
            raise RuntimeError("api_key required for provider=gemini")
        from app.adapters.llm.gemini_adapter import GeminiLLMAdapter
        return GeminiLLMAdapter(api_key=api_key, model=model)
    if name == "openrouter":
        if not api_key:
            raise RuntimeError("api_key required for provider=openrouter")
        from app.adapters.llm.openrouter_adapter import OpenRouterLLMAdapter
        return OpenRouterLLMAdapter(api_key=api_key, model=model)
    if name == "anthropic":
        if not api_key:
            raise RuntimeError("api_key required for provider=anthropic")
        from app.adapters.llm.anthropic_adapter import AnthropicLLMAdapter
        return AnthropicLLMAdapter(api_key=api_key, model=model)
    raise RuntimeError(f"Unknown LLM provider: {name}")


def _build_llm_from_config(config: LLMConfig) -> ILLMProvider:
    """Build LLMCircuitBreaker from a LLMConfig entity (used in hot reload)."""
    primary = _build_single_llm_from_key(config.provider, config.api_key, config.model)
    fallback: Optional[ILLMProvider] = None
    if config.fallback_provider != "none" and config.fallback_provider != config.provider:
        try:
            fallback = _build_single_llm_from_key(
                config.fallback_provider, config.fallback_api_key, config.fallback_model
            )
        except RuntimeError as e:
            log.warning("llm.fallback_unavailable", extra={"reason": str(e)})

    from app.adapters.llm.circuit_breaker import LLMCircuitBreaker

    return LLMCircuitBreaker(
        primary=primary,
        fallback=fallback,
        threshold=config.circuit_breaker_threshold,
        cooldown_s=config.circuit_breaker_cooldown_s,
        timeout_s=config.timeout_s,
    )


def build_llm_config_provider(s: Settings) -> ILLMConfigProvider:
    """Build the LLM config provider from settings.

    The bootstrap_config is always stub (ARC-023): LLM provider, model, API keys,
    and circuit-breaker params are DB-only config. Phase 2 in lifespan() hydrates
    the real adapter from DB after bootstrap.

    Raises RuntimeError if llm_config_provider=postgres and CONFIG_ENCRYPTION_KEY is missing.
    """
    # Phase 1 safe default — stub until Phase 2 DB hydration replaces it.
    bootstrap_config = LLMConfig(
        provider="stub",
        fallback_provider="none",
        model="",
        fallback_model="",
        api_key=None,
        fallback_api_key=None,
    )

    if s.llm_config_provider == "memory":
        from app.adapters.llm_config.memory_adapter import MemoryLLMConfigAdapter
        return MemoryLLMConfigAdapter(default_config=bootstrap_config)

    if s.llm_config_provider == "postgres":
        if not s.config_encryption_key:
            raise RuntimeError(
                "CONFIG_ENCRYPTION_KEY is required when LLM_CONFIG_PROVIDER=postgres. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        from cryptography.fernet import Fernet
        from app.adapters.llm_config.postgres_adapter import PostgresLLMConfigAdapter

        fernet = Fernet(s.config_encryption_key.encode())
        session_factory = make_session_factory(s.app_database_url)
        return PostgresLLMConfigAdapter(
            session_factory=session_factory,
            fernet=fernet,
            bootstrap_config=bootstrap_config,
        )

    raise RuntimeError(f"Unknown llm_config_provider: {s.llm_config_provider}")


def _build_stub_llm() -> ILLMProvider:
    """Build a StubLLMAdapter wrapped in a circuit breaker (Phase 1 safe default).

    The real LLM adapter is installed in Phase 2 of lifespan() via reload_llm_adapter().
    """
    from app.adapters.llm.stub_adapter import StubLLMAdapter
    from app.adapters.llm.circuit_breaker import LLMCircuitBreaker

    return LLMCircuitBreaker(
        primary=StubLLMAdapter(),
        fallback=None,
        threshold=3,
        cooldown_s=60,
        timeout_s=25,
    )


def build_ticket(s: Settings) -> ITicketProvider:
    if s.ticket_provider == "mock":
        from app.adapters.ticket.mock_adapter import MockTicketAdapter
        return MockTicketAdapter(base_url=s.mock_services_url)
    if s.ticket_provider == "gitlab":
        if not (s.gitlab_base_url and s.gitlab_token and s.gitlab_project_id):
            raise RuntimeError("GitLab adapter requires GITLAB_BASE_URL, GITLAB_TOKEN, GITLAB_PROJECT_ID")
        from app.adapters.ticket.gitlab_adapter import GitLabTicketAdapter
        return GitLabTicketAdapter(
            base_url=s.gitlab_base_url, token=s.gitlab_token, project_id=s.gitlab_project_id
        )
    if s.ticket_provider == "jira":
        if not (s.jira_base_url and s.jira_token and s.jira_project_key):
            raise RuntimeError("Jira adapter requires JIRA_BASE_URL, JIRA_TOKEN, JIRA_PROJECT_KEY")
        from app.adapters.ticket.jira_adapter import JiraTicketAdapter
        return JiraTicketAdapter(
            base_url=s.jira_base_url, token=s.jira_token, project_key=s.jira_project_key
        )
    raise RuntimeError(f"Unknown ticket provider: {s.ticket_provider}")


def build_notify(s: Settings) -> INotifyProvider:
    if s.notify_provider == "mock":
        from app.adapters.notify.mock_adapter import MockNotifyAdapter
        return MockNotifyAdapter(base_url=s.mock_services_url)
    if s.notify_provider == "slack":
        if not s.slack_webhook_url:
            raise RuntimeError("SLACK_WEBHOOK_URL required for NOTIFY_PROVIDER=slack")
        from app.adapters.notify.slack_adapter import SlackNotifyAdapter
        return SlackNotifyAdapter(webhook_url=s.slack_webhook_url)
    if s.notify_provider == "email":
        if not (s.smtp_host and s.smtp_user and s.smtp_password):
            raise RuntimeError("Email adapter requires SMTP_HOST, SMTP_USER, SMTP_PASSWORD")
        from app.adapters.notify.email_adapter import EmailNotifyAdapter
        return EmailNotifyAdapter(
            smtp_host=s.smtp_host,
            smtp_port=s.smtp_port,
            smtp_user=s.smtp_user,
            smtp_password=s.smtp_password,
        )
    raise RuntimeError(f"Unknown notify provider: {s.notify_provider}")


def build_storage(s: Settings) -> IStorageProvider:
    if s.storage_provider == "memory":
        from app.adapters.storage.memory_adapter import MemoryStorageAdapter
        return MemoryStorageAdapter()
    if s.storage_provider == "postgres":
        from app.adapters.storage.postgres_adapter import PostgresStorageAdapter
        return PostgresStorageAdapter(make_session_factory(s.app_database_url))
    raise RuntimeError(f"Unknown storage provider: {s.storage_provider}")


def build_platform_config_provider(s: Settings) -> IPlatformConfigProvider:
    """Build the platform config provider from settings.

    Falls back to MemoryPlatformConfigAdapter when CONFIG_ENCRYPTION_KEY is absent
    (test isolation — no DB or encryption key required).
    """
    if not s.config_encryption_key:
        from app.adapters.platform_config.memory_adapter import MemoryPlatformConfigAdapter
        return MemoryPlatformConfigAdapter()

    from cryptography.fernet import Fernet
    from app.adapters.platform_config.postgres_adapter import PostgresPlatformConfigAdapter

    fernet = Fernet(s.config_encryption_key.encode())
    session_factory = make_session_factory(s.app_database_url)
    return PostgresPlatformConfigAdapter(session_factory=session_factory, fernet=fernet)


def build_context(s: Settings, llm: ILLMProvider) -> IContextProvider:
    if s.context_provider == "static":
        from app.adapters.context.static_adapter import StaticContextAdapter
        return StaticContextAdapter(eshop_context_dir=s.eshop_context_dir)
    if s.context_provider == "faiss":
        from app.adapters.context.faiss_adapter import FAISSContextAdapter
        return FAISSContextAdapter(
            eshop_context_dir=s.eshop_context_dir,
            embedder=llm,
            index_path=s.faiss_index_path,
        )
    if s.context_provider == "github":
        from app.adapters.context.github_adapter import GithubContextAdapter
        return GithubContextAdapter(
            index_path=s.faiss_github_index_path,
            eshop_context_dir=s.eshop_context_dir,
            eshop_repo_url=s.eshop_repo_url,
        )
    raise RuntimeError(f"Unknown context provider: {s.context_provider}")


# ----- public bootstrap -----

_container: Optional[Container] = None


def build_auth(s: Settings) -> tuple[JWTAdapter, AuthService]:
    """Build JWT adapter and auth service from settings."""
    jwt_adapter = JWTAdapter(
        secret=s.jwt_secret,
        algorithm=s.jwt_algorithm,
        expire_minutes=s.jwt_expire_minutes,
    )
    auth_service = AuthService(jwt_adapter=jwt_adapter)
    return jwt_adapter, auth_service


def bootstrap(s: Settings = settings) -> Container:
    """Build all adapters and cache them in module state.

    Phase 1: builds a StubLLMAdapter as a safe default.
    Phase 2: lifespan() in main.py calls reload_llm_adapter() after reading DB config.
    """
    global _container
    llm = _build_stub_llm()
    jwt_adapter, auth_service = build_auth(s)
    llm_config_provider = build_llm_config_provider(s)
    platform_config_provider = build_platform_config_provider(s)
    container = Container(
        llm=llm,
        ticket=build_ticket(s),
        notify=build_notify(s),
        storage=build_storage(s),
        context=build_context(s, llm),
        jwt_adapter=jwt_adapter,
        auth_service=auth_service,
        llm_config_provider=llm_config_provider,
        platform_config_provider=platform_config_provider,
    )
    log.info("container.bootstrapped", extra=container.adapter_summary())
    _container = container
    return container


def get_container() -> Container:
    if _container is None:
        raise RuntimeError("Container not bootstrapped — call bootstrap() at startup")
    return _container
