"""Application settings loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Keep names stable — they're referenced from docker-compose.yml."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Database ----
    database_url: str = Field(
        default="postgresql+psycopg2://rag:rag@localhost:5432/rag",
        description="SQLAlchemy DB URL. Tests override this to point at SQLite.",
    )

    # ---- Vector store ----
    chroma_persist_dir: str = Field(default="./data/chroma")

    # ---- LLM ----
    llm_provider: Literal["openai", "anthropic"] = Field(default="anthropic")
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # ---- Embeddings ----
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ---- Chunking ----
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # ---- Retrieval defaults ----
    default_top_k: int = 4

    # ---- Ops ----
    log_level: str = "INFO"
    upload_dir: str = "./data/uploads"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. lru_cache makes this a lightweight singleton."""
    return Settings()
