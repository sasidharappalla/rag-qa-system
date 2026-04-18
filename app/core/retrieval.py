"""Query → retrieved chunks.

We use `similarity_search_with_score` (which returns Chroma's raw cosine distance
in [0, 2]) and convert it to a bounded relevance score in [0, 1] ourselves. This
gives the API a stable "higher is better" contract without relying on LangChain's
heuristic `relevance_score_fn` which has had different behaviours across versions.
"""

from __future__ import annotations

from app.core.vectorstore import get_vectorstore
from app.observability import RETRIEVAL_DURATION, time_block
from app.schemas.query import RetrievedChunk


def _distance_to_score(distance: float) -> float:
    """Map cosine distance in [0, 2] to a relevance score in [0, 1] (higher = better)."""
    return max(0.0, min(1.0, 1.0 - float(distance) / 2.0))


def retrieve(question: str, k: int = 4) -> list[RetrievedChunk]:
    """Return the top-k most relevant chunks for ``question``, sorted by descending score."""
    if k <= 0:
        raise ValueError("k must be a positive integer")

    vectorstore = get_vectorstore()
    with time_block(RETRIEVAL_DURATION):
        results = vectorstore.similarity_search_with_score(question, k=k)

    chunks: list[RetrievedChunk] = []
    for doc, distance in results:
        meta = doc.metadata or {}
        chunk_id = str(
            meta.get("chunk_id")
            or f"doc_{meta.get('document_id')}_chunk_{meta.get('chunk_index')}"
        )
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=doc.page_content,
                score=_distance_to_score(distance),
                document_id=meta.get("document_id"),
                chunk_index=meta.get("chunk_index"),
                source_page=meta.get("source_page"),
                source_filename=meta.get("source_filename"),
            )
        )
    chunks.sort(key=lambda c: c.score, reverse=True)
    return chunks
