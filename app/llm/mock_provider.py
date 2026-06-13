"""Deterministic provider for local demos and deployment smoke tests."""

from __future__ import annotations

from app.llm.base import LLMProvider


class MockProvider(LLMProvider):
    """Return a stable answer without requiring a paid API or network call."""

    name = "mock-rag"

    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        del prompt, max_tokens
        return "Mocked grounded answer generated from retrieved context."
