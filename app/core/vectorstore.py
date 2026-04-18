"""Shared embedding model + Chroma vector-store accessors.

Both ingestion and retrieval need the *same* embedding function bound to the *same*
persisted Chroma instance — dimension mismatch would silently corrupt results (see
CLAUDE.md "Common Pitfalls" #1). Factoring this out prevents two code paths from
drifting apart.

Embedding model load is expensive (downloads + CPU init), so we cache it. Tests can
call `reset_vectorstore_cache()` to pick up a fresh settings object.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import get_settings

COLLECTION_NAME = "rag_chunks"


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Load the sentence-transformers model once per process."""
    return HuggingFaceEmbeddings(
        model_name=get_settings().embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    """Return the persisted Chroma collection, creating the directory if needed."""
    settings = get_settings()
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(persist_dir),
        # Force cosine distance so the relevance score conversion in retrieval.py is correct.
        collection_metadata={"hnsw:space": "cosine"},
    )


def reset_vectorstore_cache() -> None:
    """Drop cached embedding model + Chroma handle. Tests call this after overriding env."""
    get_embeddings.cache_clear()
    get_vectorstore.cache_clear()
