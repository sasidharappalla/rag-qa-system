"""OpenAI implementation of LLMProvider.

Uses the async client. Rate-limit handling via tenacity with exponential backoff —
see CLAUDE.md "Common Pitfalls" #6: eval runs make k queries in a row, you will hit 429s
without this.
"""

from __future__ import annotations

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.llm.base import LLMError, LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        reraise=True,
    )
    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.0,  # Deterministic for eval reproducibility.
            )
        except Exception as e:  # noqa: BLE001 - wrap to surface a stable error type
            raise LLMError(f"OpenAI call failed: {e}") from e
        choice = response.choices[0].message.content or ""
        return choice.strip()
