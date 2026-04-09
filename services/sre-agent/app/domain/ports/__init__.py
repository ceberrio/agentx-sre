"""Ports — abstract interfaces the domain depends on. Adapters implement these."""
from .llm_provider import ILLMProvider
from .ticket_provider import ITicketProvider
from .notify_provider import INotifyProvider
from .storage_provider import IStorageProvider
from .context_provider import IContextProvider
from .llm_config_provider import ILLMConfigProvider
from .platform_config_provider import IPlatformConfigProvider

__all__ = [
    "ILLMProvider",
    "ITicketProvider",
    "INotifyProvider",
    "IStorageProvider",
    "IContextProvider",
    "ILLMConfigProvider",
    "IPlatformConfigProvider",
]
