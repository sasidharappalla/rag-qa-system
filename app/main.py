"""FastAPI entrypoint.

Keep this file boring: wire middleware + routers + lifespan. All interesting logic
lives in app/core, app/llm, app/api. A reader should be able to skim main.py and
know exactly which endpoints exist.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, platform
from app.config import get_settings
from app.db.session import init_db
from app.observability import METRICS_APP, RequestContextMiddleware, configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db()
    logger.info(
        "app.start",
        extra={
            "service": settings.service_name,
            "status": "started",
            "environment": settings.app_env,
            "llm_provider": settings.llm_provider,
            "embedding_model": settings.embedding_model,
            "chroma_persist_dir": settings.chroma_persist_dir,
        },
    )
    yield
    logger.info("app.stop")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DocuQuery RAG Service",
        description=(
            "Upload PDFs, ask grounded questions, measure quality with a built-in eval suite. "
            "See CLAUDE.md / README.md for architecture."
        ),
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(platform.router)

    if not settings.platform_demo_mode:
        from app.api import documents, evaluate, query

        app.include_router(documents.router)
        app.include_router(query.router)
        app.include_router(evaluate.router)

    # Prometheus exposition as a sub-ASGI app.
    app.mount("/metrics", METRICS_APP)

    return app


app = create_app()
