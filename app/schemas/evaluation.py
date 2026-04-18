"""Schemas for the /evaluate endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class LatencyStats(BaseModel):
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    count: int


class EvalItemResult(BaseModel):
    question: str
    expected_answer: str
    generated_answer: str
    faithfulness: float
    retrieval_precision: float
    retrieved_keywords_hit: list[str]
    latency_ms: int


class EvalReport(BaseModel):
    dataset_size: int
    mean_faithfulness: float
    mean_retrieval_precision: float
    latency: LatencyStats
    items: list[EvalItemResult]
    llm_provider: str
    embedding_model: str
