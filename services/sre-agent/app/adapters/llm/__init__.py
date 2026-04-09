from .gemini_adapter import GeminiLLMAdapter
from .openrouter_adapter import OpenRouterLLMAdapter
from .circuit_breaker import LLMCircuitBreaker

# AnthropicLLMAdapter is optional — the `anthropic` SDK may not be installed.
# Import lazily so the rest of the package remains usable without the extra dep.
try:
    from .anthropic_adapter import AnthropicLLMAdapter
except ImportError:
    AnthropicLLMAdapter = None  # type: ignore[assignment,misc]

__all__ = [
    "GeminiLLMAdapter",
    "OpenRouterLLMAdapter",
    "AnthropicLLMAdapter",
    "LLMCircuitBreaker",
]
