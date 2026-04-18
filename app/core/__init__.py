"""Core RAG pipeline: ingestion, retrieval, generation, evaluation."""

from app.core.evaluation import (
    latency_stats,
    run_evaluation,
    score_faithfulness,
    score_retrieval_precision,
)
from app.core.generation import build_prompt, generate_answer
from app.core.ingestion import ingest_pdf
from app.core.retrieval import retrieve
from app.core.vectorstore import get_embeddings, get_vectorstore, reset_vectorstore_cache

__all__ = [
    "build_prompt",
    "generate_answer",
    "get_embeddings",
    "get_vectorstore",
    "ingest_pdf",
    "latency_stats",
    "reset_vectorstore_cache",
    "retrieve",
    "run_evaluation",
    "score_faithfulness",
    "score_retrieval_precision",
]
