"""Liveness + dependency health check."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.observability import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", summary="Liveness + dependency health")
def health(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    statuses: dict[str, str] = {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.app_version,
    }

    if not settings.dependency_health_checks:
        logger.info(
            "health.checked",
            extra={
                "service": settings.service_name,
                "endpoint": "/health",
                "status": statuses["status"],
            },
        )
        return statuses

    try:
        db.execute(text("SELECT 1"))
        statuses["postgres"] = "ok"
    except Exception as e:  # noqa: BLE001
        statuses["postgres"] = f"error: {type(e).__name__}"
        statuses["status"] = "degraded"

    try:
        from app.core.vectorstore import get_vectorstore

        vs = get_vectorstore()
        # A cheap probe that exercises the underlying collection handle.
        vs._collection.count()
        statuses["chroma"] = "ok"
    except Exception as e:  # noqa: BLE001
        statuses["chroma"] = f"error: {type(e).__name__}"
        statuses["status"] = "degraded"

    logger.info(
        "health.checked",
        extra={
            "service": settings.service_name,
            "endpoint": "/health",
            "status": statuses["status"],
        },
    )
    return statuses
