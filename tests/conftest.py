"""Shared pytest fixtures.

Design notes:

* Env vars for DATABASE_URL / CHROMA_PERSIST_DIR / UPLOAD_DIR are set at module import
  so ``Settings`` (which is cached) never sees the developer's real values.
* Each test gets its own tmp dir for DB + Chroma + uploads. Caches are reset between
  tests so nothing from the previous test leaks through.
* Tests that need an LLM get a ``MockLLMProvider`` by default — no network, deterministic.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

# ---- Configure env BEFORE importing anything from app.* ----
_BOOT_ROOT = Path(tempfile.mkdtemp(prefix="rag-test-boot-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(_BOOT_ROOT / 'boot.db').as_posix()}")
os.environ.setdefault("CHROMA_PERSIST_DIR", str(_BOOT_ROOT / "chroma"))
os.environ.setdefault("UPLOAD_DIR", str(_BOOT_ROOT / "uploads"))
os.environ.setdefault("LLM_PROVIDER", "anthropic")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")
os.environ.setdefault("LOG_LEVEL", "WARNING")
(_BOOT_ROOT / "chroma").mkdir(parents=True, exist_ok=True)
(_BOOT_ROOT / "uploads").mkdir(parents=True, exist_ok=True)

# Now safe to import the app modules.
from app.config import get_settings  # noqa: E402
from app.core.vectorstore import reset_vectorstore_cache  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.session import SessionLocal, get_engine, init_db, reset_engine_cache  # noqa: E402
from app.llm.base import LLMProvider, get_llm_provider  # noqa: E402
from scripts.generate_samples import _build_pdf  # noqa: E402


class MockLLMProvider(LLMProvider):
    """Deterministic, offline LLM stand-in. Tests can either use the default responder
    or override it by setting ``responses`` or ``responder``."""

    name = "mock"

    def __init__(
        self,
        *,
        default: str = "This is a mock answer.",
        responses: list[str] | None = None,
        responder: Any = None,
    ) -> None:
        self.default = default
        self.responses = list(responses) if responses else []
        self.responder = responder
        self.calls: list[str] = []

    async def generate(self, prompt: str, max_tokens: int = 512) -> str:
        self.calls.append(prompt)
        if self.responder is not None:
            return self.responder(prompt)
        if self.responses:
            return self.responses.pop(0)
        return self.default


@pytest.fixture
def tmp_stores(tmp_path, monkeypatch):
    """Isolate DB + Chroma + uploads per test and re-init tables."""
    chroma_dir = tmp_path / "chroma"
    uploads_dir = tmp_path / "uploads"
    chroma_dir.mkdir()
    uploads_dir.mkdir()

    db_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(chroma_dir))
    monkeypatch.setenv("UPLOAD_DIR", str(uploads_dir))

    get_settings.cache_clear()
    reset_engine_cache()
    reset_vectorstore_cache()
    get_llm_provider.cache_clear()

    init_db()
    yield tmp_path

    # Best-effort teardown — Chroma's SQLite file may still be open on Windows.
    reset_vectorstore_cache()
    engine = get_engine()
    try:
        Base.metadata.drop_all(engine)
    except Exception:  # noqa: BLE001
        pass
    engine.dispose()
    reset_engine_cache()
    shutil.rmtree(chroma_dir, ignore_errors=True)


@pytest.fixture
def db_session(tmp_stores):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    """A well-formatted PDF with enough text to produce multiple chunks at chunk_size=1000."""
    out = tmp_path / "acme_sample.pdf"
    _build_pdf(
        out,
        [
            ("Acme Widget Company Handbook", "Title"),
            (
                "Acme Widget Company manufactures premium widgets. The company was "
                "founded in 2015 in Austin, Texas. Widgets are small handcrafted objects "
                "used for testing and demonstration purposes. The flagship product is the "
                "Widget Pro, which costs 42 dollars and comes in three colors: red, blue, "
                "and green. Acme has 87 employees and sold 12345 widgets last year. "
                "The company is privately held and is profitable on a full-year basis.",
                "BodyText",
            ),
            (
                "Employee benefits include four weeks of paid vacation per year, a fully "
                "subsidized gym membership, and a 401(k) plan with 5 percent company match. "
                "The office dog is named Pixel and she is a golden retriever. Free catered "
                "lunch is served every Wednesday and Friday. New hires receive a one-time "
                "home office stipend of 750 dollars to set up their remote workstation.",
                "BodyText",
            ),
            (
                "The widget manufacturing process starts with sourcing raw materials from "
                "three certified suppliers in the midwestern United States. Parts are cut "
                "on computer-numerical-control machines and assembled by hand in the Austin "
                "factory. Every widget is inspected by two independent quality engineers "
                "before being boxed for shipment. The average time from raw material to "
                "finished widget is 14 business hours.",
                "BodyText",
            ),
            (
                "Acme customer support is available Monday through Friday from 8 am to 6 pm "
                "Central Time. Warranty claims are processed within five business days, and "
                "the standard warranty runs for two full years from the date of purchase. "
                "Enterprise customers who sign an annual contract receive a dedicated "
                "account manager and a guaranteed four-hour support response time.",
                "BodyText",
            ),
        ],
    )
    return out


@pytest.fixture
def corrupt_pdf(tmp_path) -> Path:
    """A file with a .pdf extension that is not a valid PDF."""
    out = tmp_path / "not_really.pdf"
    out.write_bytes(b"this is absolutely not a PDF file, it's plain text with a lying extension")
    return out


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    return MockLLMProvider(default="Mocked answer about widgets.")


@pytest.fixture
def client(tmp_stores, mock_llm):
    """FastAPI TestClient with the LLM provider overridden to the mock."""
    from fastapi.testclient import TestClient

    from app.llm.base import get_llm_provider as real_get_llm_provider
    from app.main import app

    app.dependency_overrides[real_get_llm_provider] = lambda: mock_llm
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
