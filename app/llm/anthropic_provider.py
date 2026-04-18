"""Anthropic implementation of LLMProvider. Mirrors the OpenAI provider's shape."""

from __future__ import annotations

from anthropic import APIConnectionError, APITimeoutError, AsyncAnthropic, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.llm.base import LLMError, LLMProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        reraise=True,
    )
    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        try:
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"Anthropic call failed: {e}") from e
        # Messages API returns a list of content blocks; we only requested text.
        parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
        return "".join(parts).strip()
