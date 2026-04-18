"""FastAPI routers, one per resource."""

from app.api import documents, query

__all__ = ["documents", "query"]
