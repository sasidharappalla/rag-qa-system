"""Fast platform smoke tests that do not load an embedding model or call an LLM API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.session import reset_engine_cache
from app.llm.base import reset_provider_cache


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("PLATFORM_DEMO_MODE", "true")
    monkeypatch.setenv("DEPENDENCY_HEALTH_CHECKS", "false")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    get_settings.cache_clear()
    reset_engine_cache()
    reset_provider_cache()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    reset_provider_cache()
    reset_engine_cache()
    get_settings.cache_clear()


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "docuquery"


def test_search_returns_results(client: TestClient) -> None:
    response = client.get("/search", params={"q": "test"})

    assert response.status_code == 200
    assert response.json()["query"] == "test"
    assert response.json()["results"]


def test_ask_returns_grounded_response(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "What is this document about?"})

    assert response.status_code == 200
    assert response.json()["question"] == "What is this document about?"
    assert response.json()["model"] == "mock-rag"
