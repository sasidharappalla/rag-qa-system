"""Core RAG pipeline.

Submodules are intentionally not imported here because the platform demo has a
smaller optional dependency set than the full RAG runtime.
"""

__all__ = ["evaluation", "generation", "ingestion", "retrieval", "vectorstore"]
