"""Schemas for the platform-demo compatibility endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    id: str
    score: float
    text: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class RetrievalSummary(BaseModel):
    chunks_used: int


class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    retrieval: RetrievalSummary
