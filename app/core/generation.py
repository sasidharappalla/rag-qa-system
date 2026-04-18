"""Retrieved chunks + question → grounded answer.

Prompt is deliberately strict: "Answer only from the provided context" + explicit
fallback phrase if the answer isn't there. This is the main lever controlling
faithfulness — the evaluator's faithfulness score rises and falls with how well the
model respects this instruction.
"""

from __future__ import annotations

from app.llm.base import LLMProvider
from app.observability import GENERATION_DURATION, get_logger, time_block
from app.schemas.query import RetrievedChunk

logger = get_logger(__name__)

IDK_RESPONSE = "I don't know based on the provided documents."

SYSTEM_INSTRUCTION = (
    "You are a precise question-answering assistant. You will be given a QUESTION "
    "and a CONTEXT composed of excerpts from documents the user has uploaded. "
    "Answer the question using ONLY information contained in the CONTEXT. "
    "If the CONTEXT does not contain enough information to answer, reply exactly: "
    f'"{IDK_RESPONSE}" '
    "Do not speculate, do not use outside knowledge, do not invent citations. "
    "Keep the answer concise (1-4 sentences)."
)


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Assemble the single prompt string passed to the LLM.

    Exposed as a helper so tests can assert structure without calling the LLM.
    """
    if not chunks:
        context_block = "(no context retrieved)"
    else:
        parts = []
        for i, chunk in enumerate(chunks, start=1):
            header = f"[Source {i} — {chunk.source_filename or 'unknown'}, page {chunk.source_page}]"
            parts.append(f"{header}\n{chunk.text.strip()}")
        context_block = "\n\n".join(parts)

    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER:"
    )


async def generate_answer(
    question: str, chunks: list[RetrievedChunk], provider: LLMProvider
) -> str:
    """Call the configured LLM provider with the grounded prompt."""
    prompt = build_prompt(question, chunks)
    with time_block(GENERATION_DURATION):
        raw = await provider.generate(prompt, max_tokens=512)
    logger.info(
        "generation.complete",
        extra={
            "provider": provider.name,
            "question_length": len(question),
            "chunks_used": len(chunks),
            "answer_length": len(raw),
        },
    )
    return raw or IDK_RESPONSE
