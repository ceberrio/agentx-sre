"""Ports — abstract interfaces the domain depends on. Adapters implement these."""
from .llm_provider import ILLMProvider
from .ticket_provider import ITicketProvider
from .notify_provider import INotifyProvider
from .storage_provider import IStorageProvider
from .context_provider import IContextProvider

__all__ = [
    "ILLMProvider",
    "ITicketProvider",
    "INotifyProvider",
    "IStorageProvider",
    "IContextProvider",
]
