"""FastAPI routers, one per resource.

Routers are imported by ``app.main`` so demo mode can avoid importing the optional
RAG dependency graph.
"""

__all__ = ["documents", "evaluate", "health", "platform", "query"]
