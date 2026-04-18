"""LLM provider interface + factory.

Keeping this thin is deliberate. The whole provider surface is one async method;
concrete providers own their SDK-specific retry + rate-limit handling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import Settings, get_settings


class LLMError(RuntimeError):
    """Raised when the provider is misconfigured or a call fails terminally."""


class LLMProvider(ABC):
    """Minimal contract every provider must satisfy."""

    name: str = "base"

    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """Return the model's completion for ``prompt``.

        Implementations must handle their own rate-limit retries. Raise ``LLMError`` if
        the call cannot be completed after retries.
        """


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Return the provider configured by the LLM_PROVIDER env var.

    Cached so the SDK client (and its connection pool) is reused across requests.
    Tests can bypass this via FastAPI dependency overrides or by clearing the cache.
    """
    settings = get_settings()
    return _build_provider(settings)


def _build_provider(settings: Settings) -> LLMProvider:
    # Imported lazily so tests that only exercise one provider don't pay to import both SDKs.
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise LLMError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set")
        from app.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
    raise LLMError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")


def reset_provider_cache() -> None:
    """Test helper so a new `LLM_PROVIDER` env var takes effect mid-process."""
    get_llm_provider.cache_clear()
