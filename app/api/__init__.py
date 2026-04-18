"""FastAPI routers, one per resource."""

from app.api import documents, evaluate, query

__all__ = ["documents", "evaluate", "query"]
