"""Question-answering endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.generation import generate_answer
from app.core.retrieval import retrieve
from app.db.models import QueryLog
from app.db.session import get_db
from app.llm.base import LLMError, LLMProvider, get_llm_provider
from app.observability import QUERY_DURATION, get_logger, queries_failed, queries_total, time_block
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)


@router.post("", response_model=QueryResponse, summary="Ask a grounded question")
async def run_query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
) -> QueryResponse:
    queries_total.inc()
    start = time.perf_counter()

    try:
        with time_block(QUERY_DURATION):
            chunks = retrieve(payload.question, k=payload.k)
            answer = await generate_answer(payload.question, chunks, provider)
    except LLMError as e:
        queries_failed.inc()
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e}") from e
    except Exception as e:  # noqa: BLE001 — report as 500 while counting it
        queries_failed.inc()
        logger.exception("query.failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    latency_ms = int((time.perf_counter() - start) * 1000)

    db.add(
        QueryLog(
            question=payload.question,
            answer=answer,
            retrieved_chunk_ids=[c.chunk_id for c in chunks],
            k=payload.k,
            latency_ms=latency_ms,
            llm_provider=provider.name,
        )
    )
    db.commit()

    logger.info(
        "query.complete",
        extra={
            "question_length": len(payload.question),
            "chunks_retrieved": len(chunks),
            "llm_provider": provider.name,
            "latency_ms": latency_ms,
        },
    )

    return QueryResponse(
        answer=answer,
        sources=chunks,
        latency_ms=latency_ms,
        llm_provider=provider.name,
    )
