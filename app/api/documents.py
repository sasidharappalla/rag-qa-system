"""Document upload + list/status routes.

POST returns 202 immediately — actual ingestion runs in a BackgroundTasks worker so
a slow PDF doesn't block the client. Clients poll GET /documents/{id} to learn when
the row transitions to ready/failed.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.ingestion import ingest_pdf
from app.db.models import Document, DocumentStatus
from app.db.session import SessionLocal, get_db
from app.observability import get_logger
from app.schemas.documents import DocumentResponse

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB


def _run_ingestion_background(file_path: str, document_id: int) -> None:
    """BackgroundTasks callable. Opens its own Session — the request session is
    already closed by the time this runs."""
    db = SessionLocal()
    try:
        ingest_pdf(file_path, document_id, db)
    finally:
        db.close()


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a PDF for ingestion",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MiB limit")

    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    dest = upload_dir / safe_name
    dest.write_bytes(content)

    doc = Document(
        filename=file.filename,
        file_path=str(dest),
        status=DocumentStatus.PENDING,
        chunk_count=0,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_run_ingestion_background, str(dest), doc.id)
    logger.info(
        "document.uploaded",
        extra={"document_id": doc.id, "doc_filename": doc.filename, "size_bytes": len(content)},
    )
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=list[DocumentResponse], summary="List all documents")
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    docs = db.query(Document).order_by(Document.id.desc()).all()
    return [DocumentResponse.model_validate(d) for d in docs]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get a single document's status",
)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentResponse:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return DocumentResponse.model_validate(doc)
