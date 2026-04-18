"""Prometheus metrics. Counters for outcomes, histograms for stage latencies.

The ASGI app is mounted at /metrics in app/main.py. We use the default global registry
so `prometheus_client.make_asgi_app()` picks everything up automatically.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import Counter, Histogram, make_asgi_app

# ---- Counters (cumulative outcome totals) ----

documents_ingested = Counter(
    "documents_ingested_total",
    "Number of PDF documents successfully ingested end-to-end.",
)
documents_failed = Counter(
    "documents_failed_total",
    "Number of ingestion runs that ended in failed status.",
)
queries_total = Counter(
    "queries_total",
    "Total number of /query calls received (pre-failure).",
)
queries_failed = Counter(
    "queries_failed_total",
    "Number of /query calls that raised before returning an answer.",
)

# ---- Histograms (stage latency) ----

INGESTION_DURATION = Histogram(
    "ingestion_duration_seconds",
    "End-to-end time for one ingest_pdf call.",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)
QUERY_DURATION = Histogram(
    "query_duration_seconds",
    "End-to-end time for one /query call (retrieval + generation).",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)
RETRIEVAL_DURATION = Histogram(
    "retrieval_duration_seconds",
    "Time spent in the retrieval step only.",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
)
GENERATION_DURATION = Histogram(
    "generation_duration_seconds",
    "Time spent in the LLM generation step only.",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0),
)


@contextmanager
def time_block(histogram: Histogram) -> Iterator[None]:
    """Small helper to observe how long a block of code takes."""
    start = time.perf_counter()
    try:
        yield
    finally:
        histogram.observe(time.perf_counter() - start)


# The ASGI sub-app that exposes /metrics. Mounted in app.main.
METRICS_APP = make_asgi_app()
