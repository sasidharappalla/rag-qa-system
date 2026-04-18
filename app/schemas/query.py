"""Schemas for the /query endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    k: int = Field(default=4, ge=1, le=20)


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    document_id: int | None = None
    chunk_index: int | None = None
    source_page: int | None = None
    source_filename: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[RetrievedChunk]
    latency_ms: int
    llm_provider: str
