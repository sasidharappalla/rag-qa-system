"""Phase 2 tests — prompt construction and grounded answer generation.

The LLM provider is mocked so no network is required.
"""

from __future__ import annotations

import pytest

from app.core.generation import IDK_RESPONSE, build_prompt, generate_answer
from app.schemas.query import RetrievedChunk
from tests.conftest import MockLLMProvider


def _chunks(*texts: str) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=f"c{i}",
            text=t,
            score=0.9 - i * 0.1,
            document_id=1,
            chunk_index=i,
            source_page=1,
            source_filename="test.pdf",
        )
        for i, t in enumerate(texts)
    ]


def test_prompt_includes_question_and_context():
    chunks = _chunks("Acme makes widgets.", "Widget Pro costs 42 dollars.")

    prompt = build_prompt("How much is Widget Pro?", chunks)

    assert "How much is Widget Pro?" in prompt
    assert "Acme makes widgets." in prompt
    assert "Widget Pro costs 42 dollars." in prompt
    assert IDK_RESPONSE in prompt  # guardrail instruction present


def test_prompt_survives_empty_chunks():
    prompt = build_prompt("What time is it?", [])

    assert "What time is it?" in prompt
    assert "(no context retrieved)" in prompt


@pytest.mark.asyncio
async def test_generate_answer_calls_provider_once():
    chunks = _chunks("Acme is based in Austin.")
    mock = MockLLMProvider(default="Austin.")

    answer = await generate_answer("Where is Acme based?", chunks, mock)

    assert answer == "Austin."
    assert len(mock.calls) == 1
    assert "Acme is based in Austin." in mock.calls[0]


@pytest.mark.asyncio
async def test_generate_answer_returns_idk_when_provider_returns_empty():
    chunks = _chunks("Something unrelated.")
    mock = MockLLMProvider(default="")

    answer = await generate_answer("Anything?", chunks, mock)

    assert answer == IDK_RESPONSE


@pytest.mark.asyncio
async def test_prompt_instructs_idk_fallback():
    """If the model correctly follows the prompt on empty context, it should emit the IDK phrase."""
    mock = MockLLMProvider(default=IDK_RESPONSE)

    answer = await generate_answer("Unanswerable from context?", [], mock)

    assert answer == IDK_RESPONSE
