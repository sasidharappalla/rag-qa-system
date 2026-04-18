"""FastAPI routers, one per resource."""

from app.api import documents, evaluate, health, query

__all__ = ["documents", "evaluate", "health", "query"]
