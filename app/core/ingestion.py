"""PDF → chunks → embeddings → Chroma.

This is the write side of the RAG pipeline. We keep the Postgres `Document` row
in sync so the API can report progress (pending → processing → ready | failed).
"""

from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.vectorstore import get_vectorstore
from app.db.models import Document, DocumentStatus
from app.observability import (
    INGESTION_DURATION,
    documents_failed,
    documents_ingested,
    get_logger,
    time_block,
)
from app.schemas.documents import IngestionResult

logger = get_logger(__name__)


def ingest_pdf(file_path: str, document_id: int, db: Session) -> IngestionResult:
    """Load a PDF, chunk it, embed the chunks, and persist them in Chroma.

    The `Document` row transitions through pending → processing → {ready, failed}.
    On failure, the exception is caught, the row is marked failed with the error
    message, and a `failed` IngestionResult is returned (no re-raise) so background
    task callers don't need to install a separate error handler.
    """
    settings = get_settings()
    doc = db.get(Document, document_id)
    if doc is None:
        raise ValueError(f"Document id={document_id} not found")

    doc.status = DocumentStatus.PROCESSING
    doc.error_message = None
    db.commit()

    try:
        with time_block(INGESTION_DURATION):
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"Upload not found on disk: {path}")

            loader = PyPDFLoader(str(path))
            pages = loader.load()
            if not pages:
                raise ValueError("PDF contained no extractable text")

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            chunks = splitter.split_documents(pages)
            if not chunks:
                raise ValueError("Chunking produced no segments")

            ids: list[str] = []
            for idx, chunk in enumerate(chunks):
                chunk_id = f"doc_{document_id}_chunk_{idx}"
                ids.append(chunk_id)
                # Chroma metadata must be str/int/float/bool — coerce page numbers.
                source_page = chunk.metadata.get("page", 0)
                chunk.metadata = {
                    "document_id": int(document_id),
                    "chunk_index": int(idx),
                    "source_page": int(source_page) if source_page is not None else 0,
                    "source_filename": doc.filename,
                    "chunk_id": chunk_id,
                }

            vectorstore = get_vectorstore()
            vectorstore.add_documents(documents=chunks, ids=ids)

            doc.status = DocumentStatus.READY
            doc.chunk_count = len(chunks)
            db.commit()

        documents_ingested.inc()
        logger.info(
            "ingestion.complete",
            extra={
                "document_id": document_id,
                "doc_filename": doc.filename,
                "chunk_count": len(chunks),
                "page_count": len(pages),
            },
        )
        return IngestionResult(
            document_id=document_id,
            chunk_count=len(chunks),
            status=DocumentStatus.READY,
        )
    except Exception as e:  # noqa: BLE001 — we convert any error into a failed row.
        db.rollback()
        doc = db.get(Document, document_id)
        if doc is not None:
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(e)[:2000]
            db.commit()
        documents_failed.inc()
        logger.exception(
            "ingestion.failed",
            extra={"document_id": document_id, "doc_filename": getattr(doc, "filename", None)},
        )
        return IngestionResult(
            document_id=document_id,
            chunk_count=0,
            status=DocumentStatus.FAILED,
            error_message=str(e),
        )
