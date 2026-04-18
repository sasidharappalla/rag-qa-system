"""Metrics, structured logging, and the Prometheus ASGI export."""

from app.observability.logging import RequestContextMiddleware, configure_logging, get_logger
from app.observability.metrics import (
    GENERATION_DURATION,
    INGESTION_DURATION,
    METRICS_APP,
    QUERY_DURATION,
    RETRIEVAL_DURATION,
    documents_failed,
    documents_ingested,
    queries_failed,
    queries_total,
    time_block,
)

__all__ = [
    "GENERATION_DURATION",
    "INGESTION_DURATION",
    "METRICS_APP",
    "QUERY_DURATION",
    "RETRIEVAL_DURATION",
    "RequestContextMiddleware",
    "configure_logging",
    "documents_failed",
    "documents_ingested",
    "get_logger",
    "queries_failed",
    "queries_total",
    "time_block",
]
