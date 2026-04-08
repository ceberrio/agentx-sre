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

import logging
from dataclasses import dataclass
from typing import Optional

from app.domain.ports import (
    IContextProvider,
    ILLMProvider,
    INotifyProvider,
    IStorageProvider,
    ITicketProvider,
)
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


# ----- builders -----

def _build_single_llm(name: str, s: Settings) -> ILLMProvider:
    if name == "stub":
        from app.adapters.llm.stub_adapter import StubLLMAdapter
        return StubLLMAdapter()
    if name == "gemini":
        if not s.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY required for LLM_PROVIDER=gemini")
        from app.adapters.llm.gemini_adapter import GeminiLLMAdapter
        return GeminiLLMAdapter(api_key=s.gemini_api_key, model=s.gemini_model)
    if name == "openrouter":
        if not s.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY required for LLM_PROVIDER=openrouter")
        from app.adapters.llm.openrouter_adapter import OpenRouterLLMAdapter
        return OpenRouterLLMAdapter(api_key=s.openrouter_api_key, model=s.openrouter_model)
    if name == "anthropic":
        if not s.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY required for LLM_PROVIDER=anthropic")
        from app.adapters.llm.anthropic_adapter import AnthropicLLMAdapter
        return AnthropicLLMAdapter(api_key=s.anthropic_api_key, model=s.anthropic_model)
    raise RuntimeError(f"Unknown LLM provider: {name}")


def build_llm(s: Settings) -> ILLMProvider:
    primary = _build_single_llm(s.llm_provider, s)
    fallback: Optional[ILLMProvider] = None
    if s.llm_fallback_provider != "none" and s.llm_fallback_provider != s.llm_provider:
        try:
            fallback = _build_single_llm(s.llm_fallback_provider, s)
        except RuntimeError as e:
            log.warning("llm.fallback_unavailable", extra={"reason": str(e)})

    from app.adapters.llm.circuit_breaker import LLMCircuitBreaker

    return LLMCircuitBreaker(
        primary=primary,
        fallback=fallback,
        threshold=s.llm_circuit_breaker_threshold,
        cooldown_s=s.llm_circuit_breaker_cooldown_s,
        timeout_s=s.llm_timeout_s,
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
    raise RuntimeError(f"Unknown context provider: {s.context_provider}")


# ----- public bootstrap -----

_container: Optional[Container] = None


def bootstrap(s: Settings = settings) -> Container:
    """Build all adapters and cache them in module state."""
    global _container
    llm = build_llm(s)
    container = Container(
        llm=llm,
        ticket=build_ticket(s),
        notify=build_notify(s),
        storage=build_storage(s),
        context=build_context(s, llm),
    )
    log.info("container.bootstrapped", extra=container.adapter_summary())
    _container = container
    return container


def get_container() -> Container:
    if _container is None:
        raise RuntimeError("Container not bootstrapped — call bootstrap() at startup")
    return _container
