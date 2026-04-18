"""Liveness + dependency health check."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.vectorstore import get_vectorstore
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness + dependency health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    statuses: dict[str, str] = {"status": "ok"}

    try:
        db.execute(text("SELECT 1"))
        statuses["postgres"] = "ok"
    except Exception as e:  # noqa: BLE001
        statuses["postgres"] = f"error: {type(e).__name__}"
        statuses["status"] = "degraded"

    try:
        vs = get_vectorstore()
        # A cheap probe that exercises the underlying collection handle.
        vs._collection.count()
        statuses["chroma"] = "ok"
    except Exception as e:  # noqa: BLE001
        statuses["chroma"] = f"error: {type(e).__name__}"
        statuses["status"] = "degraded"

    return statuses
