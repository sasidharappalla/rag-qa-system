"""Phase 1 tests — PDF → chunks → Chroma, plus Document row state machine."""

from __future__ import annotations

from app.config import get_settings
from app.core.ingestion import ingest_pdf
from app.db.models import Document, DocumentStatus


def _create_document(db, pdf_path) -> int:
    doc = Document(filename=pdf_path.name, file_path=str(pdf_path), status=DocumentStatus.PENDING)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc.id


def test_ingest_produces_chunks(db_session, sample_pdf):
    doc_id = _create_document(db_session, sample_pdf)

    result = ingest_pdf(str(sample_pdf), doc_id, db_session)

    assert result.status == DocumentStatus.READY
    assert result.chunk_count > 0
    db_session.expire_all()
    row = db_session.get(Document, doc_id)
    assert row.status == DocumentStatus.READY
    assert row.chunk_count == result.chunk_count


def test_chunks_under_configured_size(db_session, sample_pdf):
    """RecursiveCharacterTextSplitter can exceed chunk_size slightly on boundaries; allow 10% overshoot."""
    doc_id = _create_document(db_session, sample_pdf)
    ingest_pdf(str(sample_pdf), doc_id, db_session)

    from app.core.vectorstore import get_vectorstore

    vs = get_vectorstore()
    raw = vs._collection.get(where={"document_id": doc_id})
    documents = raw.get("documents") or []
    assert documents, "expected stored chunks"
    chunk_size = get_settings().chunk_size
    for text in documents:
        assert len(text) <= chunk_size * 1.1


def test_document_transitions_to_ready(db_session, sample_pdf):
    doc_id = _create_document(db_session, sample_pdf)
    assert db_session.get(Document, doc_id).status == DocumentStatus.PENDING

    ingest_pdf(str(sample_pdf), doc_id, db_session)

    db_session.expire_all()
    assert db_session.get(Document, doc_id).status == DocumentStatus.READY


def test_corrupt_pdf_marks_document_failed(db_session, corrupt_pdf):
    doc_id = _create_document(db_session, corrupt_pdf)

    result = ingest_pdf(str(corrupt_pdf), doc_id, db_session)

    assert result.status == DocumentStatus.FAILED
    assert result.error_message
    db_session.expire_all()
    row = db_session.get(Document, doc_id)
    assert row.status == DocumentStatus.FAILED
    assert row.error_message
    assert row.chunk_count == 0


def test_metadata_contains_source_page_and_document_id(db_session, sample_pdf):
    doc_id = _create_document(db_session, sample_pdf)
    ingest_pdf(str(sample_pdf), doc_id, db_session)

    from app.core.vectorstore import get_vectorstore

    raw = get_vectorstore()._collection.get(where={"document_id": doc_id})
    metadatas = raw.get("metadatas") or []
    assert metadatas
    first = metadatas[0]
    assert first["document_id"] == doc_id
    assert "chunk_index" in first
    assert "source_page" in first
