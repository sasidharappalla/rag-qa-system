"""Phase 3 tests — faithfulness scoring, retrieval precision, and latency stats."""

from __future__ import annotations

import pytest

from app.core.evaluation import latency_stats, score_faithfulness, score_retrieval_precision
from app.schemas.query import RetrievedChunk
from tests.conftest import MockLLMProvider


def _chunks(*texts: str) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=f"c{i}", text=t, score=0.5, document_id=1, chunk_index=i,
            source_page=1, source_filename="test.pdf",
        )
        for i, t in enumerate(texts)
    ]


# ---- Faithfulness ----

@pytest.mark.asyncio
async def test_faithfulness_parses_numeric_response():
    judge = MockLLMProvider(default="0.85")

    score = await score_faithfulness(
        answer="Acme makes widgets.",
        chunks=_chunks("Acme makes widgets in Austin."),
        judge=judge,
    )

    assert score == 0.85


@pytest.mark.asyncio
async def test_faithfulness_clamps_out_of_range_values():
    judge = MockLLMProvider(default="1.7")

    score = await score_faithfulness(
        answer="Some answer.",
        chunks=_chunks("Some context."),
        judge=judge,
    )

    assert 0.0 <= score <= 1.0
    assert score == 1.0


@pytest.mark.asyncio
async def test_faithfulness_handles_unparseable_response():
    judge = MockLLMProvider(default="I think the score is pretty high")

    score = await score_faithfulness(
        answer="Something.",
        chunks=_chunks("Something else."),
        judge=judge,
    )

    assert score == 0.0


@pytest.mark.asyncio
async def test_faithfulness_returns_zero_for_empty_answer():
    judge = MockLLMProvider(default="0.9")  # should not even be called
    score = await score_faithfulness("", _chunks("ctx"), judge)
    assert score == 0.0


# ---- Retrieval precision ----

def test_retrieval_precision_all_hit():
    chunks = _chunks("widget pro costs 42 dollars", "the office dog is named Pixel")
    precision, matched = score_retrieval_precision(chunks, ["widget", "Pixel"])

    assert precision == 1.0
    assert "widget" in matched
    assert "pixel" in matched


def test_retrieval_precision_partial_hit():
    chunks = _chunks("widget info here", "completely unrelated content")
    precision, matched = score_retrieval_precision(chunks, ["widget"])

    assert precision == 0.5
    assert matched == ["widget"]


def test_retrieval_precision_no_hits():
    chunks = _chunks("hello world", "goodbye world")
    precision, matched = score_retrieval_precision(chunks, ["widget"])

    assert precision == 0.0
    assert matched == []


def test_retrieval_precision_empty_inputs():
    assert score_retrieval_precision([], ["anything"]) == (0.0, [])
    assert score_retrieval_precision(_chunks("x"), []) == (0.0, [])


# ---- Latency stats ----

def test_latency_stats_percentiles():
    durations = [float(i) for i in range(1, 101)]  # 1..100 ms

    stats = latency_stats(durations)

    assert stats.count == 100
    assert stats.mean_ms == pytest.approx(50.5)
    # Nearest-rank percentiles on 1..100 give p50=50, p95=95, p99=99.
    assert stats.p50_ms == 50.0
    assert stats.p95_ms == 95.0
    assert stats.p99_ms == 99.0


def test_latency_stats_empty():
    stats = latency_stats([])
    assert stats.count == 0
    assert stats.p50_ms == 0.0
    assert stats.p95_ms == 0.0
    assert stats.p99_ms == 0.0


def test_latency_stats_single_value():
    stats = latency_stats([42.0])
    assert stats.count == 1
    assert stats.p50_ms == 42.0
    assert stats.p95_ms == 42.0
    assert stats.p99_ms == 42.0
    assert stats.mean_ms == 42.0
