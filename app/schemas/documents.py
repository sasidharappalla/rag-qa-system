"""Schemas for the /documents endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import DocumentStatus


class DocumentResponse(BaseModel):
    """Shape returned for both upload confirmation and list entries."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    upload_time: datetime
    status: DocumentStatus
    chunk_count: int
    error_message: str | None = None


class IngestionResult(BaseModel):
    """Internal result type returned from the ingestion pipeline."""

    document_id: int
    chunk_count: int
    status: DocumentStatus
    error_message: str | None = None
