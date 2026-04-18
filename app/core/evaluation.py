"""Evaluation: faithfulness (LLM-as-judge), retrieval relevance (keyword precision@k),
latency (p50/p95/p99).

LLM-as-judge is the industry norm but has known biases — self-preference, position
bias, score drift. We document these in README; an honest portfolio project says so
rather than pretending the number is ground truth.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.generation import generate_answer
from app.core.retrieval import retrieve
from app.llm.base import LLMProvider
from app.observability import get_logger
from app.schemas.evaluation import EvalItemResult, EvalReport, LatencyStats
from app.schemas.query import RetrievedChunk

logger = get_logger(__name__)

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

FAITHFULNESS_PROMPT = (
    "You are a strict evaluator. Given a CONTEXT and a proposed ANSWER, decide how "
    "faithfully the ANSWER is supported by the CONTEXT. Score on a scale from 0.0 "
    "to 1.0 where 1.0 means every factual claim in the ANSWER is directly supported "
    "by the CONTEXT and 0.0 means the ANSWER is not supported at all. Respond with "
    "ONLY a single number between 0 and 1. No words.\n\n"
    "CONTEXT:\n{context}\n\n"
    "ANSWER:\n{answer}\n\n"
    "SCORE:"
)


async def score_faithfulness(
    answer: str, chunks: list[RetrievedChunk], judge: LLMProvider
) -> float:
    """LLM-as-judge faithfulness in [0, 1]. Falls back to 0.0 if parsing fails."""
    if not answer.strip():
        return 0.0
    context = "\n\n".join(c.text for c in chunks) if chunks else "(no context)"
    prompt = FAITHFULNESS_PROMPT.format(context=context, answer=answer)
    raw = await judge.generate(prompt, max_tokens=16)
    match = _NUMBER_RE.search(raw)
    if not match:
        logger.warning("faithfulness.parse_failed", extra={"raw_response": raw[:120]})
        return 0.0
    try:
        score = float(match.group(0))
    except ValueError:
        return 0.0
    return max(0.0, min(1.0, score))


def score_retrieval_precision(
    chunks: list[RetrievedChunk], expected_keywords: list[str]
) -> tuple[float, list[str]]:
    """Return (precision@k, list of keywords that appeared in any retrieved chunk).

    Precision here is "fraction of retrieved chunks that contain at least one expected
    keyword". It's a crude metric but deterministic and transparent — an interviewer can
    read the code and know exactly what it measures.
    """
    if not chunks:
        return 0.0, []
    if not expected_keywords:
        return 0.0, []

    kws_lower = [kw.lower() for kw in expected_keywords]
    hits_in_any_chunk: set[str] = set()
    matching_chunks = 0
    for chunk in chunks:
        text_lower = chunk.text.lower()
        matched = [kw for kw in kws_lower if kw in text_lower]
        if matched:
            matching_chunks += 1
            hits_in_any_chunk.update(matched)
    precision = matching_chunks / len(chunks)
    return precision, sorted(hits_in_any_chunk)


def latency_stats(durations_ms: list[float]) -> LatencyStats:
    """p50 / p95 / p99 computed with the nearest-rank method on sorted durations."""
    if not durations_ms:
        return LatencyStats(p50_ms=0.0, p95_ms=0.0, p99_ms=0.0, mean_ms=0.0, count=0)
    ordered = sorted(durations_ms)
    n = len(ordered)

    def _pct(p: float) -> float:
        # Nearest-rank: index = ceil(p * n) - 1, clamped to last index.
        idx = max(0, min(n - 1, int(round(p * n)) - 1 if p * n >= 1 else 0))
        return ordered[idx]

    return LatencyStats(
        p50_ms=_pct(0.50),
        p95_ms=_pct(0.95),
        p99_ms=_pct(0.99),
        mean_ms=sum(ordered) / n,
        count=n,
    )


def load_dataset(dataset_path: str | Path) -> list[dict[str, Any]]:
    """Load the eval dataset (10-20 Q&A pairs)."""
    with open(dataset_path, encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        raise ValueError("Eval dataset must be a JSON array of objects")
    return items


async def run_evaluation(
    dataset: list[dict[str, Any]],
    provider: LLMProvider,
    judge: LLMProvider | None = None,
    k: int = 4,
) -> EvalReport:
    """Run the full eval suite and return an aggregated report.

    `judge` defaults to the same provider as `provider`. That's not ideal (self-preference
    bias — a provider tends to rate its own outputs higher) but in a single-provider
    deployment it's the best we can do locally. README documents this.
    """
    judge = judge or provider
    settings = get_settings()

    items: list[EvalItemResult] = []
    latencies: list[float] = []
    faithfulness_sum = 0.0
    precision_sum = 0.0

    for entry in dataset:
        question = entry["question"]
        expected_answer = entry.get("expected_answer", "")
        expected_keywords = entry.get("expected_source_keywords", []) or []

        start = time.perf_counter()
        chunks = retrieve(question, k=k)
        answer = await generate_answer(question, chunks, provider)
        latency_ms = int((time.perf_counter() - start) * 1000)

        faithfulness = await score_faithfulness(answer, chunks, judge)
        precision, matched = score_retrieval_precision(chunks, expected_keywords)

        faithfulness_sum += faithfulness
        precision_sum += precision
        latencies.append(latency_ms)

        items.append(
            EvalItemResult(
                question=question,
                expected_answer=expected_answer,
                generated_answer=answer,
                faithfulness=faithfulness,
                retrieval_precision=precision,
                retrieved_keywords_hit=matched,
                latency_ms=latency_ms,
            )
        )

    n = len(items) or 1
    return EvalReport(
        dataset_size=len(items),
        mean_faithfulness=faithfulness_sum / n,
        mean_retrieval_precision=precision_sum / n,
        latency=latency_stats(latencies),
        items=items,
        llm_provider=provider.name,
        embedding_model=settings.embedding_model,
    )
