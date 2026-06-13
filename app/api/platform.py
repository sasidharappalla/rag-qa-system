"""Simple platform-demo routes layered over the existing RAG pipeline."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.core.generation import generate_answer
from app.llm.base import LLMProvider, get_llm_provider
from app.observability import get_logger
from app.schemas.platform import (
    AskRequest,
    AskResponse,
    RetrievalSummary,
    SearchResponse,
    SearchResult,
)
from app.schemas.query import RetrievedChunk

router = APIRouter(tags=["platform-demo"])
logger = get_logger(__name__)

_MOCK_CHUNK = RetrievedChunk(
    chunk_id="doc-1",
    score=0.91,
    text="Mocked retrieved context for the query.",
)


def _search_chunks(query: str, settings: Settings) -> list[RetrievedChunk]:
    if settings.platform_demo_mode:
        return [_MOCK_CHUNK]
    from app.core.retrieval import retrieve

    return retrieve(query, k=4)


@router.get("/search", response_model=SearchResponse, summary="Retrieve relevant document chunks")
def search(
    q: str = Query(..., min_length=1, max_length=2000),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    start = time.perf_counter()
    chunks = _search_chunks(q, settings)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "search.complete",
        extra={
            "service": settings.service_name,
            "endpoint": "/search",
            "status": "ok",
            "results": len(chunks),
            "latency_ms": latency_ms,
        },
    )
    return SearchResponse(
        query=q,
        results=[
            SearchResult(id=chunk.chunk_id, score=chunk.score, text=chunk.text)
            for chunk in chunks
        ],
    )


@router.post("/ask", response_model=AskResponse, summary="Ask a grounded question")
async def ask(
    payload: AskRequest,
    settings: Settings = Depends(get_settings),
    provider: LLMProvider = Depends(get_llm_provider),
) -> AskResponse:
    start = time.perf_counter()
    chunks = _search_chunks(payload.question, settings)
    answer = await generate_answer(payload.question, chunks, provider)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "ask.complete",
        extra={
            "service": settings.service_name,
            "endpoint": "/ask",
            "status": "ok",
            "chunks_used": len(chunks),
            "model": provider.name,
            "latency_ms": latency_ms,
        },
    )
    return AskResponse(
        question=payload.question,
        answer=answer,
        model=provider.name,
        retrieval=RetrievalSummary(chunks_used=len(chunks)),
    )
