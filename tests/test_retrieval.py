"""Phase 2 tests — retrieval returns k scored chunks sorted by relevance."""

from __future__ import annotations

from app.core.ingestion import ingest_pdf
from app.core.retrieval import retrieve
from app.db.models import Document, DocumentStatus


def _seed(db_session, pdf_path) -> int:
    doc = Document(filename=pdf_path.name, file_path=str(pdf_path), status=DocumentStatus.PENDING)
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    ingest_pdf(str(pdf_path), doc.id, db_session)
    return doc.id


def test_retrieve_returns_k_chunks(db_session, sample_pdf):
    _seed(db_session, sample_pdf)

    chunks = retrieve("What does Acme Widget Company make?", k=3)

    assert 1 <= len(chunks) <= 3
    assert all(c.text for c in chunks)
    assert all(isinstance(c.score, float) for c in chunks)


def test_chunks_sorted_by_score_desc(db_session, sample_pdf):
    _seed(db_session, sample_pdf)

    chunks = retrieve("What does Acme manufacture?", k=4)

    assert len(chunks) >= 2
    scores = [c.score for c in chunks]
    assert scores == sorted(scores, reverse=True), "retrieval results must be sorted by descending score"


def test_relevant_query_outranks_irrelevant(db_session, sample_pdf):
    """The top-1 chunk for a question about widgets should score higher than the top-1
    chunk for a completely unrelated question."""
    _seed(db_session, sample_pdf)

    relevant = retrieve("What are widgets made of?", k=1)[0]
    off_topic = retrieve("the capital of mongolia space station", k=1)[0]

    assert relevant.score >= off_topic.score


def test_k_validation(db_session, sample_pdf):
    _seed(db_session, sample_pdf)

    import pytest

    with pytest.raises(ValueError):
        retrieve("anything", k=0)
